"""Tests for Variable Store system"""

import pytest
import ray
import tempfile
from pathlib import Path
from rayflow.orchestrator.variable_store_manager import VariableStoreManager
from rayflow.core.global_variable_store import GlobalVariableStore


class TestVariableStoreSystem:
    """Test the complete variable store system"""

    @classmethod
    def setup_class(cls):
        """Setup Ray for tests"""
        if not ray.is_initialized():
            ray.init(num_cpus=2, ignore_reinit_error=True)

    @classmethod
    def teardown_class(cls):
        """Cleanup Ray after tests"""
        if ray.is_initialized():
            ray.shutdown()

    def setup_method(self):
        """Setup for each test"""
        self.manager = VariableStoreManager()

    def teardown_method(self):
        """Cleanup after each test"""
        self.manager.cleanup()

    def test_create_variable_store(self):
        """Test creating a variable store"""
        store_handle = self.manager.create_store()

        assert store_handle is not None
        assert self.manager.is_ready()

    def test_basic_variable_operations(self):
        """Test basic get/set operations"""
        self.manager.create_store()

        # Set a variable
        success = self.manager.set_variable("test_var", 42)
        assert success is True

        # Get the variable
        value = self.manager.get_variable("test_var")
        assert value == 42

        # Check if variable exists
        assert self.manager.has_variable("test_var") is True
        assert self.manager.has_variable("nonexistent") is False

    def test_variable_types(self):
        """Test different variable types"""
        self.manager.create_store()

        # Integer
        self.manager.set_variable("int_var", 123)
        assert self.manager.get_variable("int_var") == 123

        # Float
        self.manager.set_variable("float_var", 3.14)
        assert self.manager.get_variable("float_var") == 3.14

        # String
        self.manager.set_variable("str_var", "hello")
        assert self.manager.get_variable("str_var") == "hello"

        # Boolean
        self.manager.set_variable("bool_var", True)
        assert self.manager.get_variable("bool_var") is True

        # List
        self.manager.set_variable("list_var", [1, 2, 3])
        assert self.manager.get_variable("list_var") == [1, 2, 3]

        # Dict
        self.manager.set_variable("dict_var", {"key": "value"})
        assert self.manager.get_variable("dict_var") == {"key": "value"}

    def test_list_variables(self):
        """Test listing variables"""
        self.manager.create_store()

        # Initially empty
        assert self.manager.list_variables() == []

        # Add some variables
        self.manager.set_variable("var1", 1)
        self.manager.set_variable("var2", 2)
        self.manager.set_variable("var3", 3)

        # Should list all variables
        variables = self.manager.list_variables()
        assert len(variables) == 3
        assert set(variables) == {"var1", "var2", "var3"}

    def test_get_all_variables(self):
        """Test getting all variables at once"""
        self.manager.create_store()

        # Set multiple variables
        self.manager.set_variable("a", 1)
        self.manager.set_variable("b", "hello")
        self.manager.set_variable("c", [1, 2, 3])

        # Get all
        all_vars = self.manager.get_all_variables()
        expected = {"a": 1, "b": "hello", "c": [1, 2, 3]}
        assert all_vars == expected

    def test_clear_variable(self):
        """Test removing variables"""
        self.manager.create_store()

        # Set and clear
        self.manager.set_variable("temp_var", "temporary")
        assert self.manager.has_variable("temp_var") is True

        success = self.manager.clear_variable("temp_var")
        assert success is True
        assert self.manager.has_variable("temp_var") is False

        # Try to clear non-existent variable
        success = self.manager.clear_variable("nonexistent")
        assert success is False

    def test_get_nonexistent_variable(self):
        """Test getting a variable that doesn't exist"""
        self.manager.create_store()

        with pytest.raises(KeyError):
            self.manager.get_variable("nonexistent")

    def test_store_not_created_error(self):
        """Test operations when store is not created"""
        # Don't create store

        with pytest.raises(RuntimeError):
            self.manager.get_variable("test")

        with pytest.raises(RuntimeError):
            self.manager.set_variable("test", 1)

    def test_initial_variables(self):
        """Test creating store with initial variables"""
        initial_vars = {
            "startup_value": 100,
            "config_flag": True,
            "default_message": "Hello World"
        }

        self.manager.create_store(initial_variables=initial_vars)

        # Check all initial variables were set
        for name, expected_value in initial_vars.items():
            actual_value = self.manager.get_variable(name)
            assert actual_value == expected_value

    def test_variable_store_with_definitions(self):
        """Test loading variable definitions from files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            variables_dir = temp_path / "variables"
            variables_dir.mkdir()

            # Create a sample variable file
            var_file = variables_dir / "counter.py"
            var_file.write_text('''from rayflow.core.variable import RayflowVariable

class CounterVariable(RayflowVariable):
    """Simple counter variable"""

    variable_name = "counter"
    value_type = "int"
    default_value = 0
    description = "Simple counter"
''')

            # Create store with working directory
            self.manager.create_store(working_dir=str(temp_path))

            # Variable should be loaded with default value
            assert self.manager.has_variable("counter")
            assert self.manager.get_variable("counter") == 0

            # Should have metadata
            info = self.manager.get_variable_info("counter")
            assert info['variable_name'] == "counter"
            assert info['value_type'] == "int"
            assert info['default_value'] == 0

    def test_get_stats(self):
        """Test getting variable store statistics"""
        self.manager.create_store()

        # Initially empty
        stats = self.manager.get_stats()
        assert stats['total_variables'] == 0

        # Add some variables
        self.manager.set_variable("var1", 1)
        self.manager.set_variable("var2", 2)

        stats = self.manager.get_stats()
        assert stats['total_variables'] == 2

    def test_manager_cleanup(self):
        """Test manager cleanup"""
        self.manager.create_store()
        assert self.manager.is_ready()

        self.manager.cleanup()
        assert not self.manager.is_ready()