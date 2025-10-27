import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKEND_PATH = ROOT / "src" / "backend"
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.core.config import get_settings
from app.services.hashing import hash_username


def test_hash_username_produces_consistent_hash():
    settings = get_settings()
    original_salt = settings.author_hash_salt
    settings.author_hash_salt = "unit-test-salt"
    try:
        hashed = hash_username("SampleUser")
        assert hashed is not None
        assert hashed == hash_username("SampleUser")
        assert hash_username("[deleted]") is None
        assert hash_username("") is None
    finally:
        settings.author_hash_salt = original_salt
