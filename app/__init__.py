import os
from flask import Flask
from config import config_by_name
from app.extensions import db

def create_app(config_name=None):
    """Application factory for Flask app."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Initialize extensions
    db.init_app(app)

    # Register blueprints (to be added as routes are created)
    # from app.routes.dashboard import dashboard_bp
    # app.register_blueprint(dashboard_bp)

    return app
