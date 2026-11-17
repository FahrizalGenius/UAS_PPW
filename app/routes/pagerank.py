"""PageRank Analysis and Top 10 Ranking Routes."""
import csv
from io import StringIO
from flask import Blueprint, render_template, request, flash, redirect, url_for, Response
from app.extensions import db
from app.models import PageRankResult, Page, CrawlSession
from app.graph.graph_builder import GraphBuilder
from app.graph.pagerank import compute_pagerank, store_pagerank_results, export_pagerank_to_dict

pagerank_bp = Blueprint("pagerank", __name__)


@pagerank_bp.route("/pagerank")
def index():
    """Render PageRank calculation configuration and results."""
    session_id = request.args.get("session_id", type=int)
    all_sessions = CrawlSession.query.order_by(CrawlSession.id.desc()).all()

    selected_session = None
    if session_id:
        selected_session = CrawlSession.query.get(session_id)
        if not selected_session:
            flash(f"Sesi crawling dengan ID #{session_id} tidak ditemukan.", "warning")

    if not selected_session:
        selected_session = all_sessions[0] if all_sessions else None

    # Query pagerank results with page details
    results = []
    if selected_session:
        results = (
            db.session.query(PageRankResult, Page)
            .join(Page, PageRankResult.page_id == Page.id)
            .filter(PageRankResult.session_id == selected_session.id)
            .order_by(PageRankResult.ranking_position.asc())
            .all()
        )

    return render_template(
        "pagerank.html",
        results=results,
        selected_session=selected_session,
        latest_session=selected_session,
        all_sessions=all_sessions,
    )


@pagerank_bp.route("/pagerank/calculate", methods=["POST"])
def calculate():
    """Handle PageRank calculation request.

    Validates parameters, builds the graph for the selected crawl session,
    computes PageRank, stores the results, and redirects back to the index page.
    """
    session_id = request.form.get("session_id", type=int)

    session = None
    if session_id:
        session = CrawlSession.query.get(session_id)

    if not session:
        session = CrawlSession.query.order_by(CrawlSession.id.desc()).first()

    if not session:
        flash("Tidak ada sesi crawling yang tersedia untuk menghitung PageRank.", "warning")
        return redirect(url_for("pagerank.index"))

    # Retrieve parameters from the form, falling back to defaults.
    try:
        damping = float(request.form.get("damping_factor", "0.85"))
        max_iter = int(request.form.get("max_iterations", "100"))
        tolerance = float(request.form.get("tolerance", "0.000001"))
    except ValueError:
        flash("Parameter PageRank tidak valid.", "danger")
        return redirect(url_for("pagerank.index", session_id=session.id))

    # Build graph for the selected session.
    graph = GraphBuilder.build_from_session(session.id)
    if graph.number_of_nodes() == 0:
        flash("Graf kosong – tidak ada halaman yang berhasil di-crawl untuk sesi ini.", "warning")
        return redirect(url_for("pagerank.index", session_id=session.id))

    # Compute PageRank using the utility.
    scores, iterations, converged, error = compute_pagerank(
        graph,
        damping_factor=damping,
        max_iterations=max_iter,
        tolerance=tolerance,
    )

    # Store results atomically.
    store_pagerank_results(session.id, scores, damping_factor=damping, iterations=iterations)

    # Prepare feedback message.
    if converged:
        flash_msg = (
            f"PageRank berhasil dihitung untuk Sesi #{session.id} (iterasi={iterations}, konvergen={converged}, "
            f"error={error:.2e})."
        )
    else:
        flash_msg = (
            f"PageRank selesai untuk Sesi #{session.id} setelah {iterations} iterasi tetapi belum konvergen "
            f"(error={error:.2e})."
        )
    flash(flash_msg, "info")
    return redirect(url_for("pagerank.index", session_id=session.id))


@pagerank_bp.route("/pagerank/top10")
def top10():
    """Display Top 10 web pages ranked by PageRank score."""
    session_id = request.args.get("session_id", type=int)
    all_sessions = CrawlSession.query.order_by(CrawlSession.id.desc()).all()

    selected_session = None
    if session_id:
        selected_session = CrawlSession.query.get(session_id)
        if not selected_session:
            flash(f"Sesi crawling dengan ID #{session_id} tidak ditemukan.", "warning")

    if not selected_session:
        selected_session = all_sessions[0] if all_sessions else None

    top_10_results = []
    if selected_session:
        top_10_results = (
            db.session.query(PageRankResult, Page)
            .join(Page, PageRankResult.page_id == Page.id)
            .filter(PageRankResult.session_id == selected_session.id)
            .order_by(PageRankResult.ranking_position.asc())
            .limit(10)
            .all()
        )

    return render_template(
        "top10.html",
        top_10=top_10_results,
        selected_session=selected_session,
        latest_session=selected_session,
        all_sessions=all_sessions,
    )


@pagerank_bp.route("/pagerank/download")
def download_all():
    """Download PageRank results as CSV for a specific session."""
    session_id = request.args.get("session_id", type=int)
    if not session_id:
        latest = CrawlSession.query.order_by(CrawlSession.id.desc()).first()
        session_id = latest.id if latest else None

    if not session_id:
        flash("Tidak ada data untuk diunduh.", "warning")
        return redirect(url_for("pagerank.index"))

    rows = export_pagerank_to_dict(session_id)
    if not rows:
        flash(f"Tidak ada data PageRank untuk Sesi #{session_id}.", "warning")
        return redirect(url_for("pagerank.index", session_id=session_id))

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ranking_position", "page_id", "url", "domain", 
        "pagerank_score", "damping_factor", "iterations", "calculated_at"
    ])
    for r in rows:
        writer.writerow([
            r.get("ranking_position"),
            r.get("page_id"),
            r.get("url"),
            r.get("domain"),
            f"{r.get('pagerank_score', 0):.8f}",
            r.get("damping_factor"),
            r.get("iterations"),
            r.get("calculated_at"),
        ])

    csv_data = output.getvalue()
    filename = f"pagerank_session_{session_id}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@pagerank_bp.route("/pagerank/download/top10")
def download_top10():
    """Download Top 10 PageRank results as CSV for a specific session."""
    session_id = request.args.get("session_id", type=int)
    if not session_id:
        latest = CrawlSession.query.order_by(CrawlSession.id.desc()).first()
        session_id = latest.id if latest else None

    if not session_id:
        flash("Tidak ada data untuk diunduh.", "warning")
        return redirect(url_for("pagerank.top10"))

    rows = export_pagerank_to_dict(session_id)
    if not rows:
        flash(f"Tidak ada data PageRank untuk Sesi #{session_id}.", "warning")
        return redirect(url_for("pagerank.top10", session_id=session_id))

    top10_rows = rows[:10]

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["ranking_position", "page_id", "url", "domain", "pagerank_score"])
    for r in top10_rows:
        writer.writerow([
            r.get("ranking_position"),
            r.get("page_id"),
            r.get("url"),
            r.get("domain"),
            f"{r.get('pagerank_score', 0):.8f}"
        ])

    csv_data = output.getvalue()
    filename = f"pagerank_top10_session_{session_id}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
