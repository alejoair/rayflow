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
        'exec_output': True
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
    except Exception as e:
        # If parsing fails, just return default metadata
        pass

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
                            exec_output=metadata.get('exec_output', True)
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
                    exec_output=metadata.get('exec_output', True)
                ))
    else:
        # Create nodes directory if it doesn't exist
        user_nodes_dir.mkdir(parents=True, exist_ok=True)

    return nodes
