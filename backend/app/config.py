"""
Central runtime configuration.

Everything environment-specific (secrets, database URL, CORS origins, storage,
LLM settings) is read here, once, from environment variables. For local
development the values come from `backend/.env` (never committed); in production
they come from the hosting platform's environment settings.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
IS_PRODUCTION = APP_ENV == "production"

# Well-known development fallback. It is public (it was committed in the original
# code), so it must never be accepted in production.
_DEV_JWT_SECRET = "campusone-ai-dev-secret-key-change-in-production"


class ConfigError(RuntimeError):
    """Raised at startup when a required setting is missing or unsafe."""


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if IS_PRODUCTION:
        if not secret:
            raise ConfigError("JWT_SECRET is required when APP_ENV=production but is not set.")
        if secret == _DEV_JWT_SECRET or len(secret) < 32:
            raise ConfigError("JWT_SECRET is too weak for production: use at least 32 random characters.")
        return secret
    if not secret:
        print("WARNING: JWT_SECRET is not set - using the insecure development default. "
              "Copy backend/.env.example to backend/.env and set a real secret.")
        return _DEV_JWT_SECRET
    return secret


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        if IS_PRODUCTION:
            raise ConfigError("DATABASE_URL is required when APP_ENV=production but is not set.")
        return f"sqlite:///{(BACKEND_DIR / 'campusone.db').as_posix()}"
    # Hosting platforms commonly hand out the legacy "postgres://" scheme,
    # which SQLAlchemy 2.x no longer accepts.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _cors_origins() -> list:
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        origins = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
        if IS_PRODUCTION and "*" in origins:
            raise ConfigError("CORS_ORIGINS must list the real frontend origin(s) in production, not '*'.")
        return origins
    if IS_PRODUCTION:
        raise ConfigError("CORS_ORIGINS is required when APP_ENV=production (the deployed frontend origin).")
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


JWT_SECRET = _jwt_secret()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 8)))

DATABASE_URL = _database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

CORS_ORIGINS = _cors_origins()

# Auto-seeding wipes and regenerates demo data, so it is a development-only
# convenience for a brand-new empty database and is never allowed in production.
AUTO_SEED = _bool("AUTO_SEED", default=not IS_PRODUCTION) and not IS_PRODUCTION

# --- LLM (optional everywhere: every feature has a deterministic path) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-5-5").strip()

# --- Document storage ---
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").strip().lower()  # local | database
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", str(BACKEND_DIR / "storage")))
MAX_UPLOAD_BYTES = int(float(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024)
