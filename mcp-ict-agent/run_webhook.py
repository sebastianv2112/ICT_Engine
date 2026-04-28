#!/usr/bin/env python3
"""
ICT 2022 Setup Engine — Webhook Server Standalone

Ejecuta el servidor webhook independiente de VS Code / MCP.
Cuando TradingView envía una alerta, ejecuta el análisis completo.

Uso:
    cd mcp-ict-agent
    uv run python run_webhook.py

    # En otra terminal:
    ngrok http 8642
"""

import sys
import os

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from ict_mcp.webhook import run_standalone

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8642
    run_standalone(port)
