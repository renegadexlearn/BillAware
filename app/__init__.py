# app/__init__.py
from flask import Flask
from dotenv import load_dotenv
import os

load_dotenv()

from .extensions import db, migrate
from .config import get_config



def create_app():
    

    app = Flask(__name__)

    # 🔧 Load full config (includes SQLALCHEMY_DATABASE_URI, mail, etc.)
    app.config.from_object(get_config())

    @app.context_processor
    def inject_app_branding():
        return {
            "APP_NAME": app.config.get("APP_NAME", "App")
        }

    # Jinja filters
    from .utils.time import format_date_ph
    app.jinja_env.filters["date_ph"] = format_date_ph


    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # ✅ Ensure models are imported so SQLAlchemy knows about them
    from . import models  # app/models/__init__.py 

    from app.routes.api import bp as api_bp
    from app.routes.api_auth import bp as api_auth_bp
    from app.routes.web import bp as web_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(web_bp)

    
    return app
