"""
Webhook Receiver — Recibe alertas de TradingView via HTTP.

TradingView envía POST con el mensaje de alert() como body.
El servidor almacena las señales en memoria para consulta via MCP.
"""

import json
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Dict, Optional
import pytz

ET = pytz.timezone("US/Eastern")

# ═══════════════════════════════════════════════════════
# SIGNAL STORE (in-memory, thread-safe)
# ═══════════════════════════════════════════════════════

MAX_SIGNALS = 200

_lock = threading.Lock()
_signals: List[Dict] = []


def store_signal(signal: Dict) -> None:
    """Almacena una señal recibida de TradingView."""
    signal["received_at"] = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")
    with _lock:
        _signals.append(signal)
        if len(_signals) > MAX_SIGNALS:
            _signals.pop(0)


def get_signals(limit: int = 20, symbol: str = None, signal_type: str = None) -> List[Dict]:
    """Consulta señales almacenadas con filtros opcionales."""
    with _lock:
        filtered = list(_signals)

    if symbol:
        filtered = [s for s in filtered if s.get("symbol", "").upper() == symbol.upper()]
    if signal_type:
        filtered = [s for s in filtered if s.get("type", "").lower() == signal_type.lower()]

    return filtered[-limit:]


def get_latest_signal(symbol: str = None) -> Optional[Dict]:
    """Obtiene la señal más reciente."""
    signals = get_signals(limit=1, symbol=symbol)
    return signals[0] if signals else None


def clear_signals() -> int:
    """Limpia todas las señales. Retorna cantidad eliminada."""
    with _lock:
        count = len(_signals)
        _signals.clear()
    return count


# ═══════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════

class WebhookHandler(BaseHTTPRequestHandler):
    """Handler para webhooks de TradingView."""

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 10_000:  # Max 10KB payload
            self.send_response(413)
            self.end_headers()
            return

        body = self.rfile.read(content_length).decode("utf-8", errors="replace")

        try:
            signal = json.loads(body)
        except json.JSONDecodeError:
            # TradingView puede enviar texto plano — envolverlo
            signal = {"raw_message": body, "type": "raw"}

        # Agregar metadata
        signal["source"] = "tradingview"
        store_signal(signal)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())

    def do_GET(self):
        """Health check endpoint."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with _lock:
                count = len(_signals)
            self.wfile.write(json.dumps({
                "status": "running",
                "signals_stored": count,
                "time": datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET"),
            }).encode())
        elif self.path == "/signals":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(get_signals(20)).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


# ═══════════════════════════════════════════════════════
# SERVER LIFECYCLE
# ═══════════════════════════════════════════════════════

_server: Optional[HTTPServer] = None
_thread: Optional[threading.Thread] = None


def start_webhook_server(port: int = 8642) -> str:
    """Inicia el servidor webhook en un thread separado."""
    global _server, _thread

    if _server is not None:
        return f"Ya corriendo en puerto {_server.server_address[1]}"

    _server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()

    return f"Webhook server iniciado en http://0.0.0.0:{port}"


def stop_webhook_server() -> str:
    """Detiene el servidor webhook."""
    global _server, _thread

    if _server is None:
        return "No hay servidor corriendo"

    _server.shutdown()
    _server = None
    _thread = None
    return "Servidor detenido"


def get_server_status() -> Dict:
    """Estado del servidor webhook."""
    with _lock:
        count = len(_signals)

    if _server is not None:
        port = _server.server_address[1]
        return {
            "running": True,
            "port": port,
            "url": f"http://localhost:{port}",
            "signals_stored": count,
        }
    return {
        "running": False,
        "signals_stored": count,
    }
