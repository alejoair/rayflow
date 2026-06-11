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
    # None para pins exec o tipo Any implícito
    type: str | None = None
    # Valor literal estático o referencia "node_id.pin_name"
    value: Any = None
    required: bool = False


@dataclass
class NodeDef:
    id: str
    type: str  # nombre del nodo en el catálogo
    # data inputs: nombre → valor literal o "node_id.pin_name"
    inputs: dict[str, Any] = field(default_factory=dict)
    # exec input: None si OnStart/OnEvent, o "node_id" si viene de otro nodo
    exec_in: str | list[str] | None = None


@dataclass
class VariableDef:
    name: str
    type: str
    default: Any = None


@dataclass
class FlowDef:
    name: str
    version: str = "1"
    # Inputs/outputs de la interfaz pública: nombre → tipo
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    variables: list[VariableDef] = field(default_factory=list)
    # Eventos que este flow puede emitir (informativo)
    events: list[str] = field(default_factory=list)
    nodes: list[NodeDef] = field(default_factory=list)
