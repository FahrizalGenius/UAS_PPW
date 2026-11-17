"""Graph Visualization, Adjacency Matrix, and CSV Export Routes."""
import json
from flask import Blueprint, render_template, request, flash, redirect, url_for, Response
from app.extensions import db
from app.models import CrawlSession, Page
from app.graph import GraphBuilder, AdjacencyMatrixBuilder, GraphVisualizer

graph_bp = Blueprint("graph", __name__)

@graph_bp.route("/graph")
def index():
    """Render interactive directed graph visualization with session selector."""
    session_id = request.args.get("session_id", type=int)

    # Fetch available sessions from MySQL
    sessions = CrawlSession.query.order_by(CrawlSession.id.desc()).all()

    # Determine active session
    active_session = None
    if session_id:
        active_session = db.session.get(CrawlSession, session_id)
        if not active_session:
            flash(f"Sesi #{session_id} tidak ditemukan.", "warning")
    elif sessions:
        # Default to latest session
        active_session = sessions[0]

    # Build directed graph and compute statistics
    graph = GraphBuilder.build_from_session(active_session.id if active_session else None)
    stats = GraphBuilder.get_graph_statistics(graph)
    vis_data = GraphVisualizer.get_vis_network_data(graph)

    # Check if session has 0 successful pages
    no_pages = False
    if active_session:
        success_count = Page.query.filter_by(session_id=active_session.id, crawl_status="success").count()
        if success_count == 0:
            no_pages = True

    return render_template(
        "graph.html",
        sessions=sessions,
        active_session=active_session,
        stats=stats,
        vis_data_json=json.dumps(vis_data),
        no_pages=no_pages
    )

@graph_bp.route("/graph/adjacency-matrix")
def matrix():
    """Render Adjacency Matrix with pagination and session selector."""
    session_id = request.args.get("session_id", type=int)
    page_num = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    sessions = CrawlSession.query.order_by(CrawlSession.id.desc()).all()

    active_session = None
    if session_id:
        active_session = db.session.get(CrawlSession, session_id)
        if not active_session:
            flash(f"Sesi #{session_id} tidak ditemukan.", "warning")
    elif sessions:
        active_session = sessions[0]

    graph = GraphBuilder.build_from_session(active_session.id if active_session else None)
    stats = GraphBuilder.get_graph_statistics(graph)

    matrix, node_mapping, _ = AdjacencyMatrixBuilder.build_matrix(graph)
    preview = AdjacencyMatrixBuilder.get_matrix_preview(matrix, node_mapping, page=page_num, per_page=per_page)

    return render_template(
        "adjacency_matrix.html",
        sessions=sessions,
        active_session=active_session,
        stats=stats,
        preview=preview,
        node_mapping=node_mapping,
        per_page=per_page
    )

@graph_bp.route("/graph/adjacency-matrix/export")
def export_matrix():
    """Export complete N x N adjacency matrix as a downloadable CSV file."""
    session_id = request.args.get("session_id", type=int)
    if not session_id:
        flash("Parameter session_id wajib disertakan untuk ekspor.", "warning")
        return redirect(url_for("graph.matrix"))

    session = db.session.get(CrawlSession, session_id)
    if not session:
        flash(f"Sesi #{session_id} tidak ditemukan.", "danger")
        return redirect(url_for("graph.matrix"))

    graph = GraphBuilder.build_from_session(session_id)
    if graph.number_of_nodes() == 0:
        flash(f"Sesi #{session_id} tidak memiliki node untuk diekspor ke matriks.", "warning")
        return redirect(url_for("graph.matrix", session_id=session_id))

    matrix, node_mapping, _ = AdjacencyMatrixBuilder.build_matrix(graph)
    csv_stream = AdjacencyMatrixBuilder.export_csv_stream(matrix, node_mapping)

    filename = f"adjacency_matrix_session_{session_id}.csv"
    return Response(
        csv_stream.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
