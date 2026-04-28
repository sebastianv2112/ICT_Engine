"""
Webhook Receiver — Recibe alertas de TradingView via HTTP.

TradingView envía POST con el mensaje de alert() como body.
Al recibir una señal, ejecuta analyze_ict_setup() automáticamente
y muestra el resultado en la respuesta + dashboard web.

Puede correr standalone: python -m ict_mcp.webhook
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
_analyses: List[Dict] = []  # Análisis completos ejecutados


def store_signal(signal: Dict) -> None:
    """Almacena una señal recibida de TradingView."""
    signal["received_at"] = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")
    with _lock:
        _signals.append(signal)
        if len(_signals) > MAX_SIGNALS:
            _signals.pop(0)


def store_analysis(analysis: Dict) -> None:
    """Almacena un análisis ejecutado."""
    with _lock:
        _analyses.append(analysis)
        if len(_analyses) > 50:
            _analyses.pop(0)


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


def get_latest_analysis() -> Optional[Dict]:
    """Obtiene el último análisis ejecutado."""
    with _lock:
        return _analyses[-1] if _analyses else None


def clear_signals() -> int:
    """Limpia todas las señales. Retorna cantidad eliminada."""
    with _lock:
        count = len(_signals)
        _signals.clear()
    return count


# ═══════════════════════════════════════════════════════
# RUN ANALYSIS ON SIGNAL
# ═══════════════════════════════════════════════════════

def _run_analysis(symbol: str) -> str:
    """Ejecuta analyze_ict_setup y retorna el resultado como texto."""
    try:
        from ict_mcp.ict_analysis import full_analysis

        result = full_analysis(symbol)

        # Formatear como texto (mismo formato que el tool MCP)
        lines = [
            "═" * 60,
            f"  ICT 2022 SETUP ENGINE — {result['symbol']}",
            f"  Rating: {result['rating']} ({result['score']})",
            f"  Precio actual: {result['current_price']:.2f}",
            "═" * 60,
            "",
        ]

        # Checklist
        lines.append("CHECKLIST:")
        check_icons = {True: "✅", False: "❌"}
        check_labels = {
            "1_htf_bias": "HTF Bias definido",
            "2_htf_fvg_reaction": "Reaccion en FVG HTF",
            "3_sweep_15m": "Sweep de liquidez (15m)",
            "4_displacement_2m": "Displacement + BOS (2m)",
            "5_cisd_2m": "CISD confirmado (2m)",
            "6_order_block": "Order Block activo",
            "7_fvg_2m": "FVG activo (2m)",
            "8_macro_window": "Macro window",
        }
        for key, label in check_labels.items():
            val = result["checklist"].get(key, False)
            lines.append(f"  {check_icons[val]} {label}")

        # HTF
        htf = result["htf"]
        lines.append(f"\nHTF (1H): Bias {htf['bias'].upper()}")
        lines.append(f"  FVGs: {htf['fvgs_active']} activos / {htf['fvgs_total']} total")
        if htf["reaction"]:
            r = htf["reaction"]
            lines.append(f"  Reaccion en FVG {r['direction']}: {r['bottom']:.2f} - {r['top']:.2f}")

        # 15m
        mid = result["mid_tf"]
        if mid["sweeps"]:
            for s in mid["sweeps"][-2:]:
                lines.append(f"\n15m SWEEP: {s['direction'].upper()} @ {s['level']:.2f}")

        # 2m
        ltf = result["ltf"]
        if ltf["displacements"]:
            d = ltf["displacements"][-1]
            lines.append(f"\n2m: Displacement {d['direction'].upper()} {d['body_ratio']}x {'+ BOS' if d['breaks_structure'] else ''}")
        if ltf["cisds"]:
            c = ltf["cisds"][-1]
            lines.append(f"2m: CISD {c['direction'].upper()} @ {c['close']:.2f}")
        if ltf["order_blocks"]:
            ob = ltf["order_blocks"][-1]
            status = "MITIGADO" if ob["mitigated"] else "ACTIVO"
            lines.append(f"2m: OB {ob['direction'].upper()} {ob['bottom']:.2f}-{ob['top']:.2f} [{status}]")

        # Entry
        levels = result.get("levels")
        if levels:
            lines.append("")
            lines.append("═" * 60)
            lines.append(f"  SEÑAL: {levels['direction']}")
            lines.append("═" * 60)
            lines.append(f"  Entry:  {levels['entry']:.2f}")
            lines.append(f"  SL:     {levels['sl']:.2f}  ({levels['risk_points']:.2f} pts)")
            lines.append(f"  BE:     {levels['be']:.2f}")
            lines.append(f"  TP1:    {levels['tp1']:.2f}  (2R)")
            lines.append(f"  TP2:    {levels['tp2']:.2f}  (3R)")
            lines.append(f"  OB:     {levels['ob_zone']}")
        else:
            lines.append("\nSin señal de entrada — condiciones insuficientes")

        text = "\n".join(lines)

        # Almacenar análisis
        store_analysis({
            "symbol": symbol,
            "time": datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET"),
            "rating": result["rating"],
            "score": result["score"],
            "text": text,
            "result": result,
        })

        return text

    except Exception as e:
        error_msg = f"Error en análisis: {e}"
        store_analysis({
            "symbol": symbol,
            "time": datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET"),
            "error": error_msg,
        })
        return error_msg


# ═══════════════════════════════════════════════════════
# DASHBOARD HTML
# ═══════════════════════════════════════════════════════

def _render_dashboard() -> str:
    """Genera HTML del dashboard con último análisis."""
    analysis = get_latest_analysis()
    now = datetime.now(ET).strftime("%Y-%m-%d %H:%M:%S ET")

    if not analysis:
        content = "<p class='waiting'>Esperando primera señal de TradingView...</p>"
    elif "error" in analysis:
        content = f"<pre class='error'>{analysis['error']}</pre>"
    else:
        content = f"<pre class='analysis'>{analysis['text']}</pre>"

    with _lock:
        signal_count = len(_signals)
        analysis_count = len(_analyses)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>ICT 2022 Setup Engine</title>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="10">
    <style>
        body {{ font-family: 'Courier New', monospace; background: #1a1a2e; color: #eee; padding: 20px; }}
        h1 {{ color: #00d4aa; border-bottom: 2px solid #00d4aa; padding-bottom: 10px; }}
        .stats {{ color: #888; margin-bottom: 20px; }}
        .analysis {{ background: #16213e; padding: 20px; border-radius: 8px; border-left: 4px solid #00d4aa;
                     white-space: pre-wrap; font-size: 14px; line-height: 1.6; }}
        .error {{ background: #2d1b1b; padding: 20px; border-radius: 8px; border-left: 4px solid #ff4444; }}
        .waiting {{ color: #ffa500; font-size: 18px; }}
        .signal-log {{ margin-top: 30px; }}
        .signal-log h2 {{ color: #ffa500; }}
        .signal {{ background: #16213e; padding: 10px; margin: 5px 0; border-radius: 4px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>ICT 2022 Setup Engine</h1>
    <div class="stats">
        Actualizado: {now} | Señales: {signal_count} | Análisis: {analysis_count}
        <br>Auto-refresh cada 10s
    </div>
    {content}
    <div class="signal-log">
        <h2>Últimas señales</h2>
"""

    signals = get_signals(10)
    for s in reversed(signals):
        sig_type = s.get("type", "?").upper()
        sym = s.get("symbol", "?")
        received = s.get("received_at", "?")
        html += f'<div class="signal">{received} | {sig_type} {sym}</div>\n'

    if not signals:
        html += '<div class="signal">Sin señales aún</div>\n'

    html += """
    </div>
</body>
</html>"""
    return html


# ═══════════════════════════════════════════════════════
# HTTP HANDLER
# ═══════════════════════════════════════════════════════

class WebhookHandler(BaseHTTPRequestHandler):
    """Handler para webhooks de TradingView + dashboard web."""

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
            signal = {"raw_message": body, "type": "raw"}

        # Almacenar señal
        signal["source"] = "tradingview"
        store_signal(signal)

        # Determinar símbolo para análisis
        symbol = signal.get("symbol", "NQ")
        # Limpiar sufijos de TradingView (NQ1!, MNQ1!, etc.)
        symbol = symbol.replace("1!", "").replace("!", "").strip()
        if not symbol:
            symbol = "NQ"

        # Ejecutar análisis completo
        print(f"\n{'═'*50}")
        print(f"  📨 Señal recibida: {signal.get('type', '?').upper()} {symbol}")
        print(f"  ⏳ Ejecutando análisis...")
        print(f"{'═'*50}")

        analysis_text = _run_analysis(symbol)

        print(analysis_text)
        print(f"\n{'═'*50}\n")

        # Responder con el análisis completo
        response = {
            "status": "ok",
            "signal_received": signal.get("type", "unknown"),
            "symbol": symbol,
            "analysis": analysis_text,
        }

        response_bytes = json.dumps(response, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

    def do_GET(self):
        """Dashboard web + endpoints."""
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
            self.wfile.write(json.dumps(get_signals(20), ensure_ascii=False).encode())

        elif self.path == "/analysis":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            analysis = get_latest_analysis()
            self.wfile.write(json.dumps(analysis or {}, ensure_ascii=False).encode())

        else:
            # Dashboard HTML (root y cualquier otra ruta)
            html = _render_dashboard()
            html_bytes = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)

    def log_message(self, format, *args):
        """Solo loguear POSTs, no GETs."""
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


# ═══════════════════════════════════════════════════════
# STANDALONE MODE
# ═══════════════════════════════════════════════════════

def run_standalone(port: int = 8642):
    """Ejecuta el webhook server como proceso independiente (no MCP)."""
    print(f"""
╔══════════════════════════════════════════════════════╗
║  ICT 2022 Setup Engine — Webhook Server             ║
╠══════════════════════════════════════════════════════╣
║  Puerto:     {port}                                   ║
║  Dashboard:  http://localhost:{port}                  ║
║  Health:     http://localhost:{port}/health            ║
╠══════════════════════════════════════════════════════╣
║  Exponer con ngrok:                                  ║
║    ngrok http {port}                                  ║
║                                                      ║
║  Cuando TradingView envíe una alerta:                ║
║    → Se ejecuta analyze_ict_setup() automáticamente  ║
║    → Resultado visible en dashboard y ngrok UI       ║
╚══════════════════════════════════════════════════════╝
""")
    print("Esperando señales de TradingView...\n")

    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.shutdown()


if __name__ == "__main__":
    run_standalone()
