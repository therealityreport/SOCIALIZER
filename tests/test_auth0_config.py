import os
import pathlib
import sys

import pytest
from fastapi import HTTPException

pytest.importorskip("jose")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "src" / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

ROOT_ENV_VARS = ("AUTH0_DOMAIN", "AUTH0_AUDIENCE", "AUTH0_CLIENT_ID", "AUTH0_ALGORITHMS")


def _reset_settings_cache() -> None:
    from app.core.config import get_settings
    get_settings.cache_clear()


def _reset_auth0_cache() -> None:
    from app.core import auth
    auth.get_auth0_verifier.cache_clear()


def test_auth0_verifier_requires_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import auth

    for var in ROOT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    _reset_settings_cache()
    _reset_auth0_cache()

    with pytest.raises(HTTPException) as exc:
        auth.get_auth0_verifier()
    assert exc.value.status_code == 503


def test_auth0_issuer_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("AUTH0_DOMAIN", "example.auth0.com/")
    monkeypatch.setenv("AUTH0_AUDIENCE", "https://api.socializer.test/")
    monkeypatch.delenv("AUTH0_ALGORITHMS", raising=False)

    _reset_settings_cache()
    settings = get_settings()

    assert settings.auth0_issuer == "https://example.auth0.com/"
    assert settings.auth0_algorithms == ["RS256"]

    _reset_settings_cache()
    _reset_auth0_cache()
