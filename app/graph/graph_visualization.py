"""Graph visualization data generator using PyVis and Vis.js format."""
import html
import json
import logging
from typing import Dict, Any, List
import networkx as nx
from pyvis.network import Network

logger = logging.getLogger(__name__)

class GraphVisualizer:
    """Formats directed graph networks for PyVis and Vis-Network interactive rendering."""

    @staticmethod
    def get_vis_network_data(graph: nx.DiGraph) -> Dict[str, Any]:
        """
        Generate Vis-Network JSON data (nodes, edges, options) with safe HTML tooltips.
        
        Security:
            All titles, URLs, and domains are strictly HTML-escaped to prevent XSS.
        """
        if graph.number_of_nodes() == 0:
            return {
                "nodes": [],
                "edges": [],
                "node_details": {},
                "options": {}
            }

        in_degrees = dict(graph.in_degree())
        out_degrees = dict(graph.out_degree())

        nodes_list: List[Dict[str, Any]] = []
        edges_list: List[Dict[str, Any]] = []
        node_details: Dict[str, Any] = {}

        for node_id, data in graph.nodes(data=True):
            raw_title = data.get("title", f"Page {node_id}")
            raw_url = data.get("url", "")
            raw_domain = data.get("domain", "")
            depth = data.get("depth", 0)

            in_deg = in_degrees.get(node_id, 0)
            out_deg = out_degrees.get(node_id, 0)

            # Node label (shortened for clarity)
            short_label = raw_title[:20] + "..." if len(raw_title) > 20 else (raw_title or raw_domain)

            # Safe HTML Tooltip
            safe_title = html.escape(raw_title)
            safe_url = html.escape(raw_url)
            safe_domain = html.escape(raw_domain)

            tooltip_html = (
                f"<div style='font-family: sans-serif; font-size: 12px; max-width: 280px; padding: 4px;'>"
                f"<strong>{safe_title}</strong><br/>"
                f"<span style='color: #64748b; word-break: break-all;'>{safe_url}</span><hr style='margin: 4px 0;'/>"
                f"<span>Domain: <strong>{safe_domain}</strong></span><br/>"
                f"<span>Level Depth: <strong>{depth}</strong></span><br/>"
                f"<span>In-Degree: <strong style='color:#16a34a;'>{in_deg}</strong> | "
                f"Out-Degree: <strong style='color:#2563eb;'>{out_deg}</strong></span>"
                f"</div>"
            )

            # Sizing based on in-degree (popular pages appear slightly larger)
            base_size = 14 + min(in_deg * 2, 26)

            # Color styling based on depth level
            if depth == 0:
                color = {"background": "#ef4444", "border": "#dc2626", "highlight": "#b91c1c"}
            elif in_deg == 0 and out_deg == 0:
                color = {"background": "#cbd5e1", "border": "#94a3b8", "highlight": "#64748b"}
            else:
                color = {"background": "#38bdf8", "border": "#0284c7", "highlight": "#0369a1"}

            nodes_list.append({
                "id": node_id,
                "label": short_label,
                "title": tooltip_html,
                "size": base_size,
                "color": color,
                "shape": "dot",
                "font": {"size": 11, "color": "#0f172a", "face": "Segoe UI, sans-serif"}
            })

            # Store full metadata for client-side sidebar panel when a node is clicked
            # Pre-gather incoming & outgoing neighbors
            incoming_neighbors = []
            for pred in graph.predecessors(node_id):
                pred_data = graph.nodes.get(pred, {})
                incoming_neighbors.append({
                    "id": pred,
                    "url": pred_data.get("url", ""),
                    "title": pred_data.get("title", f"Page {pred}")
                })

            outgoing_neighbors = []
            for succ in graph.successors(node_id):
                succ_data = graph.nodes.get(succ, {})
                outgoing_neighbors.append({
                    "id": succ,
                    "url": succ_data.get("url", ""),
                    "title": succ_data.get("title", f"Page {succ}")
                })

            node_details[str(node_id)] = {
                "id": node_id,
                "url": raw_url,
                "title": raw_title,
                "domain": raw_domain,
                "depth": depth,
                "in_degree": in_deg,
                "out_degree": out_deg,
                "incoming": incoming_neighbors,
                "outgoing": outgoing_neighbors
            }

        # Directed Edges with Arrows
        for u, v, data in graph.edges(data=True):
            edges_list.append({
                "from": u,
                "to": v,
                "arrows": {"to": {"enabled": True, "scaleFactor": 0.65}},
                "color": {"color": "#94a3b8", "highlight": "#2563eb", "opacity": 0.65},
                "width": 1.2,
                "smooth": {"type": "continuous", "roundness": 0.2}
            })

        # Physics options configured for smooth and calm layout up to 300 nodes
        options = {
            "nodes": {
                "borderWidth": 1.5,
                "shadow": True
            },
            "edges": {
                "shadow": False,
                "smooth": {
                    "type": "continuous",
                    "roundness": 0.2
                }
            },
            "physics": {
                "enabled": True,
                "solver": "barnesHut",
                "barnesHut": {
                    "gravitationalConstant": -3500,
                    "centralGravity": 0.35,
                    "springLength": 95,
                    "springConstant": 0.04,
                    "damping": 0.6,
                    "avoidOverlap": 0.25
                },
                "stabilization": {
                    "enabled": True,
                    "iterations": 200,
                    "updateInterval": 25,
                    "fit": True
                },
                "minVelocity": 0.75
            },
            "interaction": {
                "hover": True,
                "navigationButtons": False,
                "keyboard": False,
                "zoomView": True,
                "dragView": True,
                "dragNodes": True
            }
        }

        return {
            "nodes": nodes_list,
            "edges": edges_list,
            "node_details": node_details,
            "options": options
        }

    @staticmethod
    def generate_pyvis_html(graph: nx.DiGraph, height: str = "520px") -> str:
        """
        Generate standalone PyVis HTML snippet using pyvis.network.Network.
        """
        if graph.number_of_nodes() == 0:
            return ""

        net = Network(height=height, width="100%", directed=True, notebook=False)
        for node_id, data in graph.nodes(data=True):
            title_text = data.get("title", f"Page {node_id}")
            net.add_node(node_id, label=title_text[:20], title=data.get("url", ""))

        for u, v in graph.edges():
            net.add_edge(u, v)

        net.set_options("""
        var options = {
          "edges": {
            "arrows": { "to": { "enabled": true } }
          },
          "physics": {
            "forceAtlas2Based": { "springLength": 80 },
            "solver": "forceAtlas2Based"
          }
        }
        """)
        return net.generate_html()
