from __future__ import annotations

from collections.abc import Generator

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import AuthUser, verify_bearer_token
from app.db.session import SessionLocal

http_bearer = HTTPBearer(auto_error=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(http_bearer)) -> AuthUser:
    return verify_bearer_token(credentials.credentials)
