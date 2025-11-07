"""
Node Loader Module

Loads and instantiates node classes dynamically.
"""

import ast
import importlib
import sys
from pathlib import Path
from typing import Dict, Optional, Type
from .exceptions import NodeLoadError


class NodeLoader:
    """Loads node classes and metadata"""

    def __init__(self):
        """Initialize node loader with cache"""
        self._class_cache: Dict[str, type] = {}
        self._metadata_cache: Dict[str, dict] = {}
        self._builtin_nodes_dir = None

    def _get_builtin_nodes_dir(self) -> Path:
        """Get the built-in nodes directory"""
        if self._builtin_nodes_dir is None:
            # Get rayflow package directory
            import rayflow
            package_dir = Path(rayflow.__file__).parent
            self._builtin_nodes_dir = package_dir / "nodes"
        return self._builtin_nodes_dir

    def load_node_class(self, class_path: str) -> type:
        """
        Load a node class by its full Python path

        Args:
            class_path: e.g., "rayflow.nodes.math.add.AddNode"

        Returns:
            The node class (not instantiated)

        Raises:
            NodeLoadError: If class cannot be imported
        """
        # Check cache first
        if class_path in self._class_cache:
            return self._class_cache[class_path]

        try:
            # Split module path and class name
            parts = class_path.split('.')
            class_name = parts[-1]
            module_path = '.'.join(parts[:-1])

            # Import the module
            module = importlib.import_module(module_path)

            # Get the class
            node_class = getattr(module, class_name)

            # Cache it
            self._class_cache[class_path] = node_class

            return node_class

        except ImportError as e:
            raise NodeLoadError(f"Failed to import module {module_path}: {e}")
        except AttributeError as e:
            raise NodeLoadError(f"Class {class_name} not found in module {module_path}: {e}")
        except Exception as e:
            raise NodeLoadError(f"Failed to load node class {class_path}: {e}")

    def _class_path_to_file_path(self, class_path: str) -> Optional[Path]:
        """
        Convert class path to file path

        Args:
            class_path: e.g., "rayflow.nodes.math.add.AddNode"

        Returns:
            Path to Python file or None if not found
        """
        # Parse class path
        parts = class_path.split('.')

        # For built-in nodes: rayflow.nodes.{category}.{filename}.{ClassName}
        if parts[0] == 'rayflow' and parts[1] == 'nodes':
            builtin_dir = self._get_builtin_nodes_dir()

            # Path: nodes/{category}/{filename}.py
            if len(parts) >= 4:
                category = parts[2]
                filename = parts[3]
                file_path = builtin_dir / category / f"{filename}.py"

                if file_path.exists():
                    return file_path

        # TODO: Handle user nodes when we know the working directory
        return None

    def _extract_metadata_from_ast(self, py_file: Path) -> dict:
        """
        Extract metadata from Python file using AST

        Args:
            py_file: Path to Python file

        Returns:
            Metadata dict
        """
        metadata = {
            'icon': None,
            'category': None,
            'description': None,
            'inputs': {},
            'outputs': {},
            'exec_input': True,
            'exec_output': True,
            'constants': {}
        }

        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name):
                                    attr_name = target.id

                                    # Extract string/bool attributes
                                    if attr_name in ['icon', 'category', 'description']:
                                        if isinstance(item.value, ast.Constant):
                                            metadata[attr_name] = item.value.value

                                    # Extract exec configuration
                                    elif attr_name in ['exec_input', 'exec_output']:
                                        if isinstance(item.value, ast.Constant):
                                            metadata[attr_name] = bool(item.value.value)

                                    # Extract inputs/outputs dictionaries
                                    elif attr_name in ['inputs', 'outputs']:
                                        if isinstance(item.value, ast.Dict):
                                            parsed_dict = {}
                                            for key_node, value_node in zip(item.value.keys, item.value.values):
                                                # Extract key
                                                if isinstance(key_node, ast.Constant):
                                                    key = key_node.value
                                                else:
                                                    continue

                                                # Extract value (type name)
                                                value_type = None
                                                if isinstance(value_node, ast.Name):
                                                    value_type = value_node.id
                                                elif isinstance(value_node, ast.Constant):
                                                    value_type = str(value_node.value)

                                                if value_type:
                                                    parsed_dict[key] = value_type

                                            metadata[attr_name] = parsed_dict

                                    # Extract constants (uppercase)
                                    elif attr_name.isupper() and not attr_name.startswith('_'):
                                        if isinstance(item.value, ast.Constant):
                                            constant_value = item.value.value
                                            # Infer type
                                            if isinstance(constant_value, bool):
                                                constant_type = 'bool'
                                            elif isinstance(constant_value, int):
                                                constant_type = 'int'
                                            elif isinstance(constant_value, float):
                                                constant_type = 'float'
                                            elif isinstance(constant_value, str):
                                                constant_type = 'str'
                                            else:
                                                constant_type = 'any'

                                            metadata['constants'][attr_name] = {
                                                'value': constant_value,
                                                'type': constant_type
                                            }
        except Exception:
            # If parsing fails, return default metadata
            pass

        return metadata

    def get_node_metadata(self, class_path: str) -> dict:
        """
        Get metadata for a node class using AST parsing

        Args:
            class_path: Full path to node class

        Returns:
            NodeMetadata dict with inputs, outputs, constants, etc.
        """
        # Check cache first
        if class_path in self._metadata_cache:
            return self._metadata_cache[class_path]

        try:
            # Get file path
            file_path = self._class_path_to_file_path(class_path)

            if not file_path:
                raise NodeLoadError(f"Could not find file for {class_path}")

            # Extract metadata using AST
            ast_metadata = self._extract_metadata_from_ast(file_path)

            # Build complete metadata
            class_name = class_path.split('.')[-1]
            metadata = {
                'path': class_path,
                'name': class_name,
                'class_name': class_name,
                'inputs': ast_metadata['inputs'],
                'outputs': ast_metadata['outputs'],
                'exec_input': ast_metadata['exec_input'],
                'exec_output': ast_metadata['exec_output'],
                'icon': ast_metadata['icon'],
                'category': ast_metadata['category'],
                'description': ast_metadata['description'],
                'constants': ast_metadata['constants']
            }

            # Cache metadata
            self._metadata_cache[class_path] = metadata

            return metadata

        except Exception as e:
            raise NodeLoadError(f"Failed to get metadata for {class_path}: {e}")

    def load_all_metadata(self, flow_data: dict) -> Dict[str, dict]:
        """
        Load metadata for all nodes in flow

        Args:
            flow_data: Flow JSON

        Returns:
            Map of class_path -> NodeMetadata
        """
        metadata_map = {}
        nodes = flow_data.get('nodes', [])

        for node in nodes:
            class_path = node.get('type')
            if class_path and class_path not in metadata_map:
                try:
                    metadata = self.get_node_metadata(class_path)
                    metadata_map[class_path] = metadata
                except NodeLoadError as e:
                    # Log error but continue - validator should catch missing nodes
                    print(f"Warning: Failed to load metadata for {class_path}: {e}")

        return metadata_map

    def instantiate_node(
        self,
        class_path: str,
        constants: Optional[Dict] = None
    ) -> object:
        """
        Instantiate a node with optional constant configuration

        Args:
            class_path: Full path to node class
            constants: Optional dict of constant values to set

        Returns:
            Node instance (NOT a Ray actor, just Python object)

        Note: This creates a plain Python instance. Use ActorManager
        to create Ray actors from these instances.
        """
        try:
            # Load the class
            node_class = self.load_node_class(class_path)

            # Create instance
            instance = node_class()

            # Apply constants if provided
            if constants:
                for const_name, const_value in constants.items():
                    if hasattr(instance, const_name):
                        setattr(instance, const_name, const_value)

            return instance

        except Exception as e:
            raise NodeLoadError(f"Failed to instantiate node {class_path}: {e}")

    def reload_class(self, class_path: str) -> type:
        """
        Reload a class (useful for development/hot-reload)

        Args:
            class_path: Full path to node class

        Returns:
            Reloaded node class
        """
        # Clear from cache
        if class_path in self._class_cache:
            del self._class_cache[class_path]
        if class_path in self._metadata_cache:
            del self._metadata_cache[class_path]

        # Split module path and class name
        parts = class_path.split('.')
        module_path = '.'.join(parts[:-1])

        # Reload the module
        if module_path in sys.modules:
            importlib.reload(sys.modules[module_path])

        # Load fresh
        return self.load_node_class(class_path)

    def clear_cache(self):
        """Clear all cached classes and metadata"""
        self._class_cache.clear()
        self._metadata_cache.clear()
