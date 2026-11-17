"""Graph analysis utilities for directed web‑crawling graphs.

Provides:
- Degree distributions (in, out, total) with counts and percentages.
- Clustering coefficient per node and average.
- Average shortest path length calculated on the largest strongly connected component.
- Per‑node metric table (page id, url, domain, degrees, clustering).

All functions accept a :class:`networkx.DiGraph` that has been built by
:class:`app.graph.graph_builder.GraphBuilder`. No database queries are performed
here – the graph object already contains the required node attributes.
"""

import logging
from typing import Dict, List, Tuple, Any

import networkx as nx

logger = logging.getLogger(__name__)

# Import GraphBuilder for basic stats
from app.graph.graph_builder import GraphBuilder


class GraphAnalysis:
    """Utility class that extracts structural metrics from a directed graph.

    The class is deliberately stateless – each public method receives a ``graph``
    argument and returns plain Python data structures that can be JSON‑encoded
    and fed directly to Jinja templates.
    """

    @staticmethod
    def degree_distribution(graph: nx.DiGraph) -> Dict[str, List[Dict[str, Any]]]:
        """Return in‑, out‑ and total‑degree distributions.

        The return value is a mapping with three keys (``in``, ``out``, ``total``).
        Each value is a list of dictionaries:

        ``{"degree": int, "frequency": int, "percentage": float}``

        ``percentage`` is rounded to two decimal places and represents the share
        of nodes that have the corresponding degree.
        """
        if graph.number_of_nodes() == 0:
            empty = [{"degree": 0, "frequency": 0, "percentage": 0.0}]
            return {"in": empty, "out": empty, "total": empty}

        in_deg = dict(graph.in_degree())
        out_deg = dict(graph.out_degree())
        total_deg = {n: in_deg[n] + out_deg[n] for n in graph.nodes()}

        def _distribution(counter: Dict[int, int]) -> List[Dict[str, Any]]:
            total_nodes = len(counter)
            dist: Dict[int, int] = {}
            for d in counter.values():
                dist[d] = dist.get(d, 0) + 1
            result = []
            for degree, freq in sorted(dist.items()):
                pct = round(freq / total_nodes * 100, 2) if total_nodes else 0.0
                result.append({"degree": degree, "frequency": freq, "percentage": pct})
            return result

        return {
            "in": _distribution(in_deg),
            "out": _distribution(out_deg),
            "total": _distribution(total_deg),
        }

    @staticmethod
    def clustering_coefficients(graph: nx.DiGraph) -> Tuple[Dict[int, float], float]:
        """Calculate clustering coefficient for each node and the average.

        NetworkX implements directed clustering exactly as required. The method
        returns a tuple ``(per_node, average)`` where ``per_node`` maps node id to
        its coefficient (rounded to four decimals) and ``average`` is the mean of
        all coefficients (also rounded).
        """
        if graph.number_of_nodes() == 0:
            return ({}, 0.0)
        # nx.clustering works with DiGraph and returns a dict {node: coeff}
        raw = nx.clustering(graph)
        per_node = {n: round(c, 4) for n, c in raw.items()}
        avg = round(sum(per_node.values()) / len(per_node), 4) if per_node else 0.0
        return per_node, avg

    @staticmethod
    def average_shortest_path_length_largest_scc(graph: nx.DiGraph) -> Dict[str, Any]:
        """Average shortest path length on the largest strongly connected component.

        Returns a dictionary with the following keys:
        - ``is_strongly_connected`` (bool)
        - ``largest_scc_size`` (int)
        - ``largest_scc_percentage`` (float, rounded to two decimals)
        - ``average_path_length`` (float or ``None`` when not applicable)
        """
        if graph.number_of_nodes() == 0:
            return {
                "is_strongly_connected": False,
                "largest_scc_size": 0,
                "largest_scc_percentage": 0.0,
                "average_path_length": None,
            }

        sccs = list(nx.strongly_connected_components(graph))
        is_sc = nx.is_strongly_connected(graph)
        if not sccs:
            return {
                "is_strongly_connected": is_sc,
                "largest_scc_size": 0,
                "largest_scc_percentage": 0.0,
                "average_path_length": None,
            }
        # Identify the largest component
        largest_scc = max(sccs, key=len)
        largest_size = len(largest_scc)
        total_nodes = graph.number_of_nodes()
        pct = round(largest_size / total_nodes * 100, 2) if total_nodes else 0.0

        if largest_size <= 1:
            avg_len = None
        else:
            subgraph = graph.subgraph(largest_scc).copy()
            try:
                avg_len = round(nx.average_shortest_path_length(subgraph), 4)
            except Exception as e:
                logger.warning(f"Failed to compute avg shortest path: {e}")
                avg_len = None

        return {
            "is_strongly_connected": is_sc,
            "largest_scc_size": largest_size,
            "largest_scc_percentage": pct,
            "average_path_length": avg_len,
        }

    @staticmethod
    def per_node_metrics(graph: nx.DiGraph) -> List[Dict[str, Any]]:
        """Generate a list of per‑node statistics.

        Each entry contains:
        - ``page_id`` (node id)
        - ``url``
        - ``domain``
        - ``in_degree``
        - ``out_degree``
        - ``total_degree``
        - ``clustering_coeff`` (rounded to 4 decimals)
        """
        if graph.number_of_nodes() == 0:
            return []
        # Pre‑compute clustering once for efficiency
        clustering_dict, _ = GraphAnalysis.clustering_coefficients(graph)
        in_deg = dict(graph.in_degree())
        out_deg = dict(graph.out_degree())
        rows = []
        for node in graph.nodes(data=True):
            nid, attrs = node
            rows.append({
                "page_id": nid,
                "url": attrs.get("url", ""),
                "domain": attrs.get("domain", ""),
                "in_degree": in_deg.get(nid, 0),
                "out_degree": out_deg.get(nid, 0),
                "total_degree": in_deg.get(nid, 0) + out_deg.get(nid, 0),
                "clustering_coeff": clustering_dict.get(nid, 0.0),
            })
        return rows

    @staticmethod
    def analyze(graph: nx.DiGraph) -> Dict[str, Any]:
        """Convenience wrapper returning all metrics needed by the UI.
        """
        stats = GraphBuilder.get_graph_statistics(graph)  # reuse existing basic stats
        degree_dist = GraphAnalysis.degree_distribution(graph)
        per_node_clust, avg_clust = GraphAnalysis.clustering_coefficients(graph)
        scc_info = GraphAnalysis.average_shortest_path_length_largest_scc(graph)
        node_table = GraphAnalysis.per_node_metrics(graph)

        return {
            "basic_stats": stats,
            "degree_distribution": degree_dist,
            "clustering": {
                "per_node": per_node_clust,
                "average": avg_clust,
            },
            "scc": scc_info,
            "node_table": node_table,
        }
