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

    # Register blueprints
    from app.routes.dashboard import dashboard_bp
    from app.routes.crawling import crawling_bp
    from app.routes.pages import pages_bp
    from app.routes.graph import graph_bp
    from app.routes.pagerank import pagerank_bp
    from app.routes.analysis import analysis_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(crawling_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(graph_bp)
    app.register_blueprint(pagerank_bp)
    app.register_blueprint(analysis_bp)

    return app
