"""Capa MCP de Rayflow: expone un set curado de tools sobre el editor para que
un agente LLM construya, valide, pruebe y ejecute flows de forma autónoma."""

from rayflow.mcp.server import create_mcp

__all__ = ["create_mcp"]
