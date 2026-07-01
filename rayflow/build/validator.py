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


class _Errors:
    """Build-error collector with two modes.

    - collect=False (default): every `add()` raises BuildError immediately.
      This is build()'s historical behavior — fails on the first error.
    - collect=True: every `add()` accumulates the message and validation
      continues, so an LLM (via validate_all/`POST /editor/validate`)
      receives ALL the problems in a single pass instead of one per round-trip.
    """

    def __init__(self, collect: bool = False):
        self.collect = collect
        self.items: list[str] = []

    def add(self, msg: str) -> None:
        if self.collect:
            self.items.append(msg)
        else:
            raise BuildError(msg)


# ---------------------------------------------------------------------------
# Executable structure produced by the build
# ---------------------------------------------------------------------------

@dataclass
class ResolvedPin:
    """An already-resolved data input: a reference to another node, or a literal value."""
    is_ref: bool
    # If is_ref: the source "node_id.pin_name"
    source_node: str | None = None
    source_pin: str | None = None
    # If not is_ref: the literal value
    literal: Any = None


@dataclass
class ResolvedNode:
    node_def: NodeDef
    node_cls: type
    meta: NodeMeta
    # resolved data inputs
    resolved_inputs: dict[str, ResolvedPin] = field(default_factory=dict)
    # exec predecessors (node_ids that fire into this one)
    exec_sources: list[str] = field(default_factory=list)
    # exec outputs → list of target node_ids (fan-out: one or several)
    exec_targets: dict[str, list[str]] = field(default_factory=dict)
    # semantics of multiple exec_in: "and" (wait for all) | "or" (first to arrive)
    exec_join: str = "and"

    @property
    def state_path(self) -> str | None:
        """GraphState path this node belongs to. None = the root flow's."""
        return self.node_def.state_path


@dataclass
class BuiltFlow:
    flow_def: FlowDef
    nodes: dict[str, ResolvedNode]  # node_id → ResolvedNode
    entry_node_id: str  # OnStart / FlowInput / OnEvent
    output_node_ids: list[str]  # FlowOutput nodes (there can be several)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def build(flow: FlowDef, catalog: NodeCatalog) -> BuiltFlow:
    """Validates the flow and produces an executable BuiltFlow (fails on the first error)."""
    err = _Errors(collect=False)
    flow = flatten(flow, catalog)
    nodes = _index_nodes(flow, catalog, err)
    _validate_declared_types(flow, nodes, err)
    _validate_exec_inputs(flow, nodes, err)
    _validate_data_inputs(flow, nodes, catalog, err)
    _validate_acyclicity(nodes, err)
    entry = _find_entry(nodes, err)
    outputs = _find_outputs(nodes)
    return BuiltFlow(flow_def=flow, nodes=nodes, entry_node_id=entry, output_node_ids=outputs)


def validate_all(flow: FlowDef, catalog: NodeCatalog) -> list[str]:
    """Validates a flow, collecting ALL errors instead of failing on the first one.

    Meant for clients that iterate (the visual editor, LLM agents): a single
    call returns the complete list of problems. Returns [] if valid.

    `flatten` can fail unrecoverably (a badly-referenced CallFlow makes it
    impossible to build the graph); in that case that single error is
    returned, since the later stages would have no graph to operate on.
    """
    err = _Errors(collect=True)
    try:
        flow = flatten(flow, catalog)
    except BuildError as e:
        return [str(e)]
    nodes = _index_nodes(flow, catalog, err)
    _validate_declared_types(flow, nodes, err)
    _validate_exec_inputs(flow, nodes, err)
    _validate_data_inputs(flow, nodes, catalog, err)
    _validate_acyclicity(nodes, err)
    _find_entry(nodes, err)
    return err.items


# ---------------------------------------------------------------------------
# Flatten — recursively expands CallFlow nodes into a single flat graph
# ---------------------------------------------------------------------------

# Flat namespace separator. The resulting ids are S3-style provenance paths:
# "parent/cf/add_1". There are no real containers — just names.
SEP = "/"


def flatten(flow: FlowDef, catalog: NodeCatalog, prefix: str = "",
            state_path: str | None = None) -> FlowDef:
    """Recursively expands CallFlow nodes into a single flat graph.

    Each static CallFlow is replaced by its subflow's graph, with every id
    prefixed by "{callflow_id}/". The result is a FlowDef with no CallFlow
    nodes left: everything is a flat namespace of provenance (S3-style).

    No new node types are invented. The FlowInput/FlowOutput the subflow
    already declares are reused as splice points, marked with `subflow_of`
    pointing at their immediate CallFlow shell (one hop, like parentNode in
    the DOM).

    - prefix: the accumulated path prefixing this level's ids.
    - state_path: the GraphState this level's nodes belong to (None = the
      root flow's). An isolated CallFlow opens a new state_path.
    """
    from rayflow.schema.loader import load_flow

    out_nodes: list[NodeDef] = []

    for nd in flow.nodes:
        full_id = _join(prefix, nd.id)

        if nd.type != "CallFlow":
            out_nodes.append(_reparent_node(nd, prefix, full_id, state_path, flow.name))
            continue

        # --- Splicing a CallFlow ---
        sub_src = nd.inputs.get("flow")
        if sub_src is None or (isinstance(sub_src, str) and "." in sub_src):
            raise BuildError(
                f"CallFlow '{full_id}': the 'flow' input must be a static "
                f"subflow (a dict or a path), not a dynamic reference"
            )
        sub_flow = load_flow(sub_src)
        isolated = bool(nd.inputs.get("isolated", False))

        # Subgraph state: its own if isolated, inherited if shared.
        sub_state = full_id if isolated else state_path

        # Recursively flatten the subgraph under the CallFlow's prefix.
        # subflow_of = full_id is the IMMEDIATE parent: in a deeper
        # recursion, the inner levels already got their own.
        sub_flat = flatten(sub_flow, catalog, prefix=full_id, state_path=sub_state)
        sub_nodes, entry_id, exit_id = _splice_subflow(sub_flat, full_id, nd, sub_flow)

        # The shell keeps its own exec_in and exec_out (the parent's
        # continuation). At runtime it fires subflow_entry (blocking), reads
        # subflow_exit as 'result', then continues with exec_out. The
        # subgraph is NOT wired to the shell's exec_out: the shell
        # orchestrates it explicitly via subflow_entry. If isolated, the
        # shell lazily seeds the subflow's variables with a key prefixed by
        # sub_state. If shared, the variables are already in the parent's
        # namespace — nothing to seed.
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
    """Prefixes a "node_id" or "node_id.pin" reference with this level's prefix."""
    if not prefix:
        return ref
    if "." in ref:
        node_id, pin = ref.split(".", 1)
        return f"{_join(prefix, node_id)}.{pin}"
    return _join(prefix, ref)


def _reparent_inputs(inputs: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Prefixes references inside inputs; leaves literals and subflows untouched."""
    out: dict[str, Any] = {}
    for k, v in inputs.items():
        # 'flow' can be a dict (an inline subflow) — never a reference.
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
    if isinstance(exec_in, dict):
        return {"or": [_reparent_ref(e, prefix) for e in exec_in["or"]]}
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
        # Preserves flow_name from a deeper recursion; otherwise this level's.
        flow_name=nd.flow_name if nd.flow_name is not None else flow_name,
        subflow_entry=nd.subflow_entry,
        subflow_exit=nd.subflow_exit,
        subflow_vars=nd.subflow_vars,
        iface=nd.iface,
    )


def _splice_subflow(sub_flat: FlowDef, cf_id: str, cf_def: NodeDef,
                    sub_flow: FlowDef) -> tuple[list[NodeDef], str, str | None]:
    """Splices an already-flattened subflow into the parent graph.

    Reuses the FlowInput/OnStart and FlowOutput the subflow already declares
    — doesn't create new nodes. Marks THIS level's entry/exit with
    `subflow_of = cf_id` so the root flow doesn't treat them as its own
    entry/exit:
    - entry: fired by the CallFlow shell via subflow_entry; its inputs come from the CallFlow.
    - exit: doesn't close the flow; the shell collects its inputs as 'result'.

    Returns (nodes, entry_id, exit_id). Nodes from deeper levels already
    carry their own subflow_of from the recursion, so this level's nodes are
    identified by subflow_of is None.
    """
    nodes = list(sub_flat.nodes)
    extra = {k: v for k, v in cf_def.inputs.items() if k not in ("flow", "isolated")}
    input_names = set(sub_flow.inputs.keys())
    sub_iface = {"inputs": dict(sub_flow.inputs), "outputs": dict(sub_flow.outputs)}

    entry_id: str | None = None
    exit_id: str | None = None

    for nd in nodes:
        if nd.subflow_of is not None:
            continue  # a node from a deeper subgraph — already spliced
        if nd.type in ("OnStart", "OnEvent"):
            entry_id = nd.id
            nd.subflow_of = cf_id
            nd.iface = sub_iface
            # The shell fires the entry directly — no incoming exec edge.
            nd.exec_in = None
            for name in input_names:
                if name in extra:
                    nd.inputs[name] = extra[name]
        elif nd.type == "FlowOutput":
            exit_id = nd.id
            nd.subflow_of = cf_id
            nd.iface = sub_iface

    if entry_id is None:
        raise BuildError(f"CallFlow '{cf_id}': the subflow has no entry node")

    return nodes, entry_id, exit_id


def _validate_declared_types(flow: FlowDef, nodes: dict[str, ResolvedNode], err: _Errors) -> None:
    """Rejects any type outside the closed registry (including the public interface)."""
    def check(type_spec, where: str):
        if type_spec is None:
            return
        try:
            parse_type(type_spec)
        except TypeError_ as e:
            err.add(f"{where}: {e}")

    for name, t in flow.inputs.items():
        check(t, f"flow input '{name}'")
    for name, t in flow.outputs.items():
        check(t, f"flow output '{name}'")
    for nid, rnode in nodes.items():
        for pin in rnode.meta.inputs:
            check(pin.type, f"node '{nid}', input '{pin.name}'")
        for pin in rnode.meta.outputs:
            check(pin.type, f"node '{nid}', output '{pin.name}'")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _index_nodes(flow: FlowDef, catalog: NodeCatalog, err: _Errors) -> dict[str, ResolvedNode]:
    nodes: dict[str, ResolvedNode] = {}
    for node_def in flow.nodes:
        if node_def.id in nodes:
            err.add(
                f"Node id '{node_def.id}' is duplicate: every node must have a unique id"
            )
            continue
        entry = catalog.get(node_def.type)
        if entry is None:
            err.add(f"Node '{node_def.type}' (id={node_def.id}) is not in the catalog")
            continue
        cls, meta = entry
        # Local metadata copy so dynamic pins can be injected without
        # mutating the catalog's global metadata.
        meta = _with_dynamic_pins(meta, flow, node_def)
        nodes[node_def.id] = ResolvedNode(node_def=node_def, node_cls=cls, meta=meta)
    return nodes


_REQUEST_PINS = (
    ("headers", "dict[str, str]"),
    ("query", "dict[str, str]"),
    ("body", "Any"),
    ("method", "str"),
)


def _with_dynamic_pins(meta: NodeMeta, flow: FlowDef, node_def=None) -> NodeMeta:
    """Generates the dynamic pins of public-interface nodes.

    - FlowInput / OnEvent: data outputs = the flow's declared inputs, PLUS
      fixed headers/query/body/method pins — every served flow's trigger
      IS an HTTP request, so the entry node always exposes the raw
      envelope alongside whatever named inputs the flow declares. A flow
      that doesn't run over HTTP (or wasn't given a request) just sees
      empty dicts/strings for these — see execute()'s seeding in
      engine/executor.py.
    - FlowOutput: data inputs = the flow's declared outputs.
    - CallFlow: extra data inputs = any key in node_def.inputs not already
      declared as a pin. Lets arbitrary inputs be passed to the subflow.
    """
    import copy
    from rayflow.nodes.decorators import PinSpec

    # For boundary nodes of a spliced subgraph, the interface is annotated on
    # node_def.iface (the subflow's inputs/outputs, not the root flow's).
    iface = node_def.iface if node_def is not None else None
    flow_inputs = iface["inputs"] if iface else flow.inputs
    flow_outputs = iface["outputs"] if iface else flow.outputs

    if meta.name in ("OnStart", "OnEvent"):
        meta = copy.copy(meta)
        meta.outputs = list(meta.outputs) + [
            PinSpec(name=name, kind="data_out", type=type_str)
            for name, type_str in flow_inputs.items()
        ] + [
            PinSpec(name=name, kind="data_out", type=type_str)
            for name, type_str in _REQUEST_PINS
        ]
        # In a spliced OnStart/OnEvent, the same names are also data inputs:
        # they come in from the CallFlow and get re-exposed as outputs to the subgraph.
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
    elif meta.is_parallel and node_def is not None:
        # Discover dynamic branch pins by scanning the flow's wiring. Nodes
        # whose exec_in references this Parallel with a pin starting with
        # "branch_" define the available branches.
        branch_pins: set[str] = set()
        par_id = node_def.id
        for nd in flow.nodes:
            if nd.exec_in is None:
                continue
            sources = [nd.exec_in] if isinstance(nd.exec_in, str) else nd.exec_in
            for src in sources:
                if "." not in src:
                    continue
                src_id, src_pin = src.split(".", 1)
                if src_id == par_id and src_pin.startswith("branch_"):
                    branch_pins.add(src_pin)
        if branch_pins:
            def _branch_sort_key(pin: str) -> tuple:
                suffix = pin[len("branch_"):]
                try:
                    return (0, int(suffix))
                except ValueError:
                    return (1, suffix)
            sorted_branches = sorted(branch_pins, key=_branch_sort_key)
            # joined is always declared — keep it last.
            meta = copy.copy(meta)
            meta.exec_outputs = sorted_branches + (["joined"] if "joined" in meta.exec_outputs else [])
    return meta


def _validate_exec_inputs(flow: FlowDef, nodes: dict[str, ResolvedNode], err: _Errors) -> None:
    """Validates: every exec input has exactly one incoming edge.

    An exec edge is declared from the consumer side via `exec_in`:
    - "node_id"            -> the source node's default exec output.
    - "node_id.pin_name"   -> a specific exec output (Branch.true, Sequence.then_0…).
    """
    incoming_exec: dict[str, list[str]] = {nid: [] for nid in nodes}

    for nid, rnode in nodes.items():
        exec_in = rnode.node_def.exec_in
        if exec_in is None:
            if rnode.meta.has_exec_in:
                err.add(
                    f"Node '{rnode.meta.name}' (id={nid}) requires an exec input but has no edge"
                )
            continue

        if isinstance(exec_in, dict):
            if "or" not in exec_in:
                err.add(
                    f"Node '{nid}': exec_in as a dict must have the form {{\"or\": [...]}}"
                )
                continue
            rnode.exec_join = "or"
            sources = exec_in["or"]
        elif isinstance(exec_in, list):
            rnode.exec_join = "and"
            sources = exec_in
        else:
            rnode.exec_join = "and"
            sources = [exec_in]
        for src in sources:
            ref = _parse_exec_ref(src, nodes, err)
            if ref is None:
                continue
            src_id, src_pin = ref
            if src_id not in nodes:
                err.add(
                    f"Node '{nid}': exec_in points to '{src_id}', which doesn't exist in the graph"
                )
                continue
            incoming_exec[nid].append(src_id)
            rnode.exec_sources.append(src_id)
            nodes[src_id].exec_targets.setdefault(src_pin, []).append(nid)


def _parse_exec_ref(ref: str, nodes: dict[str, ResolvedNode], err: _Errors) -> tuple[str, str] | None:
    """Resolves "node_id" or "node_id.pin" -> (node_id, exec_out_pin).

    Returns None if the reference is ambiguous (several exec outputs with no
    explicit pin) and `err` is in collecting mode — so the caller can skip it.
    """
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
        err.add(
            f"Exec source '{src_id}' ({src_rnode.meta.name}) has multiple exec outputs "
            f"{exec_outs}; specify which one with 'node_id.pin_name'"
        )
        return None
    return src_id, "exec_out"


def _validate_data_inputs(
    flow: FlowDef, nodes: dict[str, ResolvedNode], catalog: NodeCatalog, err: _Errors
) -> None:
    """Validates types on data edges and that required inputs are covered."""
    for nid, rnode in nodes.items():
        meta = rnode.meta
        node_inputs_raw = rnode.node_def.inputs

        for pin_spec in meta.inputs:
            raw = node_inputs_raw.get(pin_spec.name, _MISSING)

            if raw is _MISSING:
                if pin_spec.required:
                    err.add(
                        f"Node '{nid}' (type={rnode.meta.name}): "
                        f"pin '{pin_spec.name}' is required but has no value or edge"
                    )
                # Falls back to the pin's default — there's no edge.
                rnode.resolved_inputs[pin_spec.name] = ResolvedPin(
                    is_ref=False, literal=pin_spec.default
                )
                continue

            if isinstance(raw, str) and "." in raw:
                # A reference to another node: "source_id.pin_name"
                parts = raw.split(".", 1)
                src_id, src_pin = parts[0], parts[1]
                if src_id not in nodes:
                    err.add(
                        f"Node '{nid}': pin '{pin_spec.name}' references '{src_id}', which doesn't exist"
                    )
                    continue
                src_meta = nodes[src_id].meta
                # Look up the output pin on the source.
                src_out = next(
                    (p for p in src_meta.outputs if p.name == src_pin), None
                )
                if src_out is None and src_pin == "meta":
                    # Implicit output injected by the engine on every node.
                    producer_type = "dict"
                elif src_out is None:
                    # A dynamic output (FlowInput/OnEvent): its declared type
                    # lives in flow.inputs. We validate against it if available.
                    producer_type = flow.inputs.get(src_pin)
                else:
                    producer_type = src_out.type

                if producer_type is not None and pin_spec.type is not None:
                    try:
                        ok = type_compatible(pin_spec.type, producer_type)
                    except TypeError_ as e:
                        err.add(
                            f"Node '{nid}', pin '{pin_spec.name}': invalid type ({e})"
                        )
                        continue
                    if not ok:
                        err.add(
                            f"Node '{nid}': pin '{pin_spec.name}' "
                            f"({parse_type(pin_spec.type)}) is incompatible with "
                            f"'{src_id}.{src_pin}' ({parse_type(producer_type)}). "
                            f"Use an explicit cast node (ToInt, ToFloat, ToStr, ToBool)."
                        )
                        continue
                rnode.resolved_inputs[pin_spec.name] = ResolvedPin(
                    is_ref=True, source_node=src_id, source_pin=src_pin
                )
            else:
                # A literal value — validate its type against the pin's.
                _check_literal_type(nid, pin_spec, raw, err)
                rnode.resolved_inputs[pin_spec.name] = ResolvedPin(is_ref=False, literal=raw)


def _literal_type_name(value: Any) -> str | None:
    """Rayflow canonical type of a Python literal, or None if it isn't modelable.

    bool before int: in Python bool is a subclass of int, but in the type
    system they're incompatible, so a True literal is "bool", not "int".
    """
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return None


def _check_literal_type(nid: str, pin_spec, value: Any, err: _Errors) -> None:
    """Checks that a static literal is compatible with the pin's declared type.

    Only applies to concrete types: if the pin is Any, or the literal is
    None (used as 'no value' for dynamic pins), or it isn't a modelable
    Python type, it's skipped. The comparison reuses the same strict rules
    as edges.
    """
    if pin_spec.type is None or value is None:
        return
    lit_type = _literal_type_name(value)
    if lit_type is None:
        return
    try:
        if type_compatible(pin_spec.type, lit_type):
            return
    except TypeError_:
        return
    err.add(
        f"Node '{nid}': pin '{pin_spec.name}' ({parse_type(pin_spec.type)}) "
        f"receives a literal {value!r} of type '{lit_type}', which is incompatible. "
        f"Use a value of the correct type or a cast node (ToInt, ToFloat, ToStr, ToBool)."
    )




def _validate_acyclicity(nodes: dict[str, ResolvedNode], err: _Errors) -> None:
    """Detects cycles in the data subgraph and in the execution plane.

    The internal checks raise on the first cycle found; in collecting mode
    we wrap them to report the cycle without aborting the rest of validation.
    """
    for check in (_check_data_cycles, _check_exec_cycles):
        try:
            check(nodes)
        except BuildError as e:
            err.add(str(e))


def _check_data_cycles(nodes: dict[str, ResolvedNode]) -> None:
    # DFS over data edges.
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(nid: str):
        color[nid] = GRAY
        for pin_res in nodes[nid].resolved_inputs.values():
            if pin_res.is_ref and pin_res.source_node:
                src = pin_res.source_node
                if color[src] == GRAY:
                    raise BuildError(
                        f"Data cycle detected: '{src}' → ... → '{nid}'"
                    )
                if color[src] == WHITE:
                    dfs(src)
        color[nid] = BLACK

    for nid in nodes:
        if color[nid] == WHITE:
            dfs(nid)


def _check_exec_cycles(nodes: dict[str, ResolvedNode]) -> None:
    # DFS over exec edges (exec_targets is dict[str, list[str]]).
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {nid: WHITE for nid in nodes}

    def dfs(nid: str):
        color[nid] = GRAY
        for target_ids in nodes[nid].exec_targets.values():
            for target_id in target_ids:
                if color[target_id] == GRAY:
                    raise BuildError(
                        f"Execution cycle detected: '{target_id}' → ... → '{nid}'"
                    )
                if color[target_id] == WHITE:
                    dfs(target_id)
        color[nid] = BLACK

    for nid in nodes:
        if color[nid] == WHITE:
            dfs(nid)


def _find_entry(nodes: dict[str, ResolvedNode], err: _Errors) -> str:
    # Entry/output nodes of spliced subgraphs carry subflow_of: they don't
    # count as the root flow's entry/exit.
    on_starts = [
        nid for nid, rn in nodes.items()
        if rn.meta.name == "OnStart" and rn.node_def.subflow_of is None
    ]
    on_events = [
        nid for nid, rn in nodes.items()
        if rn.meta.name == "OnEvent" and rn.node_def.subflow_of is None
    ]
    on_varchange = [
        nid for nid, rn in nodes.items()
        if rn.meta.name == "OnVariableChange" and rn.node_def.subflow_of is None
    ]
    all_entries = on_starts + on_events + on_varchange
    if not all_entries:
        err.add("The flow has no entry node (OnStart, OnEvent, or OnVariableChange)")
        return ""
    if len(on_starts) > 1:
        err.add(f"The flow has more than one OnStart node: {on_starts}")
    # Prefer OnStart for direct execution; otherwise an externally-triggered
    # entry point (OnEvent or OnVariableChange).
    if on_starts:
        return on_starts[0]
    if on_events:
        return on_events[0]
    return on_varchange[0]


def _find_outputs(nodes: dict[str, ResolvedNode]) -> list[str]:
    return [
        nid for nid, rn in nodes.items()
        if rn.meta.name == "FlowOutput" and rn.node_def.subflow_of is None
    ]
