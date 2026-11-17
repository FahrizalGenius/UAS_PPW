"""Directed Graph Builder from MySQL crawled data using NetworkX."""
import logging
from typing import Dict, Any, Optional
import networkx as nx

from app.models import Page, Link

logger = logging.getLogger(__name__)

class GraphBuilder:
    """Builds and analyzes directed graphs (nx.DiGraph) based on web crawling sessions."""

    @staticmethod
    def build_from_session(session_id: int) -> nx.DiGraph:
        """
        Construct a directed graph (nx.DiGraph) from a crawling session in MySQL.
        
        Node rules:
            - Only pages with crawl_status == 'success' are included as nodes.
            - Node key is page.id (unique primary key, preventing identity collisions).
            - Node attributes: page_id, url, final_url, title, domain, depth, status_code.
            
        Edge rules:
            - Source and target must both be successfully crawled pages in this session.
            - Links with NULL target_page_id are ignored.
            - Links pointing to pages outside the successful node set are ignored.
            - Multi-links between the same page pair become a single directed edge.
            - Isolated nodes (degree 0) are strictly preserved.
            
        Returns:
            nx.DiGraph: Directed graph instance.
        """
        graph = nx.DiGraph()

        if not session_id:
            return graph

        # 1. Fetch all successfully crawled pages for this session
        successful_pages = Page.query.filter_by(
            session_id=session_id,
            crawl_status="success"
        ).all()

        if not successful_pages:
            logger.info(f"Session #{session_id} has no successful pages to build a graph.")
            return graph

        # 2. Add nodes with complete metadata attributes
        for page in successful_pages:
            graph.add_node(
                page.id,
                page_id=page.id,
                url=page.url,
                final_url=page.final_url or page.url,
                title=page.title or "(Tanpa Judul)",
                domain=page.domain,
                depth=page.depth,
                status_code=page.status_code
            )

        valid_node_ids = set(graph.nodes())

        # 3. Fetch all links with valid targets for this session
        links = Link.query.filter(
            Link.session_id == session_id,
            Link.target_page_id.isnot(None)
        ).all()

        # 4. Add directed edges
        for link in links:
            source_id = link.source_page_id
            target_id = link.target_page_id

            # Only add edge if both source and target exist as nodes in the graph
            if source_id in valid_node_ids and target_id in valid_node_ids:
                # In nx.DiGraph, duplicate add_edge calls update edge attributes without duplicating edges
                graph.add_edge(source_id, target_id, anchor_text=link.anchor_text)

        logger.info(
            f"Built directed graph for session #{session_id}: "
            f"{graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges."
        )
        return graph

    @staticmethod
    def get_graph_statistics(graph: nx.DiGraph) -> Dict[str, Any]:
        """
        Calculate fundamental structural metrics for a directed graph.
        
        Directed Graph Degree Definitions:
            - in_degree(v): number of incoming edges to node v.
            - out_degree(v): number of outgoing edges from node v.
            - total_degree(v) = in_degree(v) + out_degree(v).
            - Average degree = sum(total_degree) / N = 2 * E / N.
            
        Returns:
            Dictionary containing node counts, edge counts, degree distributions, and averages.
        """
        total_nodes = graph.number_of_nodes()
        total_edges = graph.number_of_edges()

        if total_nodes == 0:
            return {
                "total_nodes": 0,
                "total_edges": 0,
                "nodes_with_incoming": 0,
                "nodes_with_outgoing": 0,
                "isolated_nodes": 0,
                "in_degree_zero_nodes": 0,
                "out_degree_zero_nodes": 0,
                "avg_in_degree": 0.0,
                "avg_out_degree": 0.0,
                "avg_degree": 0.0,
                "density": 0.0
            }

        in_degrees = dict(graph.in_degree())
        out_degrees = dict(graph.out_degree())
        total_degrees = {n: in_degrees[n] + out_degrees[n] for n in graph.nodes()}

        nodes_with_incoming = sum(1 for d in in_degrees.values() if d > 0)
        nodes_with_outgoing = sum(1 for d in out_degrees.values() if d > 0)
        isolated_nodes = sum(1 for n in graph.nodes() if total_degrees[n] == 0)
        in_degree_zero_nodes = sum(1 for d in in_degrees.values() if d == 0)
        out_degree_zero_nodes = sum(1 for d in out_degrees.values() if d == 0)

        avg_in_degree = total_edges / total_nodes
        avg_out_degree = total_edges / total_nodes
        avg_degree = sum(total_degrees.values()) / total_nodes

        # Density for directed graph: E / (N * (N - 1))
        density = 0.0
        if total_nodes > 1:
            density = total_edges / (total_nodes * (total_nodes - 1))

        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "nodes_with_incoming": nodes_with_incoming,
            "nodes_with_outgoing": nodes_with_outgoing,
            "isolated_nodes": isolated_nodes,
            "in_degree_zero_nodes": in_degree_zero_nodes,
            "out_degree_zero_nodes": out_degree_zero_nodes,
            "avg_in_degree": round(avg_in_degree, 4),
            "avg_out_degree": round(avg_out_degree, 4),
            "avg_degree": round(avg_degree, 4),
            "density": round(density, 6)
        }
