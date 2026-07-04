#!/usr/bin/env python3
"""Scaffolds a Rayflow custom node class from a short description of its
pins — the decorator import line, ExecInput/ExecOutput, Input/Output pin
declarations, and a run() with the right signature/shape, instead of
hand-typing that boilerplate every time.

Usage:
    python3 .claude/skills/rayflow-node/scripts/scaffold_node.py MyNode \\
        --decorator engine_node --category Text \\
        --input value:str --input times:int:2 \\
        --output result:str \\
        --exec

    # write straight to custom_nodes/MyNode.py instead of stdout:
    python3 .../scaffold_node.py MyNode --input x:int --output y:int --write

Pin spec: "name:type" or "name:type:default" (default only for --input;
the raw default token is used as Python source, so pass e.g. `2`, `"hi"`,
`True` — quote appropriately for your shell). Only covers @engine_node,
@ray_node, @parallel_node — NOT @entry_node (entry nodes must NOT declare
exec_in and MUST declare at least one ExecOutput; that combination isn't
one of --exec's two modes here, so write an entry node by hand — see the
SKILL.md's "Frontend bundle" section for the shape).

This only generates/writes the .py file. It does NOT register it with the
running server — after --write, still call
mcp__rayflow__reload_custom_nodes (or create_custom_node/
update_custom_node_source, which hot-reload automatically) so the live
catalog picks it up. Then validate the contract with check_node.py in this
same scripts/ directory before wiring it into a flow.
"""
import argparse
import sys
from pathlib import Path

DECORATORS = ("engine_node", "ray_node", "parallel_node")

# Sensible zero-values when no explicit default was given, keyed by the
# pin's declared type — matches the convention builtin nodes already use
# (e.g. ForEach's `array = Input("list", default=None)`, EmitEvent's
# `payload = Input("Any", default=None)`): None for anything that isn't a
# primitive with an obvious zero value.
_ZERO_DEFAULTS = {"int": "0", "float": "0.0", "str": '""', "bool": "False"}


def _parse_pin(spec: str, is_input: bool):
    """'name:type' or 'name:type:default' (input only) -> (name, type, default_src|None)."""
    parts = spec.split(":", 2)
    if len(parts) < 2:
        raise ValueError(f"pin spec '{spec}' must be 'name:type' or 'name:type:default'")
    name, type_str = parts[0], parts[1]
    if not name.isidentifier():
        raise ValueError(f"pin name '{name}' is not a valid Python identifier")
    default_src = None
    if is_input and len(parts) == 3:
        default_src = parts[2]
    return name, type_str, default_src


def _validate_type(type_str: str) -> None:
    """Best-effort: checks the type string against rayflow's real type
    parser if rayflow is importable here. Skipped (not an error) if not —
    the server-side create_custom_node/hot-reload will catch it either way."""
    try:
        from rayflow.types import parse_type, TypeError_
    except ImportError:
        return
    try:
        parse_type(type_str)
    except TypeError_ as e:
        raise ValueError(str(e))


def _default_literal(type_str: str, raw: str | None) -> str:
    if raw is not None:
        if type_str == "str":
            return repr(raw)
        if type_str == "bool":
            return "True" if raw.strip().lower() in ("1", "true", "yes") else "False"
        return raw  # int/float/list/dict/Any/generics: pass through as Python source
    return _ZERO_DEFAULTS.get(type_str, "None")


def build_source(name: str, decorator: str, category: str, has_exec: bool,
                  inputs: list, outputs: list) -> str:
    lines = [
        f"from rayflow.nodes.decorators import {decorator}, ExecContext, ExecInput, ExecOutput, Input, Output",
        "",
        "",
        f"@{decorator}",
        f"class {name}:",
        f'    """TODO: describe what {name} does."""',
        f'    category = "{category}"',
    ]
    if has_exec:
        lines.append("    exec_in = ExecInput()")
    for pin_name, type_str, raw_default in inputs:
        lines.append(f'    {pin_name} = Input("{type_str}", default={_default_literal(type_str, raw_default)})')
    for pin_name, type_str in outputs:
        lines.append(f'    {pin_name} = Output("{type_str}")')
    if has_exec:
        lines.append("    exec_out = ExecOutput()")
    lines.append("")

    sig_params = "".join(f", {n}: {t}" for n, t, _ in inputs)
    if has_exec:
        lines.append(f"    async def run(self, ctx: ExecContext{sig_params}) -> None:")
        lines.append("        # TODO: implement. Call ctx.set_output(...) for each output")
        lines.append("        # BEFORE ctx.fire() if a downstream node needs it this step.")
        for pin_name, _type_str in outputs:
            lines.append(f'        ctx.set_output("{pin_name}", None)  # TODO')
        lines.append('        await ctx.fire("exec_out")')
    else:
        lines.append(f"    async def run(self, ctx: ExecContext{sig_params}) -> dict:")
        lines.append("        # TODO: implement. Pure node: no ctx.fire()/ctx.set_output() —")
        lines.append("        # just return a dict matching the Output names above.")
        ret = ", ".join(f'"{n}": None' for n, _ in outputs)
        lines.append(f"        return {{{ret}}}  # TODO")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="Class name, e.g. MyNode")
    parser.add_argument("--decorator", choices=DECORATORS, default="engine_node")
    parser.add_argument("--category", default="General")
    parser.add_argument("--input", action="append", default=[], dest="inputs",
                         metavar="name:type[:default]",
                         help="Repeatable. E.g. --input value:str --input times:int:2")
    parser.add_argument("--output", action="append", default=[], dest="outputs",
                         metavar="name:type",
                         help="Repeatable. E.g. --output result:str")
    parser.add_argument("--exec", action="store_true", dest="has_exec",
                         help="Give the node exec_in/exec_out (default: a 'pure' data node, "
                              "evaluated on demand — see the contract section for the difference)")
    parser.add_argument("--write", action="store_true",
                         help="Write to custom_nodes/<name>.py instead of printing to stdout "
                              "(run from the project root — same place you'd run 'rayflow serve')")
    args = parser.parse_args()

    if not args.name.isidentifier():
        print(f"error: '{args.name}' is not a valid Python identifier", file=sys.stderr)
        return 1

    try:
        inputs = [_parse_pin(s, is_input=True) for s in args.inputs]
        outputs = [(n, t) for n, t, _ in (_parse_pin(s, is_input=False) for s in args.outputs)]
        for _n, t, _d in inputs:
            _validate_type(t)
        for _n, t in outputs:
            _validate_type(t)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    source = build_source(args.name, args.decorator, args.category, args.has_exec, inputs, outputs)

    if args.write:
        target = Path.cwd() / "custom_nodes" / f"{args.name}.py"
        if target.exists():
            print(f"error: {target} already exists — refusing to overwrite", file=sys.stderr)
            return 1
        target.parent.mkdir(parents=True, exist_ok=True)
        init = target.parent / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")
        target.write_text(source, encoding="utf-8")
        print(f"wrote {target}")
        print("Next: call mcp__rayflow__reload_custom_nodes (or edit further via "
              "update_custom_node_source) so the running server's catalog sees it, "
              "then check_node.py to sanity-check the pin contract.")
    else:
        print(source)

    return 0


if __name__ == "__main__":
    sys.exit(main())
