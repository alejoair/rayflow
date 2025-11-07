"""Test example with NumPy variable"""

import pytest
import ray
import numpy as np
import tempfile
from pathlib import Path
from rayflow.orchestrator.variable_store_manager import VariableStoreManager


class TestNumpyVariableExample:
    """Test real-world example with NumPy arrays"""

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

    def test_numpy_array_variable(self):
        """Test storing and retrieving NumPy arrays"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            variables_dir = temp_path / "variables"
            variables_dir.mkdir()

            # Create NumPy variable definition
            numpy_var_file = variables_dir / "data_array.py"
            numpy_var_file.write_text('''from rayflow.core.variable import RayflowVariable

class DataArrayVariable(RayflowVariable):
    """NumPy array for data processing"""

    variable_name = "data_array"
    value_type = "custom"
    default_value = None

    # Custom type configuration
    is_custom = True
    custom_import = "import numpy as np"
    custom_type_hint = "np.ndarray"

    description = "NumPy array for matrix operations"
    icon = "fa-table"
    category = "scientific"
''')

            # Create store with working directory
            self.manager.create_store(working_dir=str(temp_path))

            # Create a NumPy array
            data = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])

            # Store the NumPy array
            self.manager.set_variable("data_array", data)

            # Retrieve it
            retrieved_data = self.manager.get_variable("data_array")

            # Verify it's the same array
            assert isinstance(retrieved_data, np.ndarray)
            assert np.array_equal(retrieved_data, data)
            assert retrieved_data.shape == (3, 3)

            # Test variable info
            info = self.manager.get_variable_info("data_array")
            assert info['variable_name'] == "data_array"
            assert info['value_type'] == "custom"
            assert info['is_custom'] is True
            assert info['custom_import'] == "import numpy as np"

    def test_multiple_scientific_variables(self):
        """Test multiple scientific computing variables"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            variables_dir = temp_path / "variables"
            variables_dir.mkdir()

            # Create multiple variable definitions
            variables_def = {
                'matrix.py': '''from rayflow.core.variable import RayflowVariable

class MatrixVariable(RayflowVariable):
    variable_name = "transformation_matrix"
    value_type = "custom"
    default_value = None
    is_custom = True
    custom_import = "import numpy as np"
    description = "Transformation matrix"
    category = "linear_algebra"
''',
                'learning_rate.py': '''from rayflow.core.variable import RayflowVariable

class LearningRateVariable(RayflowVariable):
    variable_name = "learning_rate"
    value_type = "float"
    default_value = 0.001
    description = "Learning rate for optimization"
    category = "ml_hyperparams"
''',
                'batch_size.py': '''from rayflow.core.variable import RayflowVariable

class BatchSizeVariable(RayflowVariable):
    variable_name = "batch_size"
    value_type = "int"
    default_value = 32
    description = "Training batch size"
    category = "ml_hyperparams"
'''
            }

            # Write all variable files
            for filename, content in variables_def.items():
                (variables_dir / filename).write_text(content)

            # Create store
            self.manager.create_store(working_dir=str(temp_path))

            # Verify default values were loaded
            assert self.manager.get_variable("learning_rate") == 0.001
            assert self.manager.get_variable("batch_size") == 32

            # Set transformation matrix
            identity_matrix = np.eye(3)
            self.manager.set_variable("transformation_matrix", identity_matrix)

            # Verify all variables
            variables = self.manager.list_variables()
            assert set(variables) == {"learning_rate", "batch_size", "transformation_matrix"}

            # Get the matrix back
            retrieved_matrix = self.manager.get_variable("transformation_matrix")
            assert np.array_equal(retrieved_matrix, identity_matrix)

            # Test workflow simulation: update hyperparameters
            self.manager.set_variable("learning_rate", 0.01)
            self.manager.set_variable("batch_size", 64)

            # Verify updates
            assert self.manager.get_variable("learning_rate") == 0.01
            assert self.manager.get_variable("batch_size") == 64

            # Get all variables at once (like a snapshot)
            all_vars = self.manager.get_all_variables()
            assert all_vars["learning_rate"] == 0.01
            assert all_vars["batch_size"] == 64
            assert np.array_equal(all_vars["transformation_matrix"], identity_matrix)

    def test_workflow_simulation(self):
        """Simulate a complete ML workflow with variables"""
        self.manager.create_store()

        # Initialize workflow variables
        self.manager.set_variable("epoch", 0)
        self.manager.set_variable("best_accuracy", 0.0)
        self.manager.set_variable("model_weights", np.random.randn(10, 5))
        self.manager.set_variable("training_data", np.random.randn(100, 10))

        # Simulate training epochs
        for epoch in range(1, 6):
            # Update epoch
            self.manager.set_variable("epoch", epoch)

            # Simulate accuracy improvement
            current_accuracy = 0.5 + (epoch * 0.1)

            # Update best accuracy if improved
            best_acc = self.manager.get_variable("best_accuracy")
            if current_accuracy > best_acc:
                self.manager.set_variable("best_accuracy", current_accuracy)

            # Simulate weight updates
            weights = self.manager.get_variable("model_weights")
            updated_weights = weights + np.random.randn(*weights.shape) * 0.01
            self.manager.set_variable("model_weights", updated_weights)

        # Final verification
        assert self.manager.get_variable("epoch") == 5
        assert self.manager.get_variable("best_accuracy") == 1.0  # 0.5 + (5 * 0.1)

        final_weights = self.manager.get_variable("model_weights")
        assert final_weights.shape == (10, 5)

        # Get training statistics
        stats = self.manager.get_stats()
        assert stats['total_variables'] == 4