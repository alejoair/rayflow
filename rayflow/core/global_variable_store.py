"""
Global Variable Store

Ray actor that manages global variables shared across workflow execution.
"""

import importlib
import ray
from typing import Any, Dict, Optional, List
from pathlib import Path


@ray.remote
class GlobalVariableStore:
    """
    Ray actor that manages global variables during workflow execution.

    Provides thread-safe storage and retrieval of variables that can be
    shared across all nodes in a workflow.
    """

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the global variable store

        Args:
            working_dir: Working directory to scan for variable definitions
        """
        self.variables: Dict[str, Any] = {}
        self.variable_metadata: Dict[str, Dict] = {}
        self.working_dir = Path(working_dir) if working_dir else None

        # Load variable definitions if working directory provided
        if self.working_dir:
            self._load_variable_definitions()

    def _load_variable_definitions(self):
        """Load variable definitions from the working directory"""
        variables_dir = self.working_dir / "variables"

        if not variables_dir.exists():
            return

        # Scan for variable files
        for py_file in variables_dir.glob("*.py"):
            if py_file.name == "__init__.py":
                continue

            try:
                # Parse metadata using AST (similar to endpoint)
                metadata = self._extract_variable_metadata(py_file)

                if metadata.get('variable_name'):
                    var_name = metadata['variable_name']
                    self.variable_metadata[var_name] = metadata

                    # Initialize with default value if provided
                    default_value = metadata.get('default_value')
                    if default_value is not None:
                        # Handle custom types
                        if metadata.get('is_custom') and metadata.get('custom_import'):
                            try:
                                # Execute custom import
                                exec(metadata['custom_import'])
                                # Transform value if needed
                                # Note: In real implementation, this would be safer
                                self.variables[var_name] = default_value
                            except Exception as e:
                                print(f"Warning: Failed to initialize custom variable {var_name}: {e}")
                                self.variables[var_name] = default_value
                        else:
                            self.variables[var_name] = default_value

            except Exception as e:
                print(f"Warning: Failed to load variable from {py_file}: {e}")

    def _extract_variable_metadata(self, py_file: Path) -> Dict:
        """Extract variable metadata using AST parsing"""
        import ast

        metadata = {
            'variable_name': None,
            'value_type': None,
            'default_value': None,
            'description': '',
            'is_custom': False,
            'custom_import': None,
            'is_readonly': False
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

                                    # Extract string attributes
                                    if attr_name in ['variable_name', 'value_type', 'description', 'custom_import']:
                                        if isinstance(item.value, ast.Constant):
                                            metadata[attr_name] = item.value.value

                                    # Extract boolean attributes
                                    elif attr_name in ['is_custom', 'is_readonly']:
                                        if isinstance(item.value, ast.Constant):
                                            metadata[attr_name] = bool(item.value.value)

                                    # Extract default_value
                                    elif attr_name == 'default_value':
                                        if isinstance(item.value, ast.Constant):
                                            metadata[attr_name] = item.value.value
                                        elif isinstance(item.value, ast.Name) and item.value.id == 'None':
                                            metadata[attr_name] = None
                    break
        except Exception:
            pass

        return metadata

    def get_variable(self, name: str) -> Any:
        """
        Get the value of a variable

        Args:
            name: Variable name

        Returns:
            Variable value

        Raises:
            KeyError: If variable doesn't exist
        """
        if name not in self.variables:
            raise KeyError(f"Variable '{name}' not found")

        return self.variables[name]

    def set_variable(self, name: str, value: Any) -> bool:
        """
        Set the value of a variable

        Args:
            name: Variable name
            value: New value

        Returns:
            bool: True if set successfully

        Raises:
            ValueError: If variable is readonly or validation fails
            TypeError: If value type is incompatible
        """
        # Check if variable is readonly
        metadata = self.variable_metadata.get(name, {})
        if metadata.get('is_readonly', False):
            raise ValueError(f"Variable '{name}' is readonly")

        # Validate value if metadata available
        if name in self.variable_metadata:
            self._validate_value(name, value)

        # Store the value
        self.variables[name] = value
        return True

    def _validate_value(self, name: str, value: Any):
        """
        Validate a value against variable metadata

        Args:
            name: Variable name
            value: Value to validate

        Raises:
            TypeError: If value type is incompatible
        """
        metadata = self.variable_metadata[name]
        value_type = metadata.get('value_type')

        if value_type and value is not None:
            # Basic type checking
            type_map = {
                'int': int,
                'float': (int, float),  # Allow int for float
                'str': str,
                'bool': bool,
                'dict': dict,
                'list': list
            }

            if value_type in type_map:
                expected_type = type_map[value_type]
                if not isinstance(value, expected_type):
                    raise TypeError(
                        f"Variable '{name}' expects {value_type}, got {type(value).__name__}"
                    )

    def has_variable(self, name: str) -> bool:
        """
        Check if a variable exists

        Args:
            name: Variable name

        Returns:
            bool: True if variable exists
        """
        return name in self.variables

    def list_variables(self) -> List[str]:
        """
        Get list of all variable names

        Returns:
            List of variable names
        """
        return list(self.variables.keys())

    def get_variable_info(self, name: str) -> Dict:
        """
        Get metadata for a variable

        Args:
            name: Variable name

        Returns:
            Variable metadata dict

        Raises:
            KeyError: If variable doesn't exist
        """
        if name not in self.variable_metadata:
            if name in self.variables:
                # Variable exists but no metadata
                return {
                    'variable_name': name,
                    'value_type': 'any',
                    'has_value': True,
                    'current_value': self.variables[name]
                }
            else:
                raise KeyError(f"Variable '{name}' not found")

        metadata = self.variable_metadata[name].copy()
        metadata['has_value'] = name in self.variables
        if metadata['has_value']:
            metadata['current_value'] = self.variables[name]

        return metadata

    def get_all_variables(self) -> Dict[str, Any]:
        """
        Get all variables as a dictionary

        Returns:
            Dictionary of all variables {name: value}
        """
        return self.variables.copy()

    def clear_variable(self, name: str) -> bool:
        """
        Remove a variable

        Args:
            name: Variable name

        Returns:
            bool: True if removed successfully
        """
        if name in self.variables:
            del self.variables[name]
            return True
        return False

    def clear_all_variables(self):
        """Clear all variables (but keep metadata)"""
        self.variables.clear()

    def get_stats(self) -> Dict:
        """
        Get statistics about the variable store

        Returns:
            Statistics dictionary
        """
        return {
            'total_variables': len(self.variables),
            'defined_variables': len(self.variable_metadata),
            'variables_with_values': len([k for k in self.variable_metadata.keys() if k in self.variables]),
            'custom_variables': len([k for k, v in self.variable_metadata.items() if v.get('is_custom', False)]),
            'readonly_variables': len([k for k, v in self.variable_metadata.items() if v.get('is_readonly', False)])
        }