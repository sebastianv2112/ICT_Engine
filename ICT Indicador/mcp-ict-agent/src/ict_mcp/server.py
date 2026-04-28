"""
MCP Server — ICT 2022 Setup Engine.

Expone herramientas para análisis multi-TF del Modelo ICT 2022.
Flujo: 1H (bias + FVG) → 15m (sweep) → 2m (CISD + OB → entry)
"""

import json
from mcp.server.fastmcp import FastMCP
from ict_mcp.data_provider import fetch_candles, get_current_price, is_market_open
from ict_mcp.ict_analysis import (
    find_fvg,
    find_swing_points,
    find_equal_levels,
    find_sweeps,
    find_displacement,
    find_order_blocks,
    find_cisd,
    determine_bias,
    is_in_macro_window,
    full_analysis,
)
from ict_mcp.webhook import (
    start_webhook_server,
    stop_webhook_server,
    get_server_status,
    get_signals,
    get_latest_signal,
    clear_signals,
)

mcp = FastMCP("ICT 2022 Setup Engine")


# ═══════════════════════════════════════════════════════
# TOOL: get_candles
# ═══════════════════════════════════════════════════════

@mcp.tool()
def get_candles(symbol: str, timeframe: str = "1h", bars: int = 50) -> str:
    """
    Obtener velas OHLCV para un símbolo y timeframe.

    Símbolos soportados: NQ, ES, YM (futuros), EURUSD, GBPUSD (forex),
    o cualquier ticker de Yahoo Finance.

    Timeframes: 1m, 2m, 5m, 15m, 30m, 1h

    Args:
        symbol: Símbolo (NQ, ES, YM o ticker completo)
        timeframe: Intervalo de las velas
        bars: Número de velas (max recomendado: 100)
    """
    try:
        df = fetch_candles(symbol, timeframe, min(bars, 200))
        lines = [
            f"📊 {symbol.upper()} | {timeframe} | {len(df)} velas",
            f"{'Tiempo':>20} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10} {'Vol':>10}",
            "─" * 75,
        ]
        for idx, row in df.iterrows():
            t = idx.strftime("%Y-%m-%d %H:%M") if hasattr(idx, "strftime") else str(idx)
            lines.append(
                f"{t:>20} {row['open']:>10.2f} {row['high']:>10.2f} "
                f"{row['low']:>10.2f} {row['close']:>10.2f} {int(row['volume']):>10}"
            )
        last = df.iloc[-1]
        lines.append("")
        lines.append(f"Último: {last['close']:.2f} | Rango: {df['low'].min():.2f} — {df['high'].max():.2f}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error obteniendo datos: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: detect_fvg
# ═══════════════════════════════════════════════════════

@mcp.tool()
def detect_fvg(symbol: str, timeframe: str = "1h", lookback: int = 50) -> str:
    """
    Detectar Fair Value Gaps (FVG) en un símbolo y timeframe.

    Bullish FVG = gap alcista (low > high[2])
    Bearish FVG = gap bajista (high < low[2])

    Retorna FVGs activos (no llenados) y recientes.

    Args:
        symbol: Símbolo (NQ, ES, YM)
        timeframe: Intervalo (1m, 2m, 5m, 15m, 1h)
        lookback: Velas hacia atrás a analizar
    """
    try:
        df = fetch_candles(symbol, timeframe, lookback + 10)
        fvgs = find_fvg(df, lookback)

        if not fvgs:
            return f"📋 {symbol.upper()} {timeframe} — No se detectaron FVGs en las últimas {lookback} velas."

        active = [f for f in fvgs if not f["filled"]]
        filled = [f for f in fvgs if f["filled"]]

        lines = [f"📋 FVG — {symbol.upper()} | {timeframe} | {len(fvgs)} total ({len(active)} activos)", ""]

        if active:
            lines.append("🟢 FVGs ACTIVOS (no llenados):")
            for f in active:
                icon = "🔵" if f["direction"] == "bullish" else "🔴"
                lines.append(
                    f"  {icon} {f['direction'].upper():>8} | "
                    f"{f['bottom']:.2f} — {f['top']:.2f} (mid: {f['midpoint']:.2f}) | "
                    f"Size: {f['size']:.2f} | {f['time']}"
                )

        if filled:
            lines.append(f"\n⚪ FVGs llenados: {len(filled)}")
            for f in filled[-3:]:  # Últimos 3
                lines.append(f"  ── {f['direction']:>8} | {f['bottom']:.2f} — {f['top']:.2f} | {f['time']}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: detect_liquidity
# ═══════════════════════════════════════════════════════

@mcp.tool()
def detect_liquidity(symbol: str, timeframe: str = "15m", lookback: int = 100) -> str:
    """
    Detectar niveles de liquidez: Swing Highs/Lows, Equal Highs/Lows, y Sweeps.

    Identifica dónde hay liquidez acumulada y si fue barrida recientemente.

    Args:
        symbol: Símbolo (NQ, ES, YM)
        timeframe: Intervalo (recomendado: 15m)
        lookback: Velas a analizar
    """
    try:
        df = fetch_candles(symbol, timeframe, lookback)
        swings = find_swing_points(df, left=5, right=5)
        equals = find_equal_levels(swings)
        all_levels = swings + equals
        sweeps = find_sweeps(df, all_levels)

        highs = [s for s in swings if s["type"] == "high"]
        lows = [s for s in swings if s["type"] == "low"]

        lines = [f"💧 Liquidez — {symbol.upper()} | {timeframe}", ""]

        lines.append(f"📈 Swing Highs ({len(highs)}):")
        for h in highs[-5:]:
            lines.append(f"  ▲ {h['level']:.2f} @ {h['time']}")

        lines.append(f"\n📉 Swing Lows ({len(lows)}):")
        for l in lows[-5:]:
            lines.append(f"  ▼ {l['level']:.2f} @ {l['time']}")

        if equals:
            lines.append(f"\n⚡ Equal Levels ({len(equals)}) — ALTA LIQUIDEZ:")
            for eq in equals:
                icon = "═══ EQH" if eq["type"] == "equal_highs" else "═══ EQL"
                lines.append(f"  {icon} @ {eq['level']:.2f} (niveles: {eq['levels']})")

        if sweeps:
            lines.append(f"\n🔥 SWEEPS DETECTADOS ({len(sweeps)}):")
            for s in sweeps[-3:]:
                icon = "🐂" if s["direction"] == "bull_sweep" else "🐻"
                lines.append(
                    f"  {icon} {s['direction'].upper()} | Nivel: {s['level']:.2f} | "
                    f"Penetración: {s['penetration']:.2f} pts | {s['candle_time']}"
                )
        else:
            lines.append("\n⏳ Sin sweeps recientes")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: detect_displacement
# ═══════════════════════════════════════════════════════

@mcp.tool()
def detect_displacement_ob(symbol: str, timeframe: str = "2m", factor: float = 1.5, lookback: int = 30) -> str:
    """
    Detectar Displacement (velas institucionales) y sus Order Blocks asociados.

    Displacement = cuerpo > promedio * factor + rompe estructura.
    OB = última vela contraria antes del displacement.

    Args:
        symbol: Símbolo (NQ, ES, YM)
        timeframe: Intervalo (recomendado: 2m para LTF)
        factor: Multiplicador para body vs average (default: 1.5)
        lookback: Velas a analizar
    """
    try:
        df = fetch_candles(symbol, timeframe, lookback + 20)
        disps = find_displacement(df, factor, lookback)
        obs = find_order_blocks(df, disps)

        lines = [f"⚡ Displacement + OB — {symbol.upper()} | {timeframe}", ""]

        if disps:
            lines.append(f"💥 Displacements ({len(disps)}):")
            for d in disps[-5:]:
                icon = "🟢" if d["direction"] == "bullish" else "🔴"
                struct = "✓ BOS" if d["breaks_structure"] else "✗ no BOS"
                lines.append(
                    f"  {icon} {d['direction'].upper():>8} | Body ratio: {d['body_ratio']}x | "
                    f"{struct} | {d['time']}"
                )
                lines.append(
                    f"     O:{d['open']:.2f} H:{d['high']:.2f} L:{d['low']:.2f} C:{d['close']:.2f}"
                )
        else:
            lines.append("⏳ Sin displacement reciente")

        if obs:
            lines.append(f"\n📦 Order Blocks ({len(obs)}):")
            for ob in obs[-3:]:
                icon = "🔵" if ob["direction"] == "bullish" else "🔴"
                status = "⚠️ MITIGADO" if ob["mitigated"] else "✅ ACTIVO"
                lines.append(
                    f"  {icon} {ob['direction'].upper():>8} OB | "
                    f"{ob['bottom']:.2f} — {ob['top']:.2f} (mid: {ob['midpoint']:.2f}) | "
                    f"{status} | {ob['time']}"
                )
        else:
            lines.append("\n📦 Sin Order Blocks detectados")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: detect_cisd
# ═══════════════════════════════════════════════════════

@mcp.tool()
def detect_cisd(symbol: str, timeframe: str = "2m", lookback: int = 30) -> str:
    """
    Detectar CISD (Change in State of Delivery) — equivalente a CHoCH.

    Bull CISD: tras velas bajistas, cierre rompe el high de la última → cambio a entrega alcista.
    Bear CISD: tras velas alcistas, cierre rompe el low de la última → cambio a entrega bajista.

    Args:
        symbol: Símbolo (NQ, ES, YM)
        timeframe: Intervalo (recomendado: 2m)
        lookback: Velas a analizar
    """
    try:
        df = fetch_candles(symbol, timeframe, lookback + 5)
        cisds = find_cisd(df, lookback)

        if not cisds:
            return f"⏳ {symbol.upper()} {timeframe} — Sin CISD detectado en las últimas {lookback} velas."

        lines = [f"🔄 CISD — {symbol.upper()} | {timeframe}", ""]
        for c in cisds[-5:]:
            icon = "🟢" if c["direction"] == "bullish" else "🔴"
            lines.append(
                f"  {icon} {c['direction'].upper():>8} CISD | "
                f"Close: {c['close']:.2f} rompió {c['broke_level']:.2f} | "
                f"{c['time']}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: check_macro
# ═══════════════════════════════════════════════════════

@mcp.tool()
def check_macro() -> str:
    """
    Verificar si estamos en una Macro Window ICT.

    Macros clave: London Open, NY AM, NY Lunch, NY PM, NY Close.
    Los setups en macro windows tienen mayor probabilidad.
    """
    macro = is_in_macro_window()
    market = is_market_open()

    lines = [f"🕐 Hora actual: {macro['time_et']}", ""]

    if market["is_open"]:
        lines.append("🟢 Mercado: ABIERTO")
    else:
        lines.append(f"🔴 Mercado: CERRADO — {market['reason']}")

    lines.append("")

    if macro["in_macro"]:
        lines.append(f"✅ EN MACRO: {macro['macro_name']}")
        lines.append("→ Alta probabilidad de movimiento institucional")
    else:
        lines.append("⏳ Fuera de macro window")
        if macro.get("next_macro"):
            lines.append(f"→ Próxima: {macro['next_macro']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# TOOL: market_status
# ═══════════════════════════════════════════════════════

@mcp.tool()
def market_status(symbol: str = "NQ") -> str:
    """
    Estado actual del mercado: precio, rango del día, y estado de sesión.

    Args:
        symbol: Símbolo (NQ, ES, YM)
    """
    try:
        price_info = get_current_price(symbol)
        market = is_market_open()
        macro = is_in_macro_window()

        lines = [
            f"📊 {price_info['symbol']} ({price_info['ticker']})",
            f"Precio: {price_info['last_price']:.2f}",
        ]

        if "previous_close" in price_info:
            change = price_info["last_price"] - price_info["previous_close"]
            pct = (change / price_info["previous_close"]) * 100
            icon = "🟢" if change >= 0 else "🔴"
            lines.append(f"Cambio: {icon} {change:+.2f} ({pct:+.2f}%)")

        if "day_high" in price_info:
            lines.append(f"Rango día: {price_info['day_low']:.2f} — {price_info['day_high']:.2f}")

        lines.append(f"\nSesión: {'🟢 Abierta' if market['is_open'] else '🔴 Cerrada'}")
        lines.append(f"Hora ET: {market['time_et']}")

        if macro["in_macro"]:
            lines.append(f"Macro: ✅ {macro['macro_name']}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: analyze_ict_setup (FULL ANALYSIS)
# ═══════════════════════════════════════════════════════

@mcp.tool()
def analyze_ict_setup(symbol: str) -> str:
    """
    Análisis COMPLETO ICT 2022 multi-timeframe.

    Ejecuta el flujo completo:
    1H (bias + FVG) → 15m (sweep) → 2m (CISD + OB → entry)

    Retorna: checklist, rating (A+/A/B/C), y niveles de entrada si aplica.

    Args:
        symbol: Símbolo (NQ, ES, YM)
    """
    try:
        result = full_analysis(symbol)

        lines = [
            "═" * 60,
            f"  ICT 2022 SETUP ENGINE — {result['symbol']}",
            f"  Rating: {result['rating']} ({result['score']})",
            f"  Precio actual: {result['current_price']:.2f}",
            "═" * 60,
            "",
        ]

        # Checklist
        lines.append("📋 CHECKLIST:")
        check_icons = {True: "✅", False: "❌"}
        check_labels = {
            "1_htf_bias": "HTF Bias definido",
            "2_htf_fvg_reaction": "Reacción en FVG HTF",
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

        # HTF Context
        htf = result["htf"]
        lines.append(f"\n📈 HTF (1H):")
        lines.append(f"  Bias: {htf['bias'].upper()}")
        lines.append(f"  FVGs: {htf['fvgs_active']} activos / {htf['fvgs_total']} total")
        if htf["reaction"]:
            r = htf["reaction"]
            lines.append(f"  ⚡ Reacción en FVG {r['direction']} ({r.get('reaction', 'N/A')}): {r['bottom']:.2f} — {r['top']:.2f}")

        # 15m Context
        mid = result["mid_tf"]
        lines.append(f"\n💧 15m Liquidez:")
        if mid["sweeps"]:
            for s in mid["sweeps"]:
                lines.append(f"  🔥 {s['direction'].upper()} @ {s['level']:.2f} ({s['candle_time']})")
        else:
            lines.append("  ⏳ Sin sweeps recientes")
        if mid["equal_levels"]:
            for eq in mid["equal_levels"]:
                lines.append(f"  ⚡ {eq['type'].upper()} @ {eq['level']:.2f}")

        # 2m Context
        ltf = result["ltf"]
        lines.append(f"\n⚡ LTF (2m):")
        if ltf["displacements"]:
            d = ltf["displacements"][-1]
            lines.append(f"  Displacement: {d['direction'].upper()} {d['body_ratio']}x {'+ BOS' if d['breaks_structure'] else ''}")
        if ltf["cisds"]:
            c = ltf["cisds"][-1]
            lines.append(f"  CISD: {c['direction'].upper()} @ {c['close']:.2f} ({c['time']})")
        if ltf["order_blocks"]:
            ob = ltf["order_blocks"][-1]
            status = "MITIGADO" if ob["mitigated"] else "ACTIVO"
            lines.append(f"  OB: {ob['direction'].upper()} {ob['bottom']:.2f}—{ob['top']:.2f} [{status}]")

        # Macro
        lines.append(f"\n🕐 Macro: {'✅ ' + result['macro'].get('macro_name', '') if result['macro']['in_macro'] else '❌ Fuera de macro'}")

        # Entry Levels
        levels = result.get("levels")
        if levels:
            lines.append("")
            lines.append("═" * 60)
            lines.append(f"  🎯 SEÑAL: {levels['direction']}")
            lines.append("═" * 60)
            lines.append(f"  Entry:  {levels['entry']:.2f}")
            lines.append(f"  SL:     {levels['sl']:.2f}  ({levels['risk_points']:.2f} pts)")
            lines.append(f"  BE:     {levels['be']:.2f}")
            lines.append(f"  TP1:    {levels['tp1']:.2f}  (2R)")
            lines.append(f"  TP2:    {levels['tp2']:.2f}  (3R)")
            lines.append(f"  OB:     {levels['ob_zone']}")
        else:
            lines.append("\n⏳ Sin señal de entrada — condiciones insuficientes")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error en análisis: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: tradingview_webhook_start
# ═══════════════════════════════════════════════════════

@mcp.tool()
def tradingview_webhook_start(port: int = 8642) -> str:
    """
    Iniciar el servidor webhook para recibir alertas de TradingView.

    TradingView enviará POST con JSON a http://tu-ip:{port}/
    Usa ngrok o cloudflare tunnel para exponer el puerto.

    Args:
        port: Puerto HTTP (default: 8642)
    """
    try:
        msg = start_webhook_server(port)
        status = get_server_status()
        lines = [
            f"✅ {msg}",
            "",
            "📋 Para conectar TradingView:",
            f"  1. Expón el puerto con: ngrok http {port}",
            "  2. Copia la URL pública (ej: https://abc123.ngrok.io)",
            "  3. En TradingView → Alert → Webhook URL → pega la URL",
            "  4. Las alertas del indicador ICT llegarán automáticamente",
            "",
            f"Señales almacenadas: {status['signals_stored']}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error: {e}"


# ═══════════════════════════════════════════════════════
# TOOL: tradingview_webhook_status
# ═══════════════════════════════════════════════════════

@mcp.tool()
def tradingview_webhook_status() -> str:
    """Ver estado del servidor webhook y señales almacenadas."""
    status = get_server_status()
    if status["running"]:
        return (
            f"🟢 Webhook server corriendo en puerto {status['port']}\n"
            f"URL local: {status['url']}\n"
            f"Señales almacenadas: {status['signals_stored']}"
        )
    return f"🔴 Webhook server detenido\nSeñales almacenadas: {status['signals_stored']}"


# ═══════════════════════════════════════════════════════
# TOOL: tradingview_get_signals
# ═══════════════════════════════════════════════════════

@mcp.tool()
def tradingview_get_signals(limit: int = 10, symbol: str = "", signal_type: str = "") -> str:
    """
    Consultar señales recibidas de TradingView via webhook.

    Args:
        limit: Máximo de señales a retornar (default: 10)
        symbol: Filtrar por símbolo (NQ, ES, YM). Vacío = todos
        signal_type: Filtrar por tipo (long, short, impulse). Vacío = todos
    """
    sym = symbol if symbol else None
    stype = signal_type if signal_type else None
    signals = get_signals(limit, sym, stype)

    if not signals:
        return "📭 No hay señales almacenadas" + (f" para {symbol}" if symbol else "")

    lines = [f"📬 {len(signals)} señal(es) de TradingView:", ""]

    for s in reversed(signals):
        sig_type = s.get("type", "unknown").upper()
        sym_name = s.get("symbol", "?")
        received = s.get("received_at", "?")

        if sig_type in ("LONG", "SHORT"):
            entry = s.get("entry", "?")
            sl = s.get("sl", "?")
            tp = s.get("tp", "?")
            icon = "🟢" if sig_type == "LONG" else "🔴"
            lines.append(f"{icon} {sig_type} {sym_name} | Entry: {entry} | SL: {sl} | TP: {tp}")
            lines.append(f"   Recibida: {received}")

            # Checklist if available
            checklist = s.get("checklist", {})
            if checklist:
                lines.append(f"   Bias: {checklist.get('bias', '?')} | Sweep: {'✅' if checklist.get('sweep') else '❌'} | OB: {'✅' if checklist.get('ob') else '❌'}")
        elif sig_type == "IMPULSE":
            direction = s.get("direction", "?")
            icon = "⚡"
            lines.append(f"{icon} IMPULSE {direction} {sym_name} | {received}")
        else:
            lines.append(f"📩 {s.get('raw_message', json.dumps(s))[:100]}")
            lines.append(f"   Recibida: {received}")

        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# TOOL: tradingview_latest_signal
# ═══════════════════════════════════════════════════════

@mcp.tool()
def tradingview_latest_signal(symbol: str = "NQ") -> str:
    """
    Obtener la ÚLTIMA señal recibida de TradingView para un símbolo.

    Ideal para preguntar: "¿hay señal nueva en NQ?"

    Args:
        symbol: Símbolo a consultar (NQ, ES, YM)
    """
    signal = get_latest_signal(symbol if symbol else None)
    if not signal:
        return f"📭 Sin señales para {symbol.upper()}"

    sig_type = signal.get("type", "unknown").upper()
    received = signal.get("received_at", "?")

    if sig_type in ("LONG", "SHORT"):
        icon = "🟢" if sig_type == "LONG" else "🔴"
        lines = [
            f"{icon} ÚLTIMA SEÑAL: {sig_type} {signal.get('symbol', symbol.upper())}",
            f"Recibida: {received}",
            "",
            f"Entry:  {signal.get('entry', '?')}",
            f"SL:     {signal.get('sl', '?')} ({signal.get('sl_distance', '?')} pts)",
            f"TP:     {signal.get('tp', '?')} (RR {signal.get('rr', '?')})",
            "",
        ]
        checklist = signal.get("checklist", {})
        if checklist:
            lines.append("Checklist:")
            lines.append(f"  HTF Bias: {checklist.get('bias', '?')}")
            lines.append(f"  Sweep:    {'✅' if checklist.get('sweep') else '❌'}")
            lines.append(f"  OB:       {checklist.get('ob_zone', '?')}")
            lines.append(f"  Macro:    {'✅' if checklist.get('in_macro') else '❌'}")
        return "\n".join(lines)

    return f"📩 Última señal ({received}): {json.dumps(signal, indent=2)}"


# ═══════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════

def main():
    # Auto-start webhook server when MCP starts
    start_webhook_server(8642)
    mcp.run()


if __name__ == "__main__":
    main()
