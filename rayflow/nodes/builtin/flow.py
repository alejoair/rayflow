"""CallFlow node — runs a subflow from within a flow.

After the validator's flatten(), the subflow is already expanded inline
into the flat graph (ids prefixed "{callflow_id}/..."). The CallFlow shell
no longer creates a FlowEngine: it's orchestrated by the engine, which fires
the inline subgraph's entry (blocking), reads the return FlowOutput as
'result', and continues.

See FlowEngine._fire_callflow_node and validator.flatten().
"""
from rayflow.nodes.decorators import (
    ExecContext,
    ExecInput,
    ExecOutput,
    Input,
    Output,
    engine_node,
)


@engine_node
class CallFlow:
    """Runs another flow as a subgraph, already flattened inline by the build.

    'flow' accepts, resolved at build time by `rayflow.workspace.resolve_flow`:
    - the NAME of a saved flow, exactly as returned by list_flows/create_flow
      (e.g. "my_subflow", no extension) — resolved against the workspace's
      flows/ directory.
    - a literal file path to a flow JSON file.
    - an inline subflow dict (the parsed FlowDef as JSON), not a reference.
    Referencing an unknown name/path raises a BuildError at validation time
    ("CallFlow '<id>': the 'flow' input references unknown flow '<name>'").

    Modes per 'isolated' (resolved at build time as the subgraph's state_path):
    - False (default): the subgraph shares the parent's GraphState.
    - True: the subgraph gets its own GraphState (a path segment).

    The 'result' output is a dict with the subflow's outputs
    ("callflow_id.result"). Extra inputs (beyond 'flow'/'isolated') are
    passed to the subgraph's FlowInput (wired at build time).

    run() is never invoked: the engine orchestrates this node via
    _fire_callflow_node, using subflow_entry/subflow_exit from the NodeDef.
    This body exists only as a pin declaration.
    """
    exec_in  = ExecInput()
    flow     = Input("Any",  default="")
    isolated = Input("bool", default=False)
    result   = Output("dict")
    exec_out = ExecOutput()

    async def run(self, ctx: ExecContext, flow: str, isolated: bool, **extra_inputs) -> None:
        # Not used: the engine orchestrates CallFlow directly (see
        # FlowEngine._fire_callflow_node). Left here for declaration symmetry.
        pass
