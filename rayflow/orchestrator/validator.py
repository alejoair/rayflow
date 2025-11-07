"""
Flow Validator Module

Validates flow structure and rules before execution.
"""

from typing import Dict, List, Tuple, Set
from .exceptions import ValidationError


class FlowValidator:
    """Validates flow structure before execution"""

    def validate(self, flow_data: dict) -> Tuple[bool, List[str], List[str]]:
        """
        Validate the flow structure

        Args:
            flow_data: Raw flow JSON from frontend

        Returns:
            (is_valid, errors, warnings)
            - is_valid: True if valid, False otherwise
            - errors: List of validation error messages (cause is_valid = False)
            - warnings: List of validation warning messages (don't affect is_valid)
        """
        errors = []
        warnings = []

        # Run all validation checks
        errors.extend(self._check_single_start(flow_data))
        errors.extend(self._check_at_least_one_return(flow_data))
        errors.extend(self._check_all_nodes_reachable(flow_data))
        errors.extend(self._check_return_nodes_reachable(flow_data))
        errors.extend(self._check_no_cycles(flow_data))
        errors.extend(self._check_type_compatibility(flow_data))

        # Multiple return paths is a warning, not an error
        warnings.extend(self._check_multiple_return_paths(flow_data))

        is_valid = len(errors) == 0
        return is_valid, errors, warnings

    def _check_single_start(self, flow_data: dict) -> List[str]:
        """Ensure exactly one START node exists"""
        errors = []
        nodes = flow_data.get('nodes', [])

        # COMPREHENSIVE DEBUG: Log what we're searching for
        print(f"[VALIDATOR] Searching for START nodes in {len(nodes)} nodes:")
        start_nodes_found = []
        for i, node in enumerate(nodes):
            node_type = node.get('type', '')
            node_id = node.get('id', 'unknown')
            node_label = node.get('data', {}).get('label', 'N/A')
            is_start = 'StartNode' in node_type
            if is_start:
                start_nodes_found.append(f"{node_label} ({node_id})")
            print(f"  Node {i+1}: id='{node_id}', label='{node_label}', type='{node_type}', contains 'StartNode': {is_start}")

        print(f"[VALIDATOR] START nodes found: {start_nodes_found}")

        start_nodes = [
            node for node in nodes
            if 'StartNode' in node.get('type', '')
        ]

        if len(start_nodes) == 0:
            errors.append("Flow must have exactly one START node (found 0)")
        elif len(start_nodes) > 1:
            errors.append(f"Flow must have exactly one START node (found {len(start_nodes)})")

        return errors

    def _check_at_least_one_return(self, flow_data: dict) -> List[str]:
        """Ensure at least one RETURN node exists"""
        errors = []
        nodes = flow_data.get('nodes', [])

        return_nodes = [
            node for node in nodes
            if 'ReturnNode' in node.get('type', '')
        ]

        if len(return_nodes) == 0:
            errors.append("Flow must have at least one RETURN node")

        return errors

    def _check_all_nodes_reachable(self, flow_data: dict) -> List[str]:
        """Ensure all nodes are reachable from START"""
        errors = []
        nodes = flow_data.get('nodes', [])
        edges = flow_data.get('edges', [])

        if not nodes:
            return errors

        # Find START node
        start_nodes = [n for n in nodes if 'StartNode' in n.get('type', '')]
        if not start_nodes:
            return errors  # Already caught by _check_single_start

        start_id = start_nodes[0]['id']

        # Build adjacency list (only exec connections)
        graph = {node['id']: [] for node in nodes}
        for edge in edges:
            # Only follow exec connections for reachability
            if edge.get('type') == 'exec' or 'exec' in edge.get('sourceHandle', ''):
                source = edge['source']
                target = edge['target']
                if source in graph:
                    graph[source].append(target)

        # BFS from START
        visited = set()
        queue = [start_id]
        visited.add(start_id)

        while queue:
            current = queue.pop(0)
            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        # Check if all nodes were reached
        all_node_ids = {node['id'] for node in nodes}
        unreachable = all_node_ids - visited

        if unreachable:
            unreachable_names = []
            for node_id in unreachable:
                node = next((n for n in nodes if n['id'] == node_id), None)
                if node:
                    label = node.get('data', {}).get('label', node_id)
                    unreachable_names.append(f"{label} ({node_id})")

            errors.append(
                f"The following nodes are not reachable from START: {', '.join(unreachable_names)}"
            )

        return errors

    def _check_return_nodes_reachable(self, flow_data: dict) -> List[str]:
        """Ensure at least one RETURN node is reachable"""
        errors = []
        nodes = flow_data.get('nodes', [])
        edges = flow_data.get('edges', [])

        if not nodes:
            return errors

        # Find START and RETURN nodes
        start_nodes = [n for n in nodes if 'StartNode' in n.get('type', '')]
        return_nodes = [n for n in nodes if 'ReturnNode' in n.get('type', '')]

        if not start_nodes or not return_nodes:
            return errors  # Already caught by other checks

        start_id = start_nodes[0]['id']
        return_ids = {node['id'] for node in return_nodes}

        # Build adjacency list (only exec connections)
        graph = {node['id']: [] for node in nodes}
        for edge in edges:
            if edge.get('type') == 'exec' or 'exec' in edge.get('sourceHandle', ''):
                source = edge['source']
                target = edge['target']
                if source in graph:
                    graph[source].append(target)

        # BFS from START to see if any RETURN is reachable
        visited = set()
        queue = [start_id]
        visited.add(start_id)
        found_return = False

        while queue:
            current = queue.pop(0)
            if current in return_ids:
                found_return = True
                break

            for neighbor in graph.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        if not found_return:
            errors.append("No RETURN node is reachable from START")

        return errors

    def _check_no_cycles(self, flow_data: dict) -> List[str]:
        """Ensure no execution cycles exist"""
        errors = []
        nodes = flow_data.get('nodes', [])
        edges = flow_data.get('edges', [])

        if not nodes:
            return errors

        # Build adjacency list (only exec connections)
        graph = {node['id']: [] for node in nodes}
        for edge in edges:
            if edge.get('type') == 'exec' or 'exec' in edge.get('sourceHandle', ''):
                source = edge['source']
                target = edge['target']
                if source in graph:
                    graph[source].append(target)

        # DFS cycle detection
        WHITE = 0  # Unvisited
        GRAY = 1   # Visiting (in current path)
        BLACK = 2  # Visited (completed)

        colors = {node_id: WHITE for node_id in graph}
        cycle_found = False
        cycle_path = []

        def dfs(node_id: str, path: List[str]) -> bool:
            nonlocal cycle_found, cycle_path

            if cycle_found:
                return True

            colors[node_id] = GRAY
            path.append(node_id)

            for neighbor in graph.get(node_id, []):
                if colors[neighbor] == GRAY:
                    # Found a cycle
                    cycle_found = True
                    cycle_start_idx = path.index(neighbor)
                    cycle_path = path[cycle_start_idx:] + [neighbor]
                    return True
                elif colors[neighbor] == WHITE:
                    if dfs(neighbor, path):
                        return True

            path.pop()
            colors[node_id] = BLACK
            return False

        # Check for cycles starting from each unvisited node
        for node_id in graph:
            if colors[node_id] == WHITE:
                if dfs(node_id, []):
                    break

        if cycle_found:
            # Format cycle path with node labels
            cycle_labels = []
            for node_id in cycle_path:
                node = next((n for n in nodes if n['id'] == node_id), None)
                if node:
                    label = node.get('data', {}).get('label', node_id)
                    cycle_labels.append(label)

            errors.append(
                f"Execution cycle detected: {' → '.join(cycle_labels)}"
            )

        return errors

    def _check_type_compatibility(self, flow_data: dict) -> List[str]:
        """Ensure connected ports have compatible types"""
        errors = []
        nodes = flow_data.get('nodes', [])
        edges = flow_data.get('edges', [])

        # Build node map for quick lookup
        node_map = {node['id']: node for node in nodes}

        for edge in edges:
            source_id = edge['source']
            target_id = edge['target']
            source_handle = edge.get('sourceHandle', '')
            target_handle = edge.get('targetHandle', '')

            # Skip exec connections (always compatible)
            if edge.get('type') == 'exec' or source_handle == 'exec':
                continue

            source_node = node_map.get(source_id)
            target_node = node_map.get(target_id)

            if not source_node or not target_node:
                continue

            # Get output type from source
            source_outputs = source_node.get('data', {}).get('outputs', {})
            source_type = source_outputs.get(source_handle, {}).get('type', 'any')

            # Get input type from target
            target_inputs = target_node.get('data', {}).get('inputs', {})
            target_type = target_inputs.get(target_handle, {}).get('type', 'any')

            # Check compatibility
            if not self._types_compatible(source_type, target_type):
                source_label = source_node.get('data', {}).get('label', source_id)
                target_label = target_node.get('data', {}).get('label', target_id)

                errors.append(
                    f"Type mismatch: {source_label}.{source_handle} ({source_type}) "
                    f"→ {target_label}.{target_handle} ({target_type})"
                )

        return errors

    def _types_compatible(self, source_type: str, target_type: str) -> bool:
        """Check if two types are compatible for connection"""
        # 'any' is compatible with everything
        if source_type == 'any' or target_type == 'any':
            return True

        # Otherwise, types must match exactly
        return source_type == target_type

    def _check_multiple_return_paths(self, flow_data: dict) -> List[str]:
        """Check for multiple reachable RETURN paths and warn user"""
        errors = []
        nodes = flow_data.get('nodes', [])
        edges = flow_data.get('edges', [])

        if not nodes:
            return errors

        # Find START and RETURN nodes
        start_nodes = [n for n in nodes if 'StartNode' in n.get('type', '')]
        return_nodes = [n for n in nodes if 'ReturnNode' in n.get('type', '')]

        if not start_nodes or len(return_nodes) <= 1:
            return errors  # No issue if 0 or 1 RETURN nodes

        start_id = start_nodes[0]['id']
        return_ids = {node['id'] for node in return_nodes}

        # Build adjacency list (only exec connections)
        graph = {node['id']: [] for node in nodes}
        for edge in edges:
            if edge.get('type') == 'exec' or 'exec' in edge.get('sourceHandle', ''):
                source = edge['source']
                target = edge['target']
                if source in graph:
                    graph[source].append(target)

        # Find all RETURN nodes reachable from START using DFS
        def find_all_reachable_returns(start_id: str) -> Set[str]:
            visited = set()
            reachable_returns = set()

            def dfs(node_id: str):
                if node_id in visited:
                    return
                visited.add(node_id)

                if node_id in return_ids:
                    reachable_returns.add(node_id)
                    # Continue DFS even from RETURN nodes (in case there are more paths)

                for neighbor in graph.get(node_id, []):
                    dfs(neighbor)

            dfs(start_id)
            return reachable_returns

        reachable_returns = find_all_reachable_returns(start_id)

        if len(reachable_returns) > 1:
            # Create warning message with node names
            return_names = []
            for return_id in reachable_returns:
                node = next((n for n in nodes if n['id'] == return_id), None)
                if node:
                    label = node.get('data', {}).get('label', return_id)
                    return_names.append(f"{label} ({return_id})")

            warning_msg = (
                f"Flow has {len(reachable_returns)} exit points - whichever executes first will complete the flow."
            )
            errors.append(warning_msg)

        return errors
