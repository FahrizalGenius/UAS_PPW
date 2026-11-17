"""Adjacency Matrix construction, DataFrame conversion, and CSV exporter using NumPy and Pandas."""
import io
import logging
from typing import Dict, List, Tuple, Any, Optional
import networkx as nx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class AdjacencyMatrixBuilder:
    """Handles adjacency matrix calculations, node indexing, and Pandas/CSV conversions."""

    @staticmethod
    def build_matrix(graph: nx.DiGraph, nodelist: Optional[List[Any]] = None) -> Tuple[np.ndarray, List[Dict[str, Any]], List[Any]]:
        """
        Build an N x N binary adjacency matrix from a directed graph.
        
        Rules:
            - Rows represent source nodes, columns represent target nodes.
            - Value is 1 if directed edge (i -> j) exists, 0 otherwise.
            - Diagonal is 1 only if self-loop exists (i -> i).
            - Matrix is strictly directed (A -> B does not imply B -> A).
            - Empty graphs return empty (0, 0) array.
            
        Returns:
            Tuple of:
                - matrix: np.ndarray (shape N x N, int dtype)
                - node_mapping: List of dicts with node metadata (index, page_id, url, title)
                - nodes: List of node IDs in exact index order
        """
        if graph.number_of_nodes() == 0:
            return np.zeros((0, 0), dtype=int), [], []

        if nodelist is None:
            # Deterministic ordering by node ID (page_id)
            nodelist = sorted(graph.nodes())

        N = len(nodelist)
        node_to_idx = {node_id: idx for idx, node_id in enumerate(nodelist)}

        # Initialize N x N zero matrix
        matrix = np.zeros((N, N), dtype=int)

        # Fill binary edges (directed: source_row -> target_col)
        for u, v in graph.edges():
            if u in node_to_idx and v in node_to_idx:
                row_idx = node_to_idx[u]
                col_idx = node_to_idx[v]
                matrix[row_idx, col_idx] = 1

        # Build node metadata mapping
        node_mapping = []
        for idx, node_id in enumerate(nodelist):
            attr = graph.nodes.get(node_id, {})
            node_mapping.append({
                "index": idx,
                "page_id": node_id,
                "url": attr.get("url", f"Page {node_id}"),
                "title": attr.get("title", f"Page #{node_id}"),
                "domain": attr.get("domain", "")
            })

        return matrix, node_mapping, nodelist

    @staticmethod
    def to_dataframe(
        matrix: np.ndarray,
        node_mapping: List[Dict[str, Any]],
        label_key: str = "page_id"
    ) -> pd.DataFrame:
        """
        Convert an adjacency matrix NumPy array to a labeled Pandas DataFrame.
        
        Args:
            matrix: N x N NumPy array.
            node_mapping: Metadata mapping from build_matrix.
            label_key: Field to use for index & columns ('page_id', 'url', or 'title').
            
        Returns:
            pd.DataFrame with identical row and column index labels.
        """
        if matrix.size == 0 or not node_mapping:
            return pd.DataFrame()

        if label_key == "url":
            labels = [item["url"] for item in node_mapping]
        elif label_key == "title":
            labels = [item["title"] for item in node_mapping]
        else:
            labels = [f"Page_{item['page_id']}" for item in node_mapping]

        df = pd.DataFrame(matrix, index=labels, columns=labels)
        return df

    @staticmethod
    def get_matrix_preview(
        matrix: np.ndarray,
        node_mapping: List[Dict[str, Any]],
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        Extract a paginated subgrid slice of the matrix for fast HTML table rendering.
        Prevents browser lag when displaying large graphs up to 300 nodes.
        """
        total_nodes = len(node_mapping)
        if total_nodes == 0:
            return {
                "sub_matrix": [],
                "row_nodes": [],
                "col_nodes": [],
                "total_nodes": 0,
                "page": 1,
                "per_page": per_page,
                "total_pages": 0
            }

        total_pages = (total_nodes + per_page - 1) // per_page
        current_page = max(1, min(page, total_pages))

        start_idx = (current_page - 1) * per_page
        end_idx = min(start_idx + per_page, total_nodes)

        # Slice sub-matrix for the current page rows and columns
        sliced_matrix = matrix[start_idx:end_idx, start_idx:end_idx].tolist()
        sliced_mapping = node_mapping[start_idx:end_idx]

        return {
            "sub_matrix": sliced_matrix,
            "row_nodes": sliced_mapping,
            "col_nodes": sliced_mapping,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "total_nodes": total_nodes,
            "page": current_page,
            "per_page": per_page,
            "total_pages": total_pages
        }

    @staticmethod
    def export_csv_stream(matrix: np.ndarray, node_mapping: List[Dict[str, Any]]) -> io.StringIO:
        """
        Export complete N x N adjacency matrix into a CSV StringIO stream.
        Headers use page URLs for clarity.
        """
        df = AdjacencyMatrixBuilder.to_dataframe(matrix, node_mapping, label_key="url")
        output = io.StringIO()
        df.to_csv(output, index=True, encoding="utf-8")
        output.seek(0)
        return output
