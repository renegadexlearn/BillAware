# app/config.py
import os
from urllib.parse import quote_plus


def apply_environment_profile():
    profile = os.getenv("BILLAWARE_ENV", "dev").strip().lower() or "dev"
    if profile not in {"dev", "demo", "live"}:
        profile = "dev"
    os.environ["BILLAWARE_ENV"] = profile

    prefix = f"{profile.upper()}_"
    for key, value in list(os.environ.items()):
        if key.startswith(prefix):
            os.environ[key[len(prefix) :]] = value


apply_environment_profile()


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ---- DATABASE ----
    DB_USER = os.environ["DB_USER"]
    DB_PASSWORD_RAW = os.environ["DB_PASSWORD"]
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "3306")
    DB_NAME = os.environ["DB_NAME"]
    DB_PASSWORD = quote_plus(DB_PASSWORD_RAW)

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:"
        f"{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )

    # ---- JWT ----
    JWT_ISSUER = os.getenv("JWT_ISSUER", "https://auth.ianeer.com")
    JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "billaware")
    JWT_PUBLIC_KEY_PATH = os.getenv("JWT_PUBLIC_KEY_PATH", "./jwt_public.pem")

    # ---- AUTH ----
    AUTH_BASE_URL = os.getenv("AUTH_BASE_URL", "https://auth.ianeer.com").rstrip("/")
    AUTH_LOGIN_URL = os.getenv("AUTH_LOGIN_URL", f"{AUTH_BASE_URL}/auth")
    AUTH_LOGOUT_URL = os.getenv("AUTH_LOGOUT_URL", f"{AUTH_BASE_URL}/auth/logout")
    APP_BASE_URL = os.getenv("APP_BASE_URL", "")
    AUTH_CALLBACK_PATH = os.getenv("AUTH_CALLBACK_PATH", "/auth/callback")

    # ---- APP NAME ----
    APP_NAME = os.environ.get("APP_NAME", "App")
    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.getenv("APP_PORT", "9000"))


    # ---- DATE LIMITS ----
    MAX_BACKDATE_DAYS = int(os.environ.get("MAX_BACKDATE_DAYS", 30))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False


def get_config():
    env = os.environ.get("FLASK_ENV", "development").lower()
    profile = os.environ.get("BILLAWARE_ENV", "dev").lower()
    return ProductionConfig if env == "production" or profile in {"demo", "live"} else DevelopmentConfig
