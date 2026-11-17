"""Data Website (Pages) Route."""
from flask import Blueprint, render_template, request
from app.models import Page, CrawlSession

pages_bp = Blueprint("pages", __name__)

@pages_bp.route("/pages")
def index():
    """Display crawled web pages with search, filtering, and pagination."""
    page_num = request.args.get("page", 1, type=int)
    search_query = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()
    session_id = request.args.get("session_id", type=int)

    query = Page.query

    if session_id:
        query = query.filter(Page.session_id == session_id)

    if status_filter:
        query = query.filter(Page.crawl_status == status_filter)

    if search_query:
        like_pattern = f"%{search_query}%"
        query = query.filter(
            (Page.url.ilike(like_pattern)) |
            (Page.domain.ilike(like_pattern)) |
            (Page.title.ilike(like_pattern))
        )

    # Order by depth asc, id desc
    query = query.order_by(Page.depth.asc(), Page.id.desc())

    # Paginate results (25 per page)
    pagination = query.paginate(page=page_num, per_page=25, error_out=False)
    pages = pagination.items

    # Available sessions for filtering
    sessions = CrawlSession.query.order_by(CrawlSession.id.desc()).all()

    return render_template(
        "pages.html",
        pages=pages,
        pagination=pagination,
        search_query=search_query,
        status_filter=status_filter,
        session_id=session_id,
        sessions=sessions
    )
