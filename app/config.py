# app/config.py
import os
from urllib.parse import quote_plus


def _env_target() -> str:
    return os.getenv("ENV_TARGET", "DEV").strip().upper()


def _target_get(name: str, default: str | None = None) -> str | None:
    target = _env_target()
    return os.getenv(f"{target}_{name}", os.getenv(name, default))


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- DATABASE ----
    DB_USER = _target_get("DB_USER", os.environ["DB_USER"])
    DB_PASSWORD_RAW = _target_get("DB_PASSWORD", os.environ["DB_PASSWORD"])
    DB_HOST = _target_get("DB_HOST", os.environ.get("DB_HOST", "localhost"))
    DB_PORT = _target_get("DB_PORT", os.environ.get("DB_PORT", "3306"))
    DB_NAME = _target_get("DB_NAME", os.environ["DB_NAME"])
    DB_PASSWORD = quote_plus(DB_PASSWORD_RAW)

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:"
        f"{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )

    # ---- JWT ----
    JWT_ISSUER = _target_get("JWT_ISSUER", "https://auth.ianeer.com")
    JWT_AUDIENCE = _target_get("JWT_AUDIENCE", os.getenv("JWT_AUDIENCE", "billaware"))
    JWT_PUBLIC_KEY_PATH = _target_get("JWT_PUBLIC_KEY_PATH", os.getenv("JWT_PUBLIC_KEY_PATH", "./jwt_public.pem"))

    # ---- AUTH ----
    AUTH_BASE_URL = (_target_get("AUTH_BASE_URL", "https://auth.ianeer.com") or "https://auth.ianeer.com").rstrip("/")
    AUTH_LOGIN_URL = _target_get("AUTH_LOGIN_URL", f"{AUTH_BASE_URL}/auth")
    AUTH_LOGOUT_URL = _target_get("AUTH_LOGOUT_URL", f"{AUTH_BASE_URL}/auth/logout")
    COMMON_AUTH_BASE_URL = (_target_get("COMMON_AUTH_BASE_URL", AUTH_BASE_URL) or AUTH_BASE_URL).rstrip("/")
    COMMON_AUTH_CLIENT_ID = _target_get("COMMON_AUTH_CLIENT_ID", "billaware")
    COMMON_AUTH_CLIENT_SECRET = _target_get(
        "COMMON_AUTH_CLIENT_SECRET",
        os.getenv("BILLAWARE_CLIENT_SECRET", ""),
    )
    COMMON_AUTH_REDIRECT_URI = _target_get("COMMON_AUTH_REDIRECT_URI", "")
    COMMONAUTH_API_BASE_URL = (_target_get(
        "COMMONAUTH_API_BASE_URL",
        f"{AUTH_BASE_URL}/api/v1",
    ) or f"{AUTH_BASE_URL}/api/v1").rstrip("/")
    COMMONAUTH_TIMEOUT_SECONDS = float(_target_get("COMMONAUTH_TIMEOUT_SECONDS", "10"))
    COMMON_AUTH_TIMEOUT_SECONDS = float(_target_get("COMMON_AUTH_TIMEOUT_SECONDS", str(COMMONAUTH_TIMEOUT_SECONDS)))
    COMMON_AUTH_SYNC_EMAIL = (_target_get("COMMON_AUTH_SYNC_EMAIL", "") or "").strip().lower()
    COMMON_AUTH_SYNC_PASSWORD = (_target_get("COMMON_AUTH_SYNC_PASSWORD", "") or "").strip()
    COMMON_AUTH_PUSH_SYNC_SECRET = (_target_get("COMMON_AUTH_PUSH_SYNC_SECRET", "") or "").strip()
    APP_BASE_URL = _target_get("APP_BASE_URL", "")
    AUTH_CALLBACK_PATH = _target_get("AUTH_CALLBACK_PATH", "/auth/callback")

    # ---- APP NAME ----
    APP_NAME = os.environ.get("APP_NAME", "App")
    APP_HOST = _target_get("APP_HOST", os.getenv("APP_HOST", "127.0.0.1"))
    APP_PORT = int(_target_get("APP_PORT", os.getenv("APP_PORT", "9000")))


    # ---- DATE LIMITS ----
    MAX_BACKDATE_DAYS = int(_target_get("MAX_BACKDATE_DAYS", os.environ.get("MAX_BACKDATE_DAYS", "30")))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    return ProductionConfig if env == "production" else DevelopmentConfig
