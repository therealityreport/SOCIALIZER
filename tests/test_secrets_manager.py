import pathlib
import sys

import pytest

pytest.importorskip("jose")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "src" / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))


def _reset_caches():
    from app.core.config import get_settings
    from app.services.secrets import get_secrets_manager

    get_settings.cache_clear()
    get_secrets_manager.cache_clear()


def test_env_secret_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import secrets
    from app.core.config import get_settings

    monkeypatch.setenv("SECRETS_PROVIDER", "env")
    monkeypatch.setenv("SECRETS_PREFIX", "APP_")
    monkeypatch.setenv("APP_SAMPLE_SECRET", "s3cr3t")

    _reset_caches()

    settings = get_settings()
    assert settings.secrets_provider == "env"

    manager = secrets.get_secrets_manager()
    assert manager.get_secret("SAMPLE_SECRET") == "s3cr3t"
    # cached retrieval
    assert manager.get_secret("SAMPLE_SECRET") == "s3cr3t"

    _reset_caches()


def test_env_secret_missing_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import secrets

    monkeypatch.setenv("SECRETS_PROVIDER", "env")
    monkeypatch.setenv("SECRETS_PREFIX", "APP_")
    monkeypatch.delenv("APP_MISSING_SECRET", raising=False)

    _reset_caches()

    manager = secrets.get_secrets_manager()
    assert manager.get_secret("MISSING_SECRET", default="fallback") == "fallback"

    _reset_caches()
