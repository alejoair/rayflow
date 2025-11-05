import os
import ast
import importlib.util
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class NodeFile(BaseModel):
    name: str
    path: str
    type: str  # "builtin" or "user"
    category: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    inputs: Optional[dict] = None
    outputs: Optional[dict] = None
    exec_input: Optional[bool] = True
    exec_output: Optional[bool] = True
    constants: Optional[dict] = None  # Class constants (uppercase variables)


class CreateVariableRequest(BaseModel):
    """Request model for creating a new variable"""
    variable_name: str
    value_type: str  # "int", "float", "str", "bool", "dict", "list", "custom"
    default_value: Optional[str] = None  # JSON string for complex types
    description: Optional[str] = ""
    icon: Optional[str] = "fa-variable"
    category: Optional[str] = "general"
    is_custom: Optional[bool] = False
    custom_import: Optional[str] = None
    custom_type_hint: Optional[str] = None
    tags: Optional[List[str]] = []
    is_readonly: Optional[bool] = False


class CreateVariableResponse(BaseModel):
    """Response model for variable creation"""
    success: bool
    message: str
    file_path: Optional[str] = None
    variable_name: str


class VariableFile(BaseModel):
    """Model for variable metadata extracted from Python files"""
    name: str
    variable_name: str
    value_type: str
    default_value: Optional[str] = None
    description: Optional[str] = ""
    icon: Optional[str] = "fa-variable"
    category: Optional[str] = "general"
    is_custom: Optional[bool] = False
    custom_import: Optional[str] = None
    custom_type_hint: Optional[str] = None
    tags: Optional[List[str]] = []
    is_readonly: Optional[bool] = False
    file_path: str


def get_working_directory() -> Path:
    """Get the working directory where rayflow was called"""
    cwd = os.environ.get("RAYFLOW_CWD")
    if cwd:
        return Path(cwd)
    return Path.cwd()


def extract_node_metadata(py_file: Path) -> dict:
    """Extract metadata (icon, category, description, inputs, outputs, exec config) from a Python node file"""
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

        # Parse the AST to find class definitions
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Look for class attributes
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                attr_name = target.id

                                # Extract simple string/bool attributes
                                if attr_name in ['icon', 'category', 'description']:
                                    if isinstance(item.value, ast.Constant):
                                        metadata[attr_name] = item.value.value
                                    elif isinstance(item.value, ast.Str):  # Python < 3.8 compatibility
                                        metadata[attr_name] = item.value.s

                                # Extract boolean exec configuration
                                elif attr_name in ['exec_input', 'exec_output']:
                                    if isinstance(item.value, ast.Constant):
                                        metadata[attr_name] = bool(item.value.value)
                                    elif hasattr(item.value, 'value'):  # NameConstant for older Python
                                        metadata[attr_name] = bool(item.value.value)

                                # Extract dictionary attributes (inputs, outputs)
                                elif attr_name in ['inputs', 'outputs']:
                                    if isinstance(item.value, ast.Dict):
                                        parsed_dict = {}
                                        for key_node, value_node in zip(item.value.keys, item.value.values):
                                            # Extract key (should be string)
                                            if isinstance(key_node, ast.Constant):
                                                key = key_node.value
                                            elif isinstance(key_node, ast.Str):
                                                key = key_node.s
                                            else:
                                                continue

                                            # Extract value (type name)
                                            value_type = None
                                            if isinstance(value_node, ast.Name):
                                                value_type = value_node.id
                                            elif isinstance(value_node, ast.Constant):
                                                value_type = str(value_node.value)
                                            elif isinstance(value_node, ast.Str):
                                                value_type = value_node.s

                                            if value_type:
                                                parsed_dict[key] = value_type

                                        metadata[attr_name] = parsed_dict

                                # Extract constants (uppercase variables)
                                elif attr_name.isupper() and not attr_name.startswith('_'):
                                    constant_value = None
                                    constant_type = None
                                    
                                    # Get the value
                                    if isinstance(item.value, ast.Constant):
                                        constant_value = item.value.value
                                        # Infer type from Python type
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
                                    elif isinstance(item.value, ast.Str):  # Python < 3.8
                                        constant_value = item.value.s
                                        constant_type = 'str'
                                    elif isinstance(item.value, ast.Num):  # Python < 3.8
                                        constant_value = item.value.n
                                        if isinstance(constant_value, int):
                                            constant_type = 'int'
                                        else:
                                            constant_type = 'float'
                                    
                                    if constant_value is not None and constant_type:
                                        metadata['constants'][attr_name] = {
                                            'value': constant_value,
                                            'type': constant_type
                                        }
    except Exception as e:
        # If parsing fails, just return default metadata
        pass

    return metadata


def extract_variable_metadata(py_file: Path) -> dict:
    """Extract metadata from a Python variable file using AST parsing"""
    metadata = {
        'variable_name': None,
        'value_type': None,
        'default_value': None,
        'description': '',
        'icon': 'fa-variable',
        'category': 'general',
        'is_custom': False,
        'custom_import': None,
        'custom_type_hint': None,
        'tags': [],
        'is_readonly': False
    }

    try:
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the AST to find class definitions
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract docstring as description
                if (node.body and isinstance(node.body[0], ast.Expr) and 
                    isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                    if isinstance(node.body[0].value, ast.Constant):
                        metadata['description'] = node.body[0].value.value
                    else:  # ast.Str for older Python
                        metadata['description'] = node.body[0].value.s

                # Look for class attributes
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                attr_name = target.id

                                # Extract simple attributes
                                if attr_name in ['variable_name', 'value_type', 'description', 
                                               'icon', 'category', 'custom_import', 'custom_type_hint']:
                                    if isinstance(item.value, ast.Constant):
                                        metadata[attr_name] = item.value.value
                                    elif isinstance(item.value, ast.Str):  # Python < 3.8
                                        metadata[attr_name] = item.value.s

                                # Extract boolean attributes
                                elif attr_name in ['is_custom', 'is_readonly']:
                                    if isinstance(item.value, ast.Constant):
                                        metadata[attr_name] = bool(item.value.value)
                                    elif hasattr(item.value, 'value'):  # NameConstant
                                        metadata[attr_name] = bool(item.value.value)

                                # Extract default_value (could be various types)
                                elif attr_name == 'default_value':
                                    if isinstance(item.value, ast.Constant):
                                        metadata[attr_name] = item.value.value
                                    elif isinstance(item.value, ast.Str):
                                        metadata[attr_name] = item.value.s
                                    elif isinstance(item.value, ast.Num):
                                        metadata[attr_name] = item.value.n
                                    elif isinstance(item.value, ast.NameConstant):
                                        metadata[attr_name] = item.value.value
                                    elif isinstance(item.value, ast.Name) and item.value.id == 'None':
                                        metadata[attr_name] = None

                                # Extract tags list
                                elif attr_name == 'tags' and isinstance(item.value, ast.List):
                                    tags = []
                                    for elt in item.value.elts:
                                        if isinstance(elt, ast.Constant):
                                            tags.append(elt.value)
                                        elif isinstance(elt, ast.Str):
                                            tags.append(elt.s)
                                    metadata['tags'] = tags

                # Stop after first class (assuming one class per file)
                break

    except Exception as e:
        # If parsing fails, return default metadata
        print(f"Warning: Failed to parse variable file {py_file}: {e}")

    return metadata


@router.get("/nodes", response_model=List[NodeFile])
def list_nodes():
    """List all built-in and user nodes with metadata"""
    nodes = []

    # 1. Built-in nodes from the installed package
    builtin_nodes_dir = Path(__file__).parent.parent / "nodes"
    if builtin_nodes_dir.exists():
        for category_dir in builtin_nodes_dir.iterdir():
            if category_dir.is_dir() and category_dir.name != "__pycache__":
                for py_file in category_dir.glob("*.py"):
                    if py_file.name != "__init__.py":
                        metadata = extract_node_metadata(py_file)
                        nodes.append(NodeFile(
                            name=py_file.stem,
                            path=str(py_file),
                            type="builtin",
                            category=metadata.get('category', category_dir.name),
                            icon=metadata.get('icon'),
                            description=metadata.get('description'),
                            inputs=metadata.get('inputs', {}),
                            outputs=metadata.get('outputs', {}),
                            exec_input=metadata.get('exec_input', True),
                            exec_output=metadata.get('exec_output', True),
                            constants=metadata.get('constants', {})
                        ))

    # 2. User nodes from the working directory
    cwd = get_working_directory()
    user_nodes_dir = cwd / "nodes"
    if user_nodes_dir.exists():
        for py_file in user_nodes_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                metadata = extract_node_metadata(py_file)
                nodes.append(NodeFile(
                    name=py_file.stem,
                    path=str(py_file.relative_to(cwd)),
                    type="user",
                    category=metadata.get('category', 'other'),
                    icon=metadata.get('icon'),
                    description=metadata.get('description'),
                    inputs=metadata.get('inputs', {}),
                    outputs=metadata.get('outputs', {}),
                    exec_input=metadata.get('exec_input', True),
                    exec_output=metadata.get('exec_output', True),
                    constants=metadata.get('constants', {})
                ))
    else:
        # Create nodes directory if it doesn't exist
        user_nodes_dir.mkdir(parents=True, exist_ok=True)

    return nodes


def generate_variable_python_code(request: CreateVariableRequest) -> str:
    """Generate Python code for a variable class based on the request"""
    class_name = f"{request.variable_name.title().replace('_', '')}Variable"
    
    # Start building the code
    code_lines = [
        "from rayflow import RayflowVariable",
        "",
        f"class {class_name}(RayflowVariable):",
    ]
    
    # Add description as docstring if provided
    if request.description:
        code_lines.extend([
            f'    """{request.description}"""',
            ""
        ])
    
    # Required metadata
    code_lines.extend([
        f'    variable_name = "{request.variable_name}"',
        f'    value_type = "{request.value_type}"'
    ])
    
    # Default value handling
    if request.default_value is not None:
        # Parse the default value based on type
        if request.value_type == "str":
            code_lines.append(f'    default_value = "{request.default_value}"')
        elif request.value_type in ["int", "float", "bool"]:
            code_lines.append(f'    default_value = {request.default_value}')
        elif request.value_type in ["dict", "list"]:
            # For complex types, use the raw value (should be valid Python)
            code_lines.append(f'    default_value = {request.default_value}')
        else:  # custom or other
            code_lines.append(f'    default_value = {request.default_value}')
    else:
        code_lines.append('    default_value = None')
    
    # Optional metadata
    if request.description:
        code_lines.append(f'    description = "{request.description}"')
    
    if request.icon and request.icon != "fa-variable":
        code_lines.append(f'    icon = "{request.icon}"')
    
    if request.category and request.category != "general":
        code_lines.append(f'    category = "{request.category}"')
    
    # Custom type configuration
    if request.is_custom:
        code_lines.append('    is_custom = True')
        if request.custom_import:
            code_lines.append(f'    custom_import = "{request.custom_import}"')
        if request.custom_type_hint:
            code_lines.append(f'    custom_type_hint = "{request.custom_type_hint}"')
    
    # Tags
    if request.tags:
        tags_str = ', '.join([f'"{tag}"' for tag in request.tags])
        code_lines.append(f'    tags = [{tags_str}]')
    
    # Readonly
    if request.is_readonly:
        code_lines.append('    is_readonly = True')

@router.get("/variables", response_model=List[VariableFile])
def list_variables():
    """List all variables from the variables directory with metadata"""
    variables = []
    
    # Get working directory
    cwd = get_working_directory()
    variables_dir = cwd / "variables"
    
    if not variables_dir.exists():
        # Create variables directory if it doesn't exist
        variables_dir.mkdir(parents=True, exist_ok=True)
        return variables
    
    # Scan all Python files in variables directory
    for py_file in variables_dir.glob("*.py"):
        if py_file.name != "__init__.py":
            try:
                metadata = extract_variable_metadata(py_file)
                
                # Only include if variable_name was successfully extracted
                if metadata.get('variable_name'):
                    variables.append(VariableFile(
                        name=py_file.stem,
                        variable_name=metadata['variable_name'],
                        value_type=metadata.get('value_type', 'any'),
                        default_value=str(metadata.get('default_value')) if metadata.get('default_value') is not None else None,
                        description=metadata.get('description', ''),
                        icon=metadata.get('icon', 'fa-variable'),
                        category=metadata.get('category', 'general'),
                        is_custom=metadata.get('is_custom', False),
                        custom_import=metadata.get('custom_import'),
                        custom_type_hint=metadata.get('custom_type_hint'),
                        tags=metadata.get('tags', []),
                        is_readonly=metadata.get('is_readonly', False),
                        file_path=str(py_file.relative_to(cwd))
                    ))
            except Exception as e:
                print(f"Warning: Failed to process variable file {py_file}: {e}")
                continue
    
    return variables

    return '\n'.join(code_lines)


@router.post("/variables/create", response_model=CreateVariableResponse)
def create_variable(request: CreateVariableRequest):
    """Create a new variable file in the variables directory"""
    try:
        # Validate variable name
        if not request.variable_name.isidentifier():
            raise HTTPException(
                status_code=400, 
                detail="Variable name must be a valid Python identifier"
            )
        
        # Get working directory
        cwd = get_working_directory()
        variables_dir = cwd / "variables"
        
        # Create variables directory if it doesn't exist
        variables_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate file path
        file_path = variables_dir / f"{request.variable_name}.py"
        
        # Check if file already exists
        if file_path.exists():
            raise HTTPException(
                status_code=409, 
                detail=f"Variable '{request.variable_name}' already exists"
            )
        
        # Generate Python code
        python_code = generate_variable_python_code(request)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(python_code)
        
        return CreateVariableResponse(
            success=True,
            message=f"Variable '{request.variable_name}' created successfully",
            file_path=str(file_path.relative_to(cwd)),
            variable_name=request.variable_name
        )
        
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create variable: {str(e)}"
        )
