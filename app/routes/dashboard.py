"""Dashboard Route."""
from flask import Blueprint, render_template
from sqlalchemy import func
from app.extensions import db
from app.models import CrawlSession, Page, Link, PageRankResult

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@dashboard_bp.route("/dashboard")
def index():
    """Render main dashboard with live statistics from MySQL."""
    # Main statistics
    total_sessions = CrawlSession.query.count()
    
    # Total discovered from all sessions or pages table
    sum_discovered = db.session.query(
        func.coalesce(func.sum(CrawlSession.total_discovered), 0)
    ).scalar()
    total_pages_table = Page.query.count()
    total_discovered = max(sum_discovered, total_pages_table)

    total_crawled = Page.query.filter_by(crawl_status="success").count()
    total_failed = Page.query.filter_by(crawl_status="failed").count()
    total_links = Link.query.count()
    total_pagerank = PageRankResult.query.count()

    # Latest session details
    latest_session = CrawlSession.query.order_by(CrawlSession.id.desc()).first()

    # Top 5 PageRank summary (joined with Page)
    top_5_pagerank = []
    if latest_session:
        top_5_pagerank = (
            db.session.query(PageRankResult, Page)
            .join(Page, PageRankResult.page_id == Page.id)
            .filter(PageRankResult.session_id == latest_session.id)
            .order_by(PageRankResult.ranking_position.asc())
            .limit(5)
            .all()
        )
    elif total_pagerank > 0:
        top_5_pagerank = (
            db.session.query(PageRankResult, Page)
            .join(Page, PageRankResult.page_id == Page.id)
            .order_by(PageRankResult.ranking_position.asc())
            .limit(5)
            .all()
        )

    stats = {
        "total_sessions": total_sessions,
        "total_discovered": total_discovered,
        "total_crawled": total_crawled,
        "total_failed": total_failed,
        "total_links": total_links,
        "total_pagerank": total_pagerank,
    }

    return render_template(
        "dashboard.html",
        stats=stats,
        latest_session=latest_session,
        top_5_pagerank=top_5_pagerank
    )
