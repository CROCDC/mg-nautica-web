import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

db: SQLAlchemy = SQLAlchemy()
migrate: Migrate = Migrate()
login_manager: LoginManager = LoginManager()


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL", "sqlite:///app.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["UPLOAD_FOLDER"] = os.environ.get("UPLOAD_FOLDER", "./uploads")
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("MAX_CONTENT_LENGTH", str(500 * 1024 * 1024))
    )

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "admin.login"
    login_manager.login_message = "Iniciá sesión para continuar."
    login_manager.login_message_category = "error"

    @login_manager.user_loader
    def _load_user(user_id: str):
        from app.models import User

        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        return {
            "current_year": datetime.utcnow().year,
            "boat_type_label": {
                "sailboat": "Velero",
                "motorboat": "Lancha a motor",
                "cruiser": "Crucero",
                "catamaran": "Catamarán",
                "yacht": "Yate",
                "whaler": "Ballenera",
                "other": "Otro",
            },
            "flag_label": {
                "AR": "Argentina",
                "UY": "Uruguay",
                "FOREIGN": "Exterior",
            },
            "hull_material_label": {
                "fiberglass": "PRFV",
                "wood": "Madera",
                "ferrocement": "Ferrocemento",
                "aluminum": "Aluminio",
                "steel": "Acero",
                "other": "Otro",
            },
            "accessory_category_label": {
                "onboard": "Accesorios a bordo",
                "boots": "Botas náuticas",
                "clothing": "Ropa náutica",
                "other": "Otros",
            },
            "condition_label": {
                "new": "Nuevo",
                "used": "Usado",
            },
            "sort_label": {
                "recent": "Más recientes",
                "price_asc": "Precio: menor a mayor",
                "price_desc": "Precio: mayor a menor",
                "oldest": "Más antiguos primero",
            },
            "status_label": {
                "available": "Disponible",
                "reserved": "Reservado",
                "sold": "Vendido",
            },
        }

    with app.app_context():
        # Import models so SQLAlchemy metadata picks them up for migrations.
        from app import models  # noqa: F401
        from app.admin import admin_bp
        from app.routes import register_routes

        register_routes(app)
        app.register_blueprint(admin_bp, url_prefix="/admin")
        db.create_all()

        from app.integrations.mercadolibre.auth import MeliOAuth
        MeliOAuth.seed_from_env()

    return app
