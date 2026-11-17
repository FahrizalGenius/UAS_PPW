"""Routes package initialization and blueprint registry."""
from app.routes.dashboard import dashboard_bp
from app.routes.crawling import crawling_bp
from app.routes.pages import pages_bp
from app.routes.graph import graph_bp
from app.routes.pagerank import pagerank_bp
from app.routes.analysis import analysis_bp

__all__ = [
    "dashboard_bp",
    "crawling_bp",
    "pages_bp",
    "graph_bp",
    "pagerank_bp",
    "analysis_bp",
]
