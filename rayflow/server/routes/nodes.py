"""Node-related API endpoints."""

import ast
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


router = APIRouter()


class NodeFile(BaseModel):
    """Model representing a node file with its metadata."""
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


class NodeSourceResponse(BaseModel):
    """Response model for getting node source code."""
    content: str
    path: str
    writable: bool
    file_name: str


class NodeSourceUpdateRequest(BaseModel):
    """Request model for updating node source code."""
    file_path: str
    content: str


class NodeSourceUpdateResponse(BaseModel):
    """Response model for node source update."""
    success: bool
    message: str
    errors: List[str] = []
    backup_path: Optional[str] = None


def extract_node_metadata(py_file: Path) -> dict:
    """Extract metadata (icon, category, description, inputs, outputs, exec config) from a Python node file."""
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


@router.get("/nodes", response_model=List[NodeFile])
def list_nodes(working_dir: Path):
    """List all built-in and user nodes with metadata."""
    nodes = []

    # 1. Built-in nodes from the installed package
    builtin_nodes_dir = Path(__file__).parent.parent.parent / "nodes"
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
    user_nodes_dir = working_dir / "nodes"
    if user_nodes_dir.exists():
        for py_file in user_nodes_dir.glob("*.py"):
            if py_file.name != "__init__.py":
                metadata = extract_node_metadata(py_file)
                nodes.append(NodeFile(
                    name=py_file.stem,
                    path=str(py_file.relative_to(working_dir)),
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


@router.get("/nodes/source", response_model=NodeSourceResponse)
def get_node_source(file_path: str, working_dir: Path):
    """Get the source code of a node file."""
    try:
        # Security: Validate that the file is within allowed directories
        requested_path = Path(file_path)

        # Check if it's a relative path from working directory (user nodes)
        if not requested_path.is_absolute():
            full_path = working_dir / requested_path
            is_user_node = True
        else:
            full_path = requested_path
            # Check if it's a builtin node
            builtin_nodes_dir = Path(__file__).parent.parent.parent / "nodes"
            is_user_node = not full_path.is_relative_to(builtin_nodes_dir)

        # Validate file exists and is a Python file
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if full_path.suffix != ".py":
            raise HTTPException(status_code=400, detail="Only Python files are allowed")

        # Security: Prevent path traversal outside allowed directories
        if is_user_node:
            user_nodes_dir = working_dir / "nodes"
            if not full_path.is_relative_to(user_nodes_dir):
                raise HTTPException(status_code=403, detail="Access denied: File is outside nodes directory")

        # Read the file content
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return NodeSourceResponse(
            content=content,
            path=str(full_path.relative_to(working_dir) if is_user_node else full_path),
            writable=is_user_node,  # Only user nodes are writable
            file_name=full_path.name
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@router.post("/nodes/source", response_model=NodeSourceUpdateResponse)
def update_node_source(request: NodeSourceUpdateRequest, working_dir: Path):
    """Update the source code of a custom (user) node file."""
    try:
        # Parse the file path
        requested_path = Path(request.file_path)

        # Resolve to full path
        if not requested_path.is_absolute():
            full_path = working_dir / requested_path
        else:
            full_path = requested_path

        # Security: Only allow editing user nodes in the nodes directory
        user_nodes_dir = working_dir / "nodes"
        if not full_path.is_relative_to(user_nodes_dir):
            raise HTTPException(
                status_code=403,
                detail="Access denied: Can only edit custom nodes in the nodes directory"
            )

        # Validate file exists
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if full_path.suffix != ".py":
            raise HTTPException(status_code=400, detail="Only Python files are allowed")

        # Validate Python syntax
        errors = []
        try:
            ast.parse(request.content)
        except SyntaxError as e:
            errors.append(f"Syntax error at line {e.lineno}: {e.msg}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid Python syntax: {e.msg} at line {e.lineno}"
            )

        # Validate that the file contains a class that inherits from RayflowNode
        try:
            tree = ast.parse(request.content)
            has_rayflow_node = False
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if any base class is RayflowNode
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "RayflowNode":
                            has_rayflow_node = True
                            break
                    if has_rayflow_node:
                        break

            if not has_rayflow_node:
                errors.append("File must contain a class that inherits from RayflowNode")
                raise HTTPException(
                    status_code=400,
                    detail="File must contain a class that inherits from RayflowNode"
                )
        except HTTPException:
            raise
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")

        # Create backup before saving
        backup_path = full_path.with_suffix('.py.backup')
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
        except Exception as e:
            # Backup failure should not prevent save, but warn
            backup_path = None
            print(f"Warning: Failed to create backup: {e}")

        # Write the new content
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(request.content)

        return NodeSourceUpdateResponse(
            success=True,
            message=f"Successfully updated {full_path.name}",
            errors=errors,
            backup_path=str(backup_path.relative_to(working_dir)) if backup_path else None
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update file: {str(e)}"
        )
