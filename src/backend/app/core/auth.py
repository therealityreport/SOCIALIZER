from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, cast

import httpx
from fastapi import HTTPException, status
from jose import jwt
from jose.exceptions import JWTError
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AuthUser(BaseModel):
    """Normalized view of Auth0 claims for downstream handlers."""

    subject: str = Field(..., description="User identifier from the `sub` claim.")
    scopes: list[str] = Field(default_factory=list, description="Auth scopes supplied by Auth0.")
    permissions: list[str] = Field(default_factory=list, description="Auth0 RBAC permissions.")
    claims: dict[str, Any] = Field(default_factory=dict, description="Raw token claims.")


class Auth0Verifier:
    """Lightweight Auth0 JWT verifier with JWKS caching."""

    def __init__(self, settings: Settings) -> None:
        if not settings.auth0_domain or not settings.auth0_audience:
            raise RuntimeError("Auth0 verifier requires AUTH0_DOMAIN and AUTH0_AUDIENCE to be configured.")

        self.settings = settings
        self._jwks_cache: dict[str, Any] | None = None

    @property
    def jwks_url(self) -> str:
        issuer = self.settings.auth0_issuer
        assert issuer is not None  # already validated during __init__
        return f"{issuer}.well-known/jwks.json"

    def _fetch_jwks(self) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(self.jwks_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors best-effort
            logger.error("Failed to fetch Auth0 JWKS: %s", exc)
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth0 JWKS unavailable.") from exc
        jwks = response.json()
        keys = jwks.get("keys")
        if not isinstance(keys, list) or not keys:
            logger.error("Auth0 JWKS payload missing keys.")
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Auth0 JWKS invalid.")
        self._jwks_cache = {key["kid"]: key for key in keys if "kid" in key}
        return cast(dict[str, Any], self._jwks_cache)

    def _get_signing_key(self, kid: str) -> dict[str, Any]:
        cache = self._jwks_cache or self._fetch_jwks()
        key = cache.get(kid)
        if key:
            return key
        # refresh cache once if key not found
        cache = self._fetch_jwks()
        key = cache.get(kid)
        if not key:
            logger.error("Unable to find matching JWKS key for kid=%s", kid)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature.")
        return key

    def verify(self, token: str) -> AuthUser:
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed authorization token.") from exc

        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization token missing kid.")

        key = self._get_signing_key(kid)
        rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))

        try:
            claims = jwt.decode(
                token,
                rsa_key,
                algorithms=self.settings.auth0_algorithms,
                audience=self.settings.auth0_audience,
                issuer=self.settings.auth0_issuer,
            )
        except JWTError as exc:
            logger.debug("Auth0 token verification failed: %s", exc)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization token invalid.") from exc

        scopes_raw = claims.get("scope", "")
        scopes = scopes_raw.split() if isinstance(scopes_raw, str) else list(scopes_raw or [])
        permissions_raw = claims.get("permissions", [])
        permissions = permissions_raw if isinstance(permissions_raw, list) else []

        return AuthUser(
            subject=str(claims.get("sub", "")),
            scopes=[scope for scope in scopes if scope],
            permissions=[perm for perm in permissions if isinstance(perm, str)],
            claims=claims,
        )


@lru_cache(maxsize=1)
def get_auth0_verifier() -> Auth0Verifier:
    settings = get_settings()
    if not settings.auth0_domain or not settings.auth0_audience:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth0 integration not configured.",
        )
    return Auth0Verifier(settings)


def verify_bearer_token(token: str) -> AuthUser:
    verifier = get_auth0_verifier()
    return verifier.verify(token)
