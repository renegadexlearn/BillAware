# app/__init__.py
from dotenv import load_dotenv
from flask import Flask
import click

load_dotenv()

from .config import get_config
from .extensions import db, login_manager, migrate
from .services.auth_sync import run_commonauth_sync
from .utils.ui_settings import get_ui_settings


def create_app():
    app = Flask(__name__)
    app.config.from_object(get_config())

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in with commonAuth."

    @app.context_processor
    def inject_app_branding():
        ui_settings = get_ui_settings()
        return {
            "APP_NAME": app.config.get("APP_NAME", "App"),
            "app_title": ui_settings.get("app_title", app.config.get("APP_NAME", "App")),
            "ui_settings": ui_settings,
            "AUTH_LOGIN_URL": app.config.get("AUTH_LOGIN_URL", ""),
            "AUTH_LOGOUT_URL": app.config.get("AUTH_LOGOUT_URL", ""),
            "AUTH_CALLBACK_PATH": app.config.get("AUTH_CALLBACK_PATH", "/auth/callback"),
        }

    from .utils.time import format_date_ph, format_datetime_ph, format_ph_value

    app.jinja_env.filters["date_ph"] = format_date_ph
    app.jinja_env.filters["datetime_ph"] = format_datetime_ph
    app.jinja_env.filters["ph_display"] = format_ph_value

    from . import models
    from app.models import UserCache

    @login_manager.user_loader
    def load_user(user_id: str):
        if not str(user_id or "").isdigit():
            return None
        return db.session.get(UserCache, int(user_id))

    from app.routes.auth import auth_bp
    from app.routes.api import bp as api_bp
    from app.routes.api_auth import bp as api_auth_bp
    from app.routes.billing import bp as billing_bp
    from app.routes.web import bp as web_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(web_bp)

    with app.app_context():
        db.create_all()

    @app.cli.command("sync-commonauth")
    @click.option("--full", is_flag=True, default=False, help="Run a full reconciliation sync.")
    def sync_commonauth(full: bool):
        result = run_commonauth_sync(trigger="cli", reason="cli", force_full=full)
        if result is None:
            click.echo("commonAuth sync skipped: another sync run is active")
            return
        click.echo("commonAuth sync complete")
        click.echo(f"main_groups={result.synced.get('main_groups', 0)}")
        click.echo(f"companies={result.synced.get('companies', 0)}")
        click.echo(f"branches={result.synced.get('branches', 0)}")
        click.echo(f"users={result.synced.get('users', 0)}")
        click.echo(f"employees={result.synced.get('employees', 0)}")

    return app
