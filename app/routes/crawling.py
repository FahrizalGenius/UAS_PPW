"""Web Crawling Route."""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.extensions import db
from app.models import CrawlSession, CrawlLog, Link
from app.services.crawling_service import CrawlingService

crawling_bp = Blueprint("crawling", __name__)

@crawling_bp.route("/crawling", methods=["GET"])
def index():
    """Render Web Crawling interface, session metrics, logs, and history."""
    selected_session_id = request.args.get("session_id", type=int)

    sessions = CrawlSession.query.order_by(CrawlSession.id.desc()).limit(15).all()

    if selected_session_id:
        active_session = db.session.get(CrawlSession, selected_session_id)
    else:
        active_session = sessions[0] if sessions else None

    logs = []
    total_links_count = 0
    if active_session:
        logs = (
            CrawlLog.query.filter_by(session_id=active_session.id)
            .order_by(CrawlLog.id.desc())
            .limit(100)
            .all()
        )
        total_links_count = Link.query.filter_by(session_id=active_session.id).count()

    return render_template(
        "crawling.html",
        sessions=sessions,
        active_session=active_session,
        logs=logs,
        total_links_count=total_links_count
    )

@crawling_bp.route("/crawling/start", methods=["POST"])
def start_crawl():
    """
    Initiate web crawling session using BFS Crawler Engine.
    Executes crawling, logs process, and stores results to MySQL.
    """
    start_url = request.form.get("start_url", "").strip()
    max_pages_raw = request.form.get("max_pages", "300").strip()

    try:
        max_pages = int(max_pages_raw)
    except ValueError:
        flash("Jumlah maksimal halaman harus berupa angka bulat positif.", "danger")
        return redirect(url_for("crawling.index"))

    # Execute BFS crawling via CrawlingService
    success, session, message = CrawlingService.start_crawl_session(
        start_url=start_url,
        max_pages=max_pages
    )

    if success and session:
        flash(
            f"Sesi crawling #{session.id} selesai! Berhasil di-crawl: {session.total_crawled} halaman, "
            f"Gagal: {session.total_failed}, Total URL unik ditemukan: {session.total_discovered}.",
            "success"
        )
        return redirect(url_for("crawling.index", session_id=session.id))
    else:
        flash(f"Gagal menjalankan crawling: {message}", "danger")
        if session:
            return redirect(url_for("crawling.index", session_id=session.id))
        return redirect(url_for("crawling.index"))
