"""
Base class for RayFlow variables.

Similar to RayflowNode, this provides a standard interface for defining
variables that can be discovered and used by the GlobalVariableStore.
"""

class RayflowVariable:
    """
    Base class for all RayFlow variables.
    
    Variables are metadata definitions that describe how global variables
    should be initialized and managed during flow execution.
    """
    
    # Required metadata - must be overridden by subclasses
    variable_name = None    # str: Unique name for this variable
    value_type = None       # str: "int", "float", "str", "bool", "dict", "list", "custom"
    default_value = None    # Any: Initial value when flow starts
    
    # Optional metadata
    description = ""        # str: Human-readable description
    icon = "fa-variable"    # str: Font Awesome icon for UI
    category = "general"    # str: Category for organization in UI
    
    # Custom type support
    is_custom = False       # bool: Whether this uses a custom type
    custom_import = None    # str: Import statement for custom types (e.g., "import numpy as np")
    custom_type_hint = None # str: Type hint for documentation (e.g., "np.ndarray")
    
    # Advanced options
    tags = []              # list: Tags for filtering/searching
    is_readonly = False    # bool: Whether variable can be modified after init
    
    @classmethod
    def get_metadata(cls):
        """
        Extract all metadata from the class definition.
        
        Returns:
            dict: Complete metadata dictionary for this variable
        """
        return {
            'variable_name': cls.variable_name,
            'value_type': cls.value_type,
            'default_value': cls.default_value,
            'description': cls.description,
            'icon': cls.icon,
            'category': cls.category,
            'is_custom': cls.is_custom,
            'custom_import': cls.custom_import,
            'custom_type_hint': cls.custom_type_hint,
            'tags': cls.tags or [],
            'is_readonly': cls.is_readonly,
        }
    
    @classmethod
    def validate_definition(cls):
        """
        Validate that the variable definition is complete and valid.
        
        Returns:
            tuple: (is_valid: bool, error_message: str)
        """
        if not cls.variable_name:
            return False, "variable_name is required"
        
        if not isinstance(cls.variable_name, str):
            return False, "variable_name must be a string"
        
        if not cls.variable_name.isidentifier():
            return False, "variable_name must be a valid Python identifier"
        
        if not cls.value_type:
            return False, "value_type is required"
        
        valid_types = ["int", "float", "str", "bool", "dict", "list", "custom"]
        if cls.value_type not in valid_types:
            return False, f"value_type must be one of {valid_types}"
        
        # Custom type validation
        if cls.value_type == "custom":
            if not cls.is_custom:
                return False, "is_custom must be True for custom value_type"
            if not cls.custom_import:
                return False, "custom_import is required for custom types"
        
        # Non-custom type validation
        if cls.value_type != "custom" and cls.is_custom:
            return False, "is_custom should be False for non-custom types"
        
        return True, ""
    
    def validate(self, value):
        """
        Optional validation method for variable values.
        
        Override this method in subclasses to add custom validation logic.
        Called by GlobalVariableStore before setting a value.
        
        Args:
            value: The value to validate
            
        Returns:
            bool: True if value is valid
            
        Raises:
            TypeError, ValueError: If validation fails
        """
        # Base implementation - no validation
        return True
    
    def transform(self, value):
        """
        Optional transformation method for variable values.
        
        Override this method in subclasses to transform values before storing.
        Called by GlobalVariableStore before setting a value.
        
        Args:
            value: The value to transform
            
        Returns:
            Any: The transformed value
        """
        # Base implementation - no transformation
        return value
    
    @classmethod
    def create_example_files(cls):
        """
        Generate example variable files for different types.
        Used for documentation and testing.
        """
        examples = {
            'basic_counter.py': '''from rayflow.core.variable import RayflowVariable

class CounterVariable(RayflowVariable):
    """Simple counter variable for tracking iterations"""
    
    variable_name = "counter"
    value_type = "int"
    default_value = 0
    description = "Tracks the number of iterations"
    icon = "fa-hashtag"
    category = "counters"
''',
            
            'custom_numpy_array.py': '''from rayflow.core.variable import RayflowVariable

class NumpyArrayVariable(RayflowVariable):
    """NumPy array variable for scientific computing"""
    
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
    tags = ["numpy", "array", "scientific"]
    
    def validate(self, value):
        """Ensure value is a NumPy array"""
        import numpy as np
        if value is not None and not isinstance(value, np.ndarray):
            raise TypeError(f"Expected np.ndarray, got {type(value)}")
        return True
    
    def transform(self, value):
        """Convert lists to NumPy arrays automatically"""
        import numpy as np
        if isinstance(value, list):
            return np.array(value)
        return value
''',
            
            'readonly_config.py': '''from rayflow.core.variable import RayflowVariable

class ConfigVariable(RayflowVariable):
    """Read-only configuration variable"""
    
    variable_name = "app_config"
    value_type = "dict"
    default_value = {
        "debug": False,
        "max_workers": 4,
        "timeout": 30
    }
    description = "Application configuration (read-only)"
    icon = "fa-cog"
    category = "config"
    is_readonly = True
    tags = ["config", "readonly"]
'''
        }
        
        return examples


# Built-in variable types for common use cases
class IntVariable(RayflowVariable):
    """Helper class for integer variables"""
    value_type = "int"
    default_value = 0
    icon = "fa-hashtag"

class FloatVariable(RayflowVariable):
    """Helper class for float variables"""
    value_type = "float"
    default_value = 0.0
    icon = "fa-decimal"

class StringVariable(RayflowVariable):
    """Helper class for string variables"""
    value_type = "str"
    default_value = ""
    icon = "fa-font"

class BoolVariable(RayflowVariable):
    """Helper class for boolean variables"""
    value_type = "bool"
    default_value = False
    icon = "fa-toggle-off"

class DictVariable(RayflowVariable):
    """Helper class for dictionary variables"""
    value_type = "dict"
    default_value = {}
    icon = "fa-braces"

class ListVariable(RayflowVariable):
    """Helper class for list variables"""
    value_type = "list"
    default_value = []
    icon = "fa-list"

class CustomVariable(RayflowVariable):
    """Helper class for custom type variables"""
    value_type = "custom"
    is_custom = True
    icon = "fa-puzzle-piece"