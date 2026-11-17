"""Graph Analysis and Download Results Routes."""
import networkx as nx
from flask import Blueprint, render_template, request
from app.models import Page, Link, PageRankResult, CrawlSession
from app.graph.graph_builder import GraphBuilder
from app.graph.graph_analysis import GraphAnalysis

analysis_bp = Blueprint("analysis", __name__)


@analysis_bp.route("/analysis/graph")
def graph_analysis():
    """Render Graph Analysis metrics and structural properties for a selected session.

    Query parameter ``session_id`` (int) selects the crawling session to analyse.
    If omitted, the most recent session is used.
    """
    # Determine session
    session_id = request.args.get("session_id", type=int)
    if session_id is None:
        latest_session = CrawlSession.query.order_by(CrawlSession.id.desc()).first()
        if not latest_session:
            # No sessions at all – render empty state
            return render_template("analysis.html", latest_session=None)
        session_id = latest_session.id
    else:
        latest_session = CrawlSession.query.get(session_id)
        if not latest_session:
            # Invalid session – fallback to latest
            latest_session = CrawlSession.query.order_by(CrawlSession.id.desc()).first()
            session_id = latest_session.id if latest_session else None

    # Build graph for the chosen session using existing GraphBuilder
    graph = GraphBuilder.build_from_session(session_id) if session_id else nx.DiGraph()

    # Analyse graph using GraphAnalysis utility
    analysis_data = GraphAnalysis.analyze(graph)

    # Prepare list of all sessions for the dropdown
    all_sessions = CrawlSession.query.order_by(CrawlSession.id.desc()).all()

    return render_template(
        "analysis.html",
        latest_session=latest_session,
        all_sessions=all_sessions,
        analysis=analysis_data,
    )


@analysis_bp.route("/downloads")
@analysis_bp.route("/analysis/downloads")
def downloads():
    """Render export and download center for CSV reports."""
    total_pages = Page.query.count()
    total_pagerank = PageRankResult.query.count()
    total_links = Link.query.filter(Link.target_page_id.isnot(None)).count()

    return render_template(
        "downloads.html",
        total_pages=total_pages,
        total_pagerank=total_pagerank,
        total_links=total_links
    )
