"""
Variable Store Manager Module

Manages the GlobalVariableStore Ray actor for the orchestrator.
"""

import ray
from typing import Optional, Dict, Any
from pathlib import Path
from .exceptions import NodeLoadError


class VariableStoreManager:
    """Manages the global variable store actor"""

    def __init__(self):
        """Initialize variable store manager"""
        self._store_actor = None
        self._store_handle = None

    def create_store(
        self,
        working_dir: Optional[str] = None,
        initial_variables: Optional[Dict[str, Any]] = None
    ) -> ray.ObjectRef:
        """
        Create a new GlobalVariableStore actor

        Args:
            working_dir: Working directory to scan for variable definitions
            initial_variables: Initial variable values to set

        Returns:
            Ray actor handle

        Raises:
            NodeLoadError: If failed to create store
        """
        try:
            # Import the GlobalVariableStore actor
            from rayflow.core.global_variable_store import GlobalVariableStore

            # Create the actor
            self._store_actor = GlobalVariableStore.remote(working_dir=working_dir)
            self._store_handle = self._store_actor

            # Set initial variables if provided
            if initial_variables:
                for name, value in initial_variables.items():
                    try:
                        ray.get(self._store_actor.set_variable.remote(name, value))
                    except Exception as e:
                        print(f"Warning: Failed to set initial variable {name}: {e}")

            return self._store_handle

        except Exception as e:
            raise NodeLoadError(f"Failed to create GlobalVariableStore: {e}")

    def get_store_handle(self) -> ray.ObjectRef:
        """
        Get handle to the variable store

        Returns:
            Ray actor handle

        Raises:
            RuntimeError: If store hasn't been created
        """
        if self._store_handle is None:
            raise RuntimeError("Variable store has not been created. Call create_store() first.")

        return self._store_handle

    def get_variable(self, name: str) -> Any:
        """
        Get a variable value (blocking call)

        Args:
            name: Variable name

        Returns:
            Variable value

        Raises:
            RuntimeError: If store not created
            KeyError: If variable doesn't exist
        """
        if self._store_handle is None:
            raise RuntimeError("Variable store has not been created")

        try:
            return ray.get(self._store_actor.get_variable.remote(name))
        except Exception as e:
            raise KeyError(f"Failed to get variable '{name}': {e}")

    def set_variable(self, name: str, value: Any) -> bool:
        """
        Set a variable value (blocking call)

        Args:
            name: Variable name
            value: New value

        Returns:
            bool: True if successful

        Raises:
            RuntimeError: If store not created
            ValueError: If validation fails
        """
        if self._store_handle is None:
            raise RuntimeError("Variable store has not been created")

        try:
            return ray.get(self._store_actor.set_variable.remote(name, value))
        except Exception as e:
            raise ValueError(f"Failed to set variable '{name}': {e}")

    def has_variable(self, name: str) -> bool:
        """
        Check if a variable exists (blocking call)

        Args:
            name: Variable name

        Returns:
            bool: True if variable exists
        """
        if self._store_handle is None:
            return False

        try:
            return ray.get(self._store_actor.has_variable.remote(name))
        except Exception:
            return False

    def list_variables(self) -> list:
        """
        Get list of all variable names (blocking call)

        Returns:
            List of variable names
        """
        if self._store_handle is None:
            return []

        try:
            return ray.get(self._store_actor.list_variables.remote())
        except Exception:
            return []

    def get_variable_info(self, name: str) -> Dict:
        """
        Get variable metadata (blocking call)

        Args:
            name: Variable name

        Returns:
            Variable metadata dict
        """
        if self._store_handle is None:
            raise RuntimeError("Variable store has not been created")

        try:
            return ray.get(self._store_actor.get_variable_info.remote(name))
        except Exception as e:
            raise KeyError(f"Failed to get info for variable '{name}': {e}")

    def get_all_variables(self) -> Dict[str, Any]:
        """
        Get all variables as dictionary (blocking call)

        Returns:
            Dictionary of all variables
        """
        if self._store_handle is None:
            return {}

        try:
            return ray.get(self._store_actor.get_all_variables.remote())
        except Exception:
            return {}

    def clear_variable(self, name: str) -> bool:
        """
        Remove a variable (blocking call)

        Args:
            name: Variable name

        Returns:
            bool: True if removed
        """
        if self._store_handle is None:
            return False

        try:
            return ray.get(self._store_actor.clear_variable.remote(name))
        except Exception:
            return False

    def get_stats(self) -> Dict:
        """
        Get variable store statistics (blocking call)

        Returns:
            Statistics dictionary
        """
        if self._store_handle is None:
            return {}

        try:
            return ray.get(self._store_actor.get_stats.remote())
        except Exception:
            return {}

    def cleanup(self):
        """Cleanup the variable store actor"""
        if self._store_actor is not None:
            try:
                ray.kill(self._store_actor)
            except Exception:
                pass
            self._store_actor = None
            self._store_handle = None

    def is_ready(self) -> bool:
        """Check if the variable store is ready"""
        return self._store_handle is not None