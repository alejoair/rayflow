from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PinKind(str, Enum):
    DATA = "data"
    EXEC = "exec"


@dataclass
class PinDef:
    name: str
    kind: PinKind
    # None for exec pins or an implicit Any type
    type: str | None = None
    # A static literal value, or a reference "node_id.pin_name"
    value: Any = None
    required: bool = False


@dataclass
class NodeDef:
    id: str
    type: str  # node name in the catalog
    # data inputs: name → literal value or "node_id.pin_name"
    inputs: dict[str, Any] = field(default_factory=dict)
    # exec input: None for entry nodes (is_entry=True), or "node_id" if it comes from another node
    exec_in: str | list[str] | dict | None = None
    # GraphState path this node belongs to. None = the root flow's.
    # Assigned by flatten() when expanding an isolated CallFlow: nodes in the
    # isolated subgraph point to their own state segment.
    state_path: str | None = None
    # Immediate splice-point CallFlow shell (a single hop up, like parentNode
    # in the DOM). Only carried by the boundary FlowInput/FlowOutput of a
    # spliced subgraph. None = a root-flow node. Assigned by flatten().
    subflow_of: str | None = None
    # Declared interface of the flow this boundary node belongs to:
    # {"inputs": {...}, "outputs": {...}}. Lets _with_dynamic_pins generate
    # the correct pins for a spliced FlowInput/FlowOutput (which no longer
    # match the root flow's interface). None = use the root flow's interface.
    iface: dict | None = None
    # Only on a CallFlow shell: id of the inline subgraph's entry node and of
    # the return FlowOutput. The shell orchestrates them at runtime: fires
    # subflow_entry (blocking), reads subflow_exit's outputs as 'result',
    # then continues its own exec_out (the parent's continuation).
    subflow_entry: str | None = None
    subflow_exit: str | None = None
    # Only on an isolated CallFlow shell: subflow variables to seed (lazily)
    # with a key prefixed by the subgraph's state_path on entry. List of
    # (name, default). Empty if the subflow shares state with its parent.
    subflow_vars: list = field(default_factory=list)
    # Name of the flow that DECLARED this node. For root-flow nodes it's the
    # root flow; for nodes of a spliced CallFlow it's the subflow's name.
    # Used by _build_meta for meta['flow']. None = root flow (resolved by
    # the engine).
    flow_name: str | None = None
    # Visual editor metadata: canvas position, comments, etc. Completely
    # ignored by the engine — only the editor reads/writes it.
    ui: dict | None = None


@dataclass
class VariableDef:
    name: str
    type: str
    default: Any = None


@dataclass
class FlowDef:
    name: str
    version: str = "1"
    # Public interface inputs/outputs: name → type
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    variables: list[VariableDef] = field(default_factory=list)
    # Events this flow may emit (informational)
    events: list[str] = field(default_factory=list)
    nodes: list[NodeDef] = field(default_factory=list)
