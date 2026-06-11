from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rayflow.schema.models import FlowDef, NodeDef
from rayflow.nodes.loader import NodeCatalog
from rayflow.nodes.decorators import NodeMeta, _MISSING
from rayflow.types import (
    compatible as type_compatible,
    parse_type,
    TypeError_,
)


class BuildError(Exception):
    pass


# ---------------------------------------------------------------------------
# Estructura ejecutable producida por el build
# ---------------------------------------------------------------------------

@dataclass
class ResolvedPin:
    """Un data input ya resuelto: referencia a otro nodo o valor literal."""
    is_ref: bool
    # Si is_ref: fuente "node_id.pin_name"
    source_node: str | None = None
    source_pin: str | None = None
    # Si no is_ref: valor literal
    literal: Any = None


@dataclass
class ResolvedNode:
    node_def: NodeDef
    node_cls: type
    meta: NodeMeta
    # data inputs resueltos
    resolved_inputs: dict[str, ResolvedPin] = field(default_factory=dict)
    # exec predecessors (node_ids que disparan a este)
    exec_sources: list[str] = field(default_factory=list)
    # exec outputs → lista de node_ids destino (fan-out: uno o varios)
    exec_targets: dict[str, list[str]] = field(default_factory=dict)

    @property
    def state_path(self) -> str | None:
        """Ruta del GraphState al que pertenece. None = el del flow raíz."""
        return self.node_def.state_path


@dataclass
class BuiltFlow:
    flow_def: FlowDef
    nodes: dict[str, ResolvedNode]  # node_id → ResolvedNode
    entry_node_id: str  # OnStart / FlowInput / OnEvent
    output_node_ids: list[str]  # FlowOutput nodes (puede haber varios)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def build(flow: FlowDef, catalog: NodeCatalog) -> BuiltFlow:
    """Valida el flow y produce un BuiltFlow ejecutable."""
    flow = flatten(flow, catalog)
    nodes = _index_nodes(flow, catalog)
    _validate_declared_types(flow, nodes)
    _validate_exec_inputs(flow, nodes)
    _validate_data_inputs(flow, nodes, catalog)
    _validate_acyclicity(nodes)
    entry = _find_entry(nodes)
    outputs = _find_outputs(nodes)
    return BuiltFlow(flow_def=flow, nodes=nodes, entry_node_id=entry, output_node_ids=outputs)


# ---------------------------------------------------------------------------
# Flatten — expande recursivamente los CallFlow en un único grafo plano
# ---------------------------------------------------------------------------

# Separador del namespace plano. Los ids resultantes son rutas de procedencia
# estilo S3: "padre/cf/add_1". No hay contenedores reales — solo nombres.
SEP = "/"


def flatten(flow: FlowDef, catalog: NodeCatalog, prefix: str = "",
            state_path: str | None = None) -> FlowDef:
    """Expande recursivamente los nodos CallFlow en un único grafo plano.

    Cada CallFlow estático se reemplaza por el grafo de su subflow, con todos
    los ids prefijados con "{callflow_id}/". El resultado es un FlowDef sin
    ningún CallFlow: todo es un namespace plano de procedencia (estilo S3).

    No se inventan tipos de nodo nuevos. El FlowInput/FlowOutput que el subflow
    ya declara se reusan como puntos de empalme, marcados con `subflow_of`
    apuntando a su CallFlow shell inmediato (un salto, como parentNode en el DOM).

    - prefix: ruta acumulada que prefija los ids de este nivel.
    - state_path: GraphState al que pertenecen los nodos de este nivel
      (None = el del flow raíz). Un CallFlow isolated abre un state_path nuevo.
    """
    from rayflow.schema.loader import load_flow

    out_nodes: list[NodeDef] = []

    for nd in flow.nodes:
        full_id = _join(prefix, nd.id)

        if nd.type != "CallFlow":
            out_nodes.append(_reparent_node(nd, prefix, full_id, state_path, flow.name))
            continue

        # --- Splice de un CallFlow ---
        sub_src = nd.inputs.get("flow")
        if sub_src is None or (isinstance(sub_src, str) and "." in sub_src):
            raise BuildError(
                f"CallFlow '{full_id}': el input 'flow' debe ser un subflow "
                f"estático (dict o ruta), no una referencia dinámica"
            )
        sub_flow = load_flow(sub_src)
        isolated = bool(nd.inputs.get("isolated", False))

        # Estado del subgrafo: propio si isolated, heredado si compartido.
        sub_state = full_id if isolated else state_path

        # Aplanar el subgrafo recursivamente bajo el prefijo del CallFlow.
        # subflow_of = full_id es el padre INMEDIATO: en una recursión más
        # profunda, los niveles internos ya recibieron el suyo propio.
        sub_flat = flatten(sub_flow, catalog, prefix=full_id, state_path=sub_state)
        sub_nodes, entry_id, exit_id = _splice_subflow(sub_flat, full_id, nd, sub_flow)

        # El shell conserva su exec_in y su exec_out (la continuación del padre).
        # En runtime dispara subflow_entry (bloqueante), lee subflow_exit como
        # 'result', y luego sigue exec_out. El subgrafo NO se cablea al exec_out
        # del shell: el shell lo orquesta explícitamente vía subflow_entry.
        # Si es aislado, el shell siembra (lazy) las variables del subflow con
        # clave prefijada por sub_state. Si comparte, las variables ya están en
        # el namespace del padre — nada que sembrar.
        sub_vars = [(v.name, v.default) for v in sub_flow.variables] if isolated else []

        shell = NodeDef(
            id=full_id,
            type="CallFlow",
            inputs=_reparent_inputs(nd.inputs, prefix),
            exec_in=_reparent_exec_in(nd.exec_in, prefix),
            state_path=state_path,
            subflow_entry=entry_id,
            subflow_exit=exit_id,
            subflow_vars=sub_vars,
            flow_name=flow.name,
        )
        out_nodes.append(shell)
        out_nodes.extend(sub_nodes)

    return FlowDef(
        name=flow.name,
        version=flow.version,
        inputs=flow.inputs,
        outputs=flow.outputs,
        variables=flow.variables,
        events=flow.events,
        nodes=out_nodes,
    )


def _join(prefix: str, node_id: str) -> str:
    return f"{prefix}{SEP}{node_id}" if prefix else node_id


def _reparent_ref(ref: str, prefix: str) -> str:
    """Prefija una referencia "node_id" o "node_id.pin" con el prefijo del nivel."""
    if not prefix:
        return ref
    if "." in ref:
        node_id, pin = ref.split(".", 1)
        return f"{_join(prefix, node_id)}.{pin}"
    return _join(prefix, ref)


def _reparent_inputs(inputs: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Prefija las referencias en los inputs; deja literales y subflows intactos."""
    out: dict[str, Any] = {}
    for k, v in inputs.items():
        # 'flow' puede ser un dict (subflow inline) — nunca es una referencia.
        if k == "flow":
            out[k] = v
        elif isinstance(v, str) and "." in v:
            out[k] = _reparent_ref(v, prefix)
        else:
            out[k] = v
    return out


def _reparent_exec_in(exec_in, prefix: str):
    if exec_in is None:
        return None
    if isinstance(exec_in, str):
        return _reparent_ref(exec_in, prefix)
    return [_reparent_ref(e, prefix) for e in exec_in]


def _reparent_node(nd: NodeDef, prefix: str, full_id: str,
                   state_path: str | None, flow_name: str | None) -> NodeDef:
    return NodeDef(
        id=full_id,
        type=nd.type,
        inputs=_reparent_inputs(nd.inputs, prefix),
        exec_in=_reparent_exec_in(nd.exec_in, prefix),
        state_path=nd.state_path if nd.state_path is not None else state_path,
        subflow_of=nd.subflow_of,
        # Preserva el flow_name de una recursión más profunda; si no, el de este nivel.
        flow_name=nd.flow_name if nd.flow_name is not None else flow_name,
        subflow_entry=nd.subflow_entry,
        subflow_exit=nd.subflow_exit,
        subflow_vars=nd.subflow_vars,
        iface=nd.iface,
    )


def _splice_subflow(sub_flat: FlowDef, cf_id: str, cf_def: NodeDef,
                    sub_flow: FlowDef) -> tuple[list[NodeDef], str, str | None]:
    """Empalma un subflow ya aplanado en el grafo del padre.

    Reusa el FlowInput/OnStart y el FlowOutput que el subflow ya declara —
    no crea nodos nuevos. Marca el entry/exit de ESTE nivel con `subflow_of = cf_id`
    para que el flow raíz no los trate como su entrada/salida:
    - entry: lo dispara el CallFlow shell vía subflow_entry; sus inputs vienen del CallFlow.
    - exit: no cierra el flow; el shell recoge sus inputs como 'result'.

    Devuelve (nodes, entry_id, exit_id). Los nodos de niveles más profundos ya
    llevan su propio subflow_of de la recursión, así que se identifican los de
    este nivel por subflow_of is None.
    """
    nodes = list(sub_flat.nodes)
    extra = {k: v for k, v in cf_def.inputs.items() if k not in ("flow", "isolated")}
    input_names = set(sub_flow.inputs.keys())
    sub_iface = {"inputs": dict(sub_flow.inputs), "outputs": dict(sub_flow.outputs)}

    entry_id: str | None = None
    exit_id: str | None = None

    for nd in nodes:
        if nd.subflow_of is not None:
            continue  # nodo de un subgrafo más profundo — ya empalmado
        if nd.type in ("FlowInput", "OnStart", "OnEvent"):
            entry_id = nd.id
            nd.subflow_of = cf_id
            nd.iface = sub_iface
            # El shell dispara el entry directamente — sin arista exec entrante.
            nd.exec_in = None
            for name in input_names:
                if name in extra:
                    nd.inputs[name] = extra[name]
        elif nd.type == "FlowOutput":
            exit_id = nd.id
            nd.subflow_of = cf_id
            nd.iface = sub_iface

    if entry_id is None:
        raise BuildError(f"CallFlow '{cf_id}': el subflow no tiene nodo de entrada")

    return nodes, entry_id, exit_id


def _validate_declared_types(flow: FlowDef, nodes: dict[str, ResolvedNode]) -> None:
    """Rechaza cualquier tipo fuera del registro cerrado (incl. interfaz pública)."""
    def check(type_spec, where: str):
        if type_spec is None:
            return
        try:
            parse_type(type_spec)
        except TypeError_ as e:
            raise BuildError(f"{where}: {e}")

    for name, t in flow.inputs.items():
        check(t, f"flow input '{name}'")
    for name, t in flow.outputs.items():
        check(t, f"flow output '{name}'")
    for nid, rnode in nodes.items():
        for pin in rnode.meta.inputs:
            check(pin.type, f"nodo '{nid}', input '{pin.name}'")
        for pin in rnode.meta.outputs:
            check(pin.type, f"nodo '{nid}', output '{pin.name}'")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _index_nodes(flow: FlowDef, catalog: NodeCatalog) -> dict[str, ResolvedNode]:
    nodes: dict[str, ResolvedNode] = {}
    for node_def in flow.nodes:
        entry = catalog.get(node_def.type)
        if entry is None:
            raise BuildError(f"Nodo '{node_def.type}' (id={node_def.id}) no está en el catálogo")
        cls, meta = entry
        # Copia local de la metadata para inyectar pins dinámicos sin mutar
        # la metadata global del catálogo.
        meta = _with_dynamic_pins(meta, flow, node_def)
        nodes[node_def.id] = ResolvedNode(node_def=node_def, node_cls=cls, meta=meta)
    return nodes


def _with_dynamic_pins(meta: NodeMeta, flow: FlowDef, node_def=None) -> NodeMeta:
    """Genera los pins dinámicos de los nodos de interfaz pública.

    - FlowInput / OnEvent: data outputs = inputs declarados del flow.
    - FlowOutput: data inputs = outputs declarados del flow.
    - CallFlow: data inputs extra = cualquier key en node_def.inputs que no esté
      declarado como pin. Permite pasar inputs arbitrarios al subflow.
    """
    import copy
    from rayflow.nodes.decorators import PinSpec

    # Para nodos de frontera de un subgrafo spliced, la interfaz viene anotada
    # en node_def.iface (los inputs/outputs del subflow, no los del flow raíz).
    iface = node_def.iface if node_def is not None else None
    flow_inputs = iface["inputs"] if iface else flow.inputs
    flow_outputs = iface["outputs"] if iface else flow.outputs

    if meta.name in ("FlowInput", "OnEvent"):
        meta = copy.copy(meta)
        meta.outputs = list(meta.outputs) + [
            PinSpec(name=name, kind="data_out", type=type_str)
            for name, type_str in flow_inputs.items()
        ]
        # En un FlowInput spliced, los mismos nombres son también data inputs:
        # entran del CallFlow y se reexponen como outputs al subgrafo.
        if node_def is not None and node_def.subflow_of is not None:
            meta.inputs = list(meta.inputs) + [
                PinSpec(name=name, kind="data_in", type=type_str, default=None)
                for name, type_str in flow_inputs.items()
            ]
    elif meta.name == "FlowOutput":
        meta = copy.copy(meta)
        meta.inputs = list(meta.inputs) + [
            PinSpec(name=name, kind="data_in", type=type_str, default=None, required=True)
            for name, type_str in flow_outputs.items()
        ]
    elif meta.name == "CallFlow" and node_def is not None:
        declared = {p.name for p in meta.inputs}
        extra = [
            PinSpec(name=name, kind="data_in", type="Any", default=None)
            for name in node_def.inputs
            if name not in declared
        ]
        if extra:
            meta = copy.copy(meta)
            meta.inputs = list(meta.inputs) + extra
    return meta


def _validate_exec_inputs(flow: FlowDef, nodes: dict[str, ResolvedNode]) -> None:
    """Valida: todo exec input tiene exactamente una arista entrante.

    Una arista exec se declara desde el consumidor con `exec_in`:
    - "node_id"            -> el exec output por defecto del nodo fuente.
    - "node_id.pin_name"   -> un exec output concreto (Branch.true, Sequence.then_0…).
    """
    incoming_exec: dict[str, list[str]] = {nid: [] for nid in nodes}

    for nid, rnode in nodes.items():
        exec_in = rnode.node_def.exec_in
        if exec_in is None:
            if rnode.meta.has_exec_in:
                raise BuildError(
                    f"Nodo '{rnode.meta.name}' (id={nid}) requiere exec input pero no tiene arista"
                )
            continue

        sources = [exec_in] if isinstance(exec_in, str) else exec_in
        for src in sources:
            src_id, src_pin = _parse_exec_ref(src, nodes)
            if src_id not in nodes:
                raise BuildError(
                    f"Nodo '{nid}': exec_in apunta a '{src_id}' que no existe en el grafo"
                )
            incoming_exec[nid].append(src_id)
            rnode.exec_sources.append(src_id)
            nodes[src_id].exec_targets.setdefault(src_pin, []).append(nid)


def _parse_exec_ref(ref: str, nodes: dict[str, ResolvedNode]) -> tuple[str, str]:
    """Resuelve "node_id" o "node_id.pin" -> (node_id, exec_out_pin)."""
    if "." in ref:
        src_id, src_pin = ref.split(".", 1)
        return src_id, src_pin

    src_id = ref
    src_rnode = nodes.get(src_id)
    if src_rnode is None:
        return src_id, "exec_out"

    exec_outs = src_rnode.meta.exec_outputs
    if len(exec_outs) == 1:
        return src_id, exec_outs[0]
    if len(exec_outs) > 1:
        raise BuildError(
            f"La fuente exec '{src_id}' ({src_rnode.meta.name}) tiene varios exec outputs "
            f"{exec_outs}; especifica cuál con 'node_id.pin_name'"
        )
    return src_id, "exec_out"


def _validate_data_inputs(
    flow: FlowDef, nodes: dict[str, ResolvedNode], catalog: NodeCatalog
) -> None:
    """Valida tipos en aristas de datos y que inputs requeridos estén cubiertos."""
    for nid, rnode in nodes.items():
        meta = rnode.meta
        node_inputs_raw = rnode.node_def.inputs

        for pin_spec in meta.inputs:
            raw = node_inputs_raw.get(pin_spec.name, _MISSING)

            if raw is _MISSING:
                if pin_spec.required:
                    raise BuildError(
                        f"Nodo '{nid}' (type={rnode.meta.name}): "
                        f"pin '{pin_spec.name}' es requerido pero no tiene valor ni arista"
                    )
                # Usa default del pin — no hay arista
                rnode.resolved_inputs[pin_spec.name] = ResolvedPin(
                    is_ref=False, literal=pin_spec.default
                )
                continue

            if isinstance(raw, str) and "." in raw:
                # Referencia a otro nodo: "source_id.pin_name"
                parts = raw.split(".", 1)
                src_id, src_pin = parts[0], parts[1]
                if src_id not in nodes:
                    raise BuildError(
                        f"Nodo '{nid}': pin '{pin_spec.name}' referencia '{src_id}' que no existe"
                    )
                src_meta = nodes[src_id].meta
                # Buscar el output pin en la fuente
                src_out = next(
                    (p for p in src_meta.outputs if p.name == src_pin), None
                )
                if src_out is None and src_pin == "meta":
                    # Output implícito inyectado por el engine en todos los nodos.
                    producer_type = "dict"
                elif src_out is None:
                    # Output dinámico (FlowInput/OnEvent): el tipo declarado vive
                    # en flow.inputs. Validamos contra él si está disponible.
                    producer_type = flow.inputs.get(src_pin)
                else:
                    producer_type = src_out.type

                if producer_type is not None and pin_spec.type is not None:
                    try:
                        ok = type_compatible(pin_spec.type, producer_type)
                    except TypeError_ as e:
                        raise BuildError(
                            f"Nodo '{nid}', pin '{pin_spec.name}': tipo inválido ({e})"
                        )
                    if not ok:
                        raise BuildError(
                            f"Nodo '{nid}': pin '{pin_spec.name}' "
                            f"({parse_type(pin_spec.type)}) incompatible con "
                            f"'{src_id}.{src_pin}' ({parse_type(producer_type)}). "
                            f"Usa un nodo de casteo explícito (ToInt, ToFloat, ToStr, ToBool)."
                        )
                rnode.resolved_inputs[pin_spec.name] = ResolvedPin(
                    is_ref=True, source_node=src_id, source_pin=src_pin
                )
            else:
                # Valor literal
                rnode.resolved_inputs[pin_spec.name] = ResolvedPin(is_ref=False, literal=raw)




def _validate_acyclicity(nodes: dict[str, ResolvedNode]) -> None:
    """Detecta ciclos en el subgrafo de datos y en el plano de ejecución."""
    _check_data_cycles(nodes)
    _check_exec_cycles(nodes)


def _check_data_cycles(nodes: dict[str, ResolvedNode]) -> None:
    # DFS sobre aristas de datos
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(nid: str):
        color[nid] = GRAY
        for pin_res in nodes[nid].resolved_inputs.values():
            if pin_res.is_ref and pin_res.source_node:
                src = pin_res.source_node
                if color[src] == GRAY:
                    raise BuildError(
                        f"Ciclo de datos detectado: '{src}' → ... → '{nid}'"
                    )
                if color[src] == WHITE:
                    dfs(src)
        color[nid] = BLACK

    for nid in nodes:
        if color[nid] == WHITE:
            dfs(nid)


def _check_exec_cycles(nodes: dict[str, ResolvedNode]) -> None:
    # DFS sobre aristas exec (exec_targets es dict[str, list[str]])
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(nid: str):
        color[nid] = GRAY
        for target_ids in nodes[nid].exec_targets.values():
            for target_id in target_ids:
                if color[target_id] == GRAY:
                    raise BuildError(
                        f"Ciclo de ejecución detectado: '{target_id}' → ... → '{nid}'"
                    )
                if color[target_id] == WHITE:
                    dfs(target_id)
        color[nid] = BLACK

    for nid in nodes:
        if color[nid] == WHITE:
            dfs(nid)


def _find_entry(nodes: dict[str, ResolvedNode]) -> str:
    # Los entry/output de subgrafos spliced llevan subflow_of: no cuentan como
    # entrada/salida del flow raíz.
    entry_types = {"OnStart", "FlowInput", "OnEvent"}
    entries = [
        nid for nid, rn in nodes.items()
        if rn.meta.name in entry_types and rn.node_def.subflow_of is None
    ]
    if not entries:
        raise BuildError("El flow no tiene nodo de entrada (OnStart, FlowInput u OnEvent)")
    if len(entries) > 1:
        raise BuildError(f"El flow tiene más de un nodo de entrada: {entries}")
    return entries[0]


def _find_outputs(nodes: dict[str, ResolvedNode]) -> list[str]:
    return [
        nid for nid, rn in nodes.items()
        if rn.meta.name == "FlowOutput" and rn.node_def.subflow_of is None
    ]
