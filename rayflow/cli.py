"""CLI de Rayflow. Punto de entrada: `rayflow <comando>` o `python -m rayflow`."""
from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rayflow", description="Rayflow CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Sirve uno o más flows como API REST")
    serve.add_argument(
        "--file", "-f", action="append", dest="files", required=True, metavar="PATH",
        help="Ruta a un flow JSON. Repetible para servir varios flows.",
    )
    serve.add_argument("--host", default="127.0.0.1", help="Host del servidor (default: 127.0.0.1)")
    serve.add_argument("--port", "-p", type=int, default=8000, help="Puerto (default: 8000)")
    serve.add_argument(
        "--nodes-dir", action="append", dest="nodes_dirs", metavar="DIR",
        help="Directorio extra de nodos de usuario. Repetible.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "serve":
        from rayflow.server import serve
        try:
            serve(
                sources=args.files,
                host=args.host,
                port=args.port,
                extra_node_dirs=args.nodes_dirs,
            )
        except (ImportError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
