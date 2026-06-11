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
    # Ruta del GraphState al que pertenece este nodo. None = el del flow raíz.
    # Asignado por flatten() al expandir un CallFlow isolated: los nodos del
    # subgrafo aislado apuntan a su propio segmento de estado.
    state_path: str | None = None
    # CallFlow shell de empalme inmediato (un solo salto hacia arriba, como
    # parentNode en el DOM). Solo lo llevan los FlowInput/FlowOutput de frontera
    # de un subgrafo spliced. None = nodo del flow raíz. Asignado por flatten().
    subflow_of: str | None = None
    # Interfaz declarada del flow al que pertenece este nodo de frontera:
    # {"inputs": {...}, "outputs": {...}}. Permite que _with_dynamic_pins genere
    # los pins correctos de un FlowInput/FlowOutput spliced (que ya no coinciden
    # con la interfaz del flow raíz). None = usar la interfaz del flow raíz.
    iface: dict | None = None
    # Solo en un CallFlow shell: id del nodo de entrada del subgrafo inline y del
    # FlowOutput de retorno. El shell los orquesta en runtime: dispara
    # subflow_entry (bloqueante), lee los outputs de subflow_exit como 'result',
    # y luego sigue su propio exec_out (la continuación del padre).
    subflow_entry: str | None = None
    subflow_exit: str | None = None


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
