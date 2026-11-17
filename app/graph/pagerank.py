"""PageRank calculation utilities.

Provides ``compute_pagerank`` which calculates PageRank scores for a directed
NetworkX graph using the standard power‑iteration method. The function mirrors the
parameters of :func:`networkx.pagerank` so that the behaviour is identical to the
well‑tested NetworkX implementation while allowing us to capture iteration
information for UI display.
"""

import logging
from typing import Dict, Tuple, Any

import networkx as nx

logger = logging.getLogger(__name__)


def compute_pagerank(
    graph: nx.DiGraph,
    damping_factor: float = 0.85,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> Tuple[Dict[int, float], int, bool, float]:
    """Calculate PageRank for ``graph``.

    Parameters
    ----------
    graph:
        Directed graph built from the crawl session. Node identifiers are the
        ``page.id`` values (integers).
    damping_factor:
        Probability of following an outgoing link (``d`` in the classic formula).
    max_iterations:
        Upper bound on the number of power‑iteration steps.
    tolerance:
        Convergence threshold – the L1 norm of the difference between two
        successive rank vectors.

    Returns
    -------
    scores:
        Mapping ``node_id -> pagerank_score``. The scores sum to ~1.0.
    iterations:
        Number of iterations actually performed.
    converged:
        ``True`` if the process converged before reaching ``max_iterations``.
    error:
        Final L1 error (``sum(|rank_new - rank_old|)``). Zero when converged.
    """
    if graph.number_of_nodes() == 0:
        logger.info("Empty graph supplied to PageRank – returning empty result.")
        return {}, 0, True, 0.0

    # NetworkX's pagerank implementation already does the heavy lifting and
    # returns a dictionary of scores. However it does not expose the iteration
    # count or convergence flag directly. We therefore implement a lightweight
    # power‑iteration loop that mirrors the algorithm.
    N = graph.number_of_nodes()
    if N == 1:
        # Single node – rank is 1.0 (or 0.0 if we follow the default formula).
        node = next(iter(graph.nodes()))
        return {node: 1.0}, 0, True, 0.0

    # Initialise rank vector uniformly.
    rank: Dict[int, float] = {n: 1.0 / N for n in graph.nodes()}
    # Pre‑compute out‑degree for dangling node handling.
    out_degree = {n: graph.out_degree(n) for n in graph.nodes()}
    dangling_nodes = [n for n, d in out_degree.items() if d == 0]

    converged = False
    iteration = 0
    error = float('inf')
    teleport = (1.0 - damping_factor) / N

    while iteration < max_iterations and not converged:
        rank_new: Dict[int, float] = {n: teleport for n in graph.nodes()}
        # Distribute rank from each node to its outgoing neighbours.
        for node in graph.nodes():
            if out_degree[node] == 0:
                # Dangling node contributes its rank to all nodes equally.
                contribution = damping_factor * rank[node] / N
                for n in graph.nodes():
                    rank_new[n] += contribution
            else:
                contribution = damping_factor * rank[node] / out_degree[node]
                for succ in graph.successors(node):
                    rank_new[succ] += contribution
        # Compute L1 difference.
        error = sum(abs(rank_new[n] - rank[n]) for n in graph.nodes())
        converged = error < tolerance
        rank = rank_new
        iteration += 1

    # Normalise to ensure sum~=1 (floating point drift may occur).
    total = sum(rank.values())
    if total > 0:
        rank = {n: v / total for n, v in rank.items()}

    logger.info(
        f"PageRank computed: nodes={N}, iterations={iteration}, converged={converged}, error={error:.2e}"
    )
    return rank, iteration, converged, error

"""Utility for persisting PageRank results.

The ``store_pagerank_results`` function writes the calculated scores to the
``pagerank_results`` table. It replaces any existing results for the same session
inside a single transaction to guarantee atomicity.
"""

from app.extensions import db
from app.models import PageRankResult, Page
from datetime import datetime


def store_pagerank_results(
    session_id: int,
    scores: Dict[int, float],
    damping_factor: float,
    iterations: int,
) -> None:
    """Persist PageRank scores for a crawl ``session_id``.

    The function first deletes any existing ``PageRankResult`` rows for the given
    ``session_id`` and then inserts the new results ordered by descending score.
    Ranking positions start at 1.
    """
    # Atomic transaction
    try:
        # Remove old results for this session.
        db.session.query(PageRankResult).filter_by(session_id=session_id).delete()

        # Order pages by score descending.
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        for rank_pos, (page_id, score) in enumerate(ordered, start=1):
            pr = PageRankResult(
                session_id=session_id,
                page_id=page_id,
                pagerank_score=score,
                ranking_position=rank_pos,
                damping_factor=damping_factor,
                iterations=iterations,
                calculated_at=datetime.utcnow(),
            )
            db.session.add(pr)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"Failed to store PageRank results for session #{session_id}: {exc}")
        raise

"""Export helpers used by the download endpoints.

These helpers are deliberately simple – they return a list of dictionaries that
can be fed directly to ``pandas.DataFrame`` for CSV generation.
"""

def export_pagerank_to_dict(session_id: int) -> list:
    """Return PageRank rows for ``session_id`` as plain dictionaries.
    """
    results = (
        db.session.query(PageRankResult, Page)
        .join(Page, PageRankResult.page_id == Page.id)
        .filter(PageRankResult.session_id == session_id)
        .order_by(PageRankResult.ranking_position.asc())
        .all()
    )
    return [
        {
            "ranking_position": pr.ranking_position,
            "page_id": pr.page_id,
            "url": pg.url,
            "domain": pg.domain,
            "pagerank_score": pr.pagerank_score,
            "damping_factor": pr.damping_factor,
            "iterations": pr.iterations,
            "calculated_at": pr.calculated_at.isoformat() if pr.calculated_at else None,
        }
        for pr, pg in results
    ]
