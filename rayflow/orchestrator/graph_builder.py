"""
Graph Builder Module

Converts validated flow JSON to internal execution graph representation.
"""

from typing import Dict, List, Set, Tuple
from collections import deque
from .exceptions import GraphBuildError


class GraphBuilder:
    """Builds execution graph from validated flow"""

    def __init__(self, node_metadata_map: Dict[str, dict]):
        """
        Args:
            node_metadata_map: Map of class_path -> NodeMetadata
        """
        self.node_metadata_map = node_metadata_map

    def build_graph(self, flow_data: dict) -> dict:
        """
        Build execution graph from flow

        Args:
            flow_data: Validated flow JSON

        Returns:
            ExecutionGraph with dependencies and execution order
        """
        nodes = flow_data.get('nodes', [])
        edges = flow_data.get('edges', [])

        # Build node information
        graph_nodes = {}
        for node in nodes:
            node_id = node['id']
            class_path = node['type']

            # Get metadata for this node type
            metadata = self.node_metadata_map.get(class_path, {})

            # Get configured constant values
            constant_values = node.get('data', {}).get('constantValues', {})

            graph_nodes[node_id] = {
                'id': node_id,
                'class_path': class_path,
                'metadata': metadata,
                'constants': constant_values,
                'dependencies': [],
                'dependents': [],
                'data': node.get('data', {})
            }

        # Build edge information and dependencies
        graph_edges = {}
        exec_dependencies = {node_id: [] for node_id in graph_nodes}
        data_dependencies = {node_id: [] for node_id in graph_nodes}

        for edge in edges:
            edge_id = edge['id']
            source = edge['source']
            target = edge['target']
            source_handle = edge.get('sourceHandle', '')
            target_handle = edge.get('targetHandle', '')

            # Determine edge type
            edge_type = 'exec' if (edge.get('type') == 'exec' or source_handle == 'exec') else 'data'

            graph_edges[edge_id] = {
                'id': edge_id,
                'source': source,
                'target': target,
                'source_handle': source_handle,
                'target_handle': target_handle,
                'edge_type': edge_type
            }

            # Track dependencies
            if edge_type == 'exec':
                exec_dependencies[target].append(source)
            else:
                data_dependencies[target].append(source)

        # Combine dependencies (a node depends on both exec and data predecessors)
        all_dependencies = {}
        for node_id in graph_nodes:
            deps = list(set(exec_dependencies[node_id] + data_dependencies[node_id]))
            all_dependencies[node_id] = deps
            graph_nodes[node_id]['dependencies'] = deps

        # Build dependents (inverse of dependencies)
        for node_id, deps in all_dependencies.items():
            for dep in deps:
                if dep in graph_nodes:
                    graph_nodes[dep]['dependents'].append(node_id)

        # Identify special nodes
        special_nodes = self._identify_special_nodes(nodes)

        # Compute topological execution order
        try:
            execution_order = self._topological_sort(all_dependencies, special_nodes['start'])
        except Exception as e:
            raise GraphBuildError(f"Failed to compute execution order: {e}")

        # Build final graph
        execution_graph = {
            'nodes': graph_nodes,
            'edges': graph_edges,
            'start_node': special_nodes['start'],
            'return_nodes': special_nodes['returns'],
            'execution_order': execution_order,
            'exec_dependencies': exec_dependencies,
            'data_dependencies': data_dependencies
        }

        return execution_graph

    def _identify_special_nodes(self, nodes: List[dict]) -> dict:
        """Identify START and RETURN nodes"""
        start_node = None
        return_nodes = []

        for node in nodes:
            class_path = node['type']
            if 'StartNode' in class_path:
                start_node = node['id']
            elif 'ReturnNode' in class_path:
                return_nodes.append(node['id'])

        return {
            'start': start_node,
            'returns': return_nodes
        }

    def _topological_sort(self, dependencies: Dict[str, List[str]], start_node: str) -> List[str]:
        """
        Compute topological execution order using Kahn's algorithm

        Args:
            dependencies: Map of node_id -> list of dependency node_ids
            start_node: ID of START node

        Returns:
            List of node IDs in execution order

        Raises:
            GraphBuildError: If graph has cycles (should already be caught by validator)
        """
        # Calculate in-degrees
        in_degree = {node_id: len(deps) for node_id, deps in dependencies.items()}

        # Queue starts with nodes that have no dependencies
        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])

        # Result order
        order = []

        # Process queue
        while queue:
            # Get node with no dependencies
            current = queue.popleft()
            order.append(current)

            # For each node that depends on current
            for node_id, deps in dependencies.items():
                if current in deps:
                    in_degree[node_id] -= 1
                    if in_degree[node_id] == 0:
                        queue.append(node_id)

        # Check if all nodes were processed
        if len(order) != len(dependencies):
            unprocessed = set(dependencies.keys()) - set(order)
            raise GraphBuildError(
                f"Cannot compute execution order - possible cycle involving: {unprocessed}"
            )

        return order

    def get_node_info(self, execution_graph: dict, node_id: str) -> dict:
        """
        Get information about a specific node

        Args:
            execution_graph: The execution graph
            node_id: Node to get info for

        Returns:
            Node information dict
        """
        return execution_graph['nodes'].get(node_id)

    def get_exec_successors(self, execution_graph: dict, node_id: str) -> List[Tuple[str, str]]:
        """
        Get nodes connected via exec from this node

        Args:
            execution_graph: The execution graph
            node_id: Source node

        Returns:
            List of (target_node_id, exec_output_name) tuples
        """
        successors = []
        for edge_id, edge in execution_graph['edges'].items():
            if edge['source'] == node_id and edge['edge_type'] == 'exec':
                target = edge['target']
                output_name = edge['source_handle']
                successors.append((target, output_name))

        return successors

    def get_data_sources(self, execution_graph: dict, node_id: str) -> Dict[str, Tuple[str, str]]:
        """
        Get data source information for a node's inputs

        Args:
            execution_graph: The execution graph
            node_id: Target node

        Returns:
            Map of {input_name: (source_node_id, source_output_name)}
        """
        sources = {}
        for edge_id, edge in execution_graph['edges'].items():
            if edge['target'] == node_id and edge['edge_type'] == 'data':
                input_name = edge['target_handle']
                source_node = edge['source']
                source_output = edge['source_handle']
                sources[input_name] = (source_node, source_output)

        return sources
