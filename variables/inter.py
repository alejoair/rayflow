from rayflow import RayflowVariable

class InterVariable(RayflowVariable):
    """Variable inter"""

    variable_name = "inter"
    value_type = "int"
    default_value = 0
    description = "Variable inter"
    category = "user-created"
    tags = ["user-created"]