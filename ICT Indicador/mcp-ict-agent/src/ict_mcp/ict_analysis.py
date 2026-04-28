"""
ICT Analysis Engine — Detección de estructuras ICT 2022.

Implementa: FVG, Swing Points, Equal H/L, Sweeps, Displacement,
Order Blocks, CISD, Bias HTF, Macro Windows, Rating.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pytz

ET = pytz.timezone("US/Eastern")


# ═══════════════════════════════════════════════════════
# FVG DETECTION
# ═══════════════════════════════════════════════════════

def find_fvg(df: pd.DataFrame, lookback: int = 50) -> List[Dict]:
    """
    Detecta Fair Value Gaps en datos OHLCV.

    Bullish FVG: low[i] > high[i-2] → gap alcista sin llenar
    Bearish FVG: high[i] < low[i-2] → gap bajista sin llenar
    """
    fvgs = []
    data = df.tail(lookback + 2).reset_index()

    for i in range(2, len(data)):
        curr = data.iloc[i]
        prev2 = data.iloc[i - 2]
        time_val = data.iloc[i - 1].iloc[0]  # Tiempo de la vela del medio

        # Bullish FVG
        if curr["low"] > prev2["high"]:
            top = float(curr["low"])
            bottom = float(prev2["high"])
            filled = _is_fvg_filled(data, i, "bullish", top, bottom)
            fvgs.append({
                "direction": "bullish",
                "top": round(top, 2),
                "bottom": round(bottom, 2),
                "midpoint": round((top + bottom) / 2, 2),
                "size": round(top - bottom, 2),
                "time": _fmt_time(time_val),
                "filled": filled,
            })

        # Bearish FVG
        if curr["high"] < prev2["low"]:
            top = float(prev2["low"])
            bottom = float(curr["high"])
            filled = _is_fvg_filled(data, i, "bearish", top, bottom)
            fvgs.append({
                "direction": "bearish",
                "top": round(top, 2),
                "bottom": round(bottom, 2),
                "midpoint": round((top + bottom) / 2, 2),
                "size": round(top - bottom, 2),
                "time": _fmt_time(time_val),
                "filled": filled,
            })

    return fvgs


def _is_fvg_filled(data: pd.DataFrame, start_idx: int, direction: str, top: float, bottom: float) -> bool:
    """Verifica si un FVG fue llenado por velas posteriores."""
    for j in range(start_idx + 1, len(data)):
        candle = data.iloc[j]
        if direction == "bullish" and candle["low"] <= bottom:
            return True
        if direction == "bearish" and candle["high"] >= top:
            return True
    return False


# ═══════════════════════════════════════════════════════
# SWING POINTS
# ═══════════════════════════════════════════════════════

def find_swing_points(df: pd.DataFrame, left: int = 5, right: int = 5) -> List[Dict]:
    """
    Detecta Swing Highs y Swing Lows usando ventana left/right.

    Swing High: high[i] >= max(high[i-left:i+right+1])
    Swing Low:  low[i]  <= min(low[i-left:i+right+1])
    """
    swings = []
    data = df.reset_index()

    for i in range(left, len(data) - right):
        window = data.iloc[i - left: i + right + 1]
        row = data.iloc[i]

        if row["high"] >= window["high"].max():
            swings.append({
                "type": "high",
                "level": round(float(row["high"]), 2),
                "time": _fmt_time(row.iloc[0]),
                "index": i,
            })

        if row["low"] <= window["low"].min():
            swings.append({
                "type": "low",
                "level": round(float(row["low"]), 2),
                "time": _fmt_time(row.iloc[0]),
                "index": i,
            })

    return swings


def find_equal_levels(swings: List[Dict], tolerance_pct: float = 0.03) -> List[Dict]:
    """
    Detecta Equal Highs / Equal Lows (niveles de liquidez).

    tolerance_pct: % de tolerancia (0.03 = ~6 pts en NQ @ 20000)
    """
    equals = []
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]

    # Equal Highs
    for i, h1 in enumerate(highs):
        for h2 in highs[i + 1:]:
            diff_pct = abs(h1["level"] - h2["level"]) / h1["level"] * 100
            if diff_pct < tolerance_pct:
                level = round((h1["level"] + h2["level"]) / 2, 2)
                equals.append({
                    "type": "equal_highs",
                    "level": level,
                    "levels": [h1["level"], h2["level"]],
                    "times": [h1["time"], h2["time"]],
                })

    # Equal Lows
    for i, l1 in enumerate(lows):
        for l2 in lows[i + 1:]:
            diff_pct = abs(l1["level"] - l2["level"]) / l1["level"] * 100
            if diff_pct < tolerance_pct:
                level = round((l1["level"] + l2["level"]) / 2, 2)
                equals.append({
                    "type": "equal_lows",
                    "level": level,
                    "levels": [l1["level"], l2["level"]],
                    "times": [l1["time"], l2["time"]],
                })

    return equals


# ═══════════════════════════════════════════════════════
# SWEEP DETECTION
# ═══════════════════════════════════════════════════════

def find_sweeps(df: pd.DataFrame, levels: List[Dict], lookback: int = 20) -> List[Dict]:
    """
    Detecta Liquidity Sweeps: mecha rompe nivel pero cierre rechaza.

    Bull sweep (de lows): low < level pero close > level → setup long
    Bear sweep (de highs): high > level pero close < level → setup short
    """
    sweeps = []
    recent = df.tail(lookback).reset_index()

    for _, candle in recent.iterrows():
        for level in levels:
            lvl = level["level"]
            lvl_type = level["type"]

            if lvl_type in ("high", "equal_highs"):
                # Sweep de highs → bearish signal
                if candle["high"] > lvl and candle["close"] < lvl:
                    sweeps.append({
                        "direction": "bear_sweep",
                        "swept_type": lvl_type,
                        "level": lvl,
                        "candle_time": _fmt_time(candle.iloc[0]),
                        "wick_high": round(float(candle["high"]), 2),
                        "close": round(float(candle["close"]), 2),
                        "penetration": round(float(candle["high"] - lvl), 2),
                    })

            elif lvl_type in ("low", "equal_lows"):
                # Sweep de lows → bullish signal
                if candle["low"] < lvl and candle["close"] > lvl:
                    sweeps.append({
                        "direction": "bull_sweep",
                        "swept_type": lvl_type,
                        "level": lvl,
                        "candle_time": _fmt_time(candle.iloc[0]),
                        "wick_low": round(float(candle["low"]), 2),
                        "close": round(float(candle["close"]), 2),
                        "penetration": round(float(lvl - candle["low"]), 2),
                    })

    return sweeps


# ═══════════════════════════════════════════════════════
# DISPLACEMENT DETECTION
# ═══════════════════════════════════════════════════════

def find_displacement(df: pd.DataFrame, factor: float = 1.5, lookback: int = 30) -> List[Dict]:
    """
    Detecta velas de Displacement: cuerpo > promedio * factor.

    Indica movimiento institucional con intención.
    """
    data = df.copy()
    data["body"] = (data["close"] - data["open"]).abs()
    data["avg_body"] = data["body"].rolling(20, min_periods=5).mean()

    displacements = []
    recent = data.tail(lookback)

    for idx, row in recent.iterrows():
        if pd.isna(row["avg_body"]) or row["avg_body"] == 0:
            continue

        ratio = row["body"] / row["avg_body"]
        if ratio >= factor:
            direction = "bullish" if row["close"] > row["open"] else "bearish"

            # Verificar que rompe estructura previa
            breaks_structure = False
            iloc_pos = data.index.get_loc(idx)
            if iloc_pos > 0:
                prev = data.iloc[iloc_pos - 1]
                if direction == "bullish" and row["close"] > prev["high"]:
                    breaks_structure = True
                elif direction == "bearish" and row["close"] < prev["low"]:
                    breaks_structure = True

            displacements.append({
                "direction": direction,
                "time": _fmt_time(idx),
                "open": round(float(row["open"]), 2),
                "high": round(float(row["high"]), 2),
                "low": round(float(row["low"]), 2),
                "close": round(float(row["close"]), 2),
                "body_ratio": round(float(ratio), 2),
                "breaks_structure": breaks_structure,
            })

    return displacements


# ═══════════════════════════════════════════════════════
# ORDER BLOCKS
# ═══════════════════════════════════════════════════════

def find_order_blocks(df: pd.DataFrame, displacements: List[Dict]) -> List[Dict]:
    """
    Detecta Order Blocks: última vela contraria antes del displacement.

    Bull OB: última vela bearish antes de displacement alcista
    Bear OB: última vela bullish antes de displacement bajista
    """
    obs = []
    data = df.reset_index()

    for disp in displacements:
        if not disp["breaks_structure"]:
            continue

        # Buscar el índice del displacement en el DataFrame
        disp_time = disp["time"]
        matching = data[data.iloc[:, 0].apply(lambda x: _fmt_time(x) == disp_time)]
        if matching.empty:
            continue

        disp_iloc = matching.index[0]

        if disp["direction"] == "bullish":
            # Buscar última vela bearish antes del displacement
            for j in range(disp_iloc - 1, max(disp_iloc - 15, -1), -1):
                candle = data.iloc[j]
                if candle["close"] < candle["open"]:  # Bearish candle
                    obs.append({
                        "direction": "bullish",
                        "top": round(float(candle["high"]), 2),
                        "bottom": round(float(candle["low"]), 2),
                        "midpoint": round(float((candle["high"] + candle["low"]) / 2), 2),
                        "time": _fmt_time(candle.iloc[0]),
                        "displacement_time": disp_time,
                        "mitigated": _is_ob_mitigated(data, j, "bullish",
                                                       float(candle["high"]),
                                                       float(candle["low"])),
                    })
                    break
        else:
            # Buscar última vela bullish antes del displacement
            for j in range(disp_iloc - 1, max(disp_iloc - 15, -1), -1):
                candle = data.iloc[j]
                if candle["close"] > candle["open"]:  # Bullish candle
                    obs.append({
                        "direction": "bearish",
                        "top": round(float(candle["high"]), 2),
                        "bottom": round(float(candle["low"]), 2),
                        "midpoint": round(float((candle["high"] + candle["low"]) / 2), 2),
                        "time": _fmt_time(candle.iloc[0]),
                        "displacement_time": disp_time,
                        "mitigated": _is_ob_mitigated(data, j, "bearish",
                                                       float(candle["high"]),
                                                       float(candle["low"])),
                    })
                    break

    return obs


def _is_ob_mitigated(data: pd.DataFrame, ob_idx: int, direction: str, top: float, bottom: float) -> bool:
    """Verifica si un OB fue mitigado (precio retornó y lo atravesó)."""
    for j in range(ob_idx + 2, len(data)):  # +2 para saltar el displacement
        candle = data.iloc[j]
        if direction == "bullish" and candle["low"] < bottom:
            return True
        if direction == "bearish" and candle["high"] > top:
            return True
    return False


# ═══════════════════════════════════════════════════════
# CISD — CHANGE IN STATE OF DELIVERY
# ═══════════════════════════════════════════════════════

def find_cisd(df: pd.DataFrame, lookback: int = 30) -> List[Dict]:
    """
    Detecta CISD: cambio en el estado de entrega.

    Bull CISD: tras entrega bajista (velas bearish), cierre > high de última bearish
    Bear CISD: tras entrega alcista (velas bullish), cierre < low de última bullish

    Equivalente a CHoCH en contexto de order flow.
    """
    data = df.tail(lookback).reset_index()
    cisds = []

    for i in range(3, len(data)):
        curr = data.iloc[i]
        prev1 = data.iloc[i - 1]
        prev2 = data.iloc[i - 2]

        # Bull CISD: al menos 2 velas bearish previas, luego cierre > high de la última
        if (prev2["close"] < prev2["open"] and
            prev1["close"] < prev1["open"] and
            curr["close"] > prev1["high"]):
            cisds.append({
                "direction": "bullish",
                "time": _fmt_time(curr.iloc[0]),
                "close": round(float(curr["close"]), 2),
                "broke_level": round(float(prev1["high"]), 2),
                "delivery_candles": 2,
            })

        # Bear CISD: al menos 2 velas bullish previas, luego cierre < low de la última
        if (prev2["close"] > prev2["open"] and
            prev1["close"] > prev1["open"] and
            curr["close"] < prev1["low"]):
            cisds.append({
                "direction": "bearish",
                "time": _fmt_time(curr.iloc[0]),
                "close": round(float(curr["close"]), 2),
                "broke_level": round(float(prev1["low"]), 2),
                "delivery_candles": 2,
            })

    return cisds


# ═══════════════════════════════════════════════════════
# HTF BIAS
# ═══════════════════════════════════════════════════════

def determine_bias(df: pd.DataFrame) -> str:
    """
    Determina sesgo HTF basado en estructura de swings.

    Higher Highs + Higher Lows → bullish
    Lower Highs + Lower Lows → bearish
    Else → neutral
    """
    swings = find_swing_points(df, left=3, right=3)
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]

    if len(highs) >= 2 and len(lows) >= 2:
        hh = highs[-1]["level"] > highs[-2]["level"]
        hl = lows[-1]["level"] > lows[-2]["level"]
        lh = highs[-1]["level"] < highs[-2]["level"]
        ll = lows[-1]["level"] < lows[-2]["level"]

        if hh and hl:
            return "bullish"
        if lh and ll:
            return "bearish"

    # Fallback: tendencia de últimas 20 velas
    last = df.tail(20)
    if len(last) >= 10:
        if last.iloc[-1]["close"] > last.iloc[0]["open"]:
            return "bullish"
        elif last.iloc[-1]["close"] < last.iloc[0]["open"]:
            return "bearish"

    return "neutral"


def check_reaction_to_fvg(df: pd.DataFrame, fvgs: List[Dict]) -> Optional[Dict]:
    """
    Verifica si el precio actual está reaccionando a un FVG HTF activo.
    """
    if not fvgs:
        return None

    current = df.iloc[-1]
    price = float(current["close"])
    low = float(current["low"])
    high = float(current["high"])

    active = [f for f in fvgs if not f["filled"]]

    for fvg in reversed(active):
        # Precio dentro del FVG
        if fvg["bottom"] <= price <= fvg["top"]:
            return {**fvg, "reaction": "inside"}
        # Precio tocó el FVG
        if fvg["direction"] == "bullish" and low <= fvg["top"] and price >= fvg["bottom"]:
            return {**fvg, "reaction": "touching"}
        if fvg["direction"] == "bearish" and high >= fvg["bottom"] and price <= fvg["top"]:
            return {**fvg, "reaction": "touching"}

    return None


# ═══════════════════════════════════════════════════════
# MACRO WINDOWS
# ═══════════════════════════════════════════════════════

ICT_MACROS = [
    {"name": "London Open Kill Zone", "start": (2, 0), "end": (5, 0)},
    {"name": "NY AM Macro 1", "start": (9, 30), "end": (10, 0)},
    {"name": "NY AM Macro 2", "start": (10, 45), "end": (11, 15)},
    {"name": "NY Lunch Macro", "start": (11, 45), "end": (12, 15)},
    {"name": "NY PM Macro", "start": (13, 30), "end": (14, 0)},
    {"name": "NY PM Close", "start": (14, 45), "end": (15, 15)},
]


def is_in_macro_window(time_et: Optional[datetime] = None) -> Dict:
    """
    Verifica si el momento actual está en una macro window ICT.
    """
    if time_et is None:
        time_et = datetime.now(ET)

    hour = time_et.hour
    minute = time_et.minute
    current_minutes = hour * 60 + minute

    for macro in ICT_MACROS:
        start_min = macro["start"][0] * 60 + macro["start"][1]
        end_min = macro["end"][0] * 60 + macro["end"][1]

        if start_min <= current_minutes <= end_min:
            return {
                "in_macro": True,
                "macro_name": macro["name"],
                "time_et": time_et.strftime("%H:%M ET"),
            }

    return {
        "in_macro": False,
        "macro_name": None,
        "time_et": time_et.strftime("%H:%M ET"),
        "next_macro": _next_macro(current_minutes),
    }


def _next_macro(current_minutes: int) -> Optional[str]:
    """Encuentra la próxima macro window."""
    for macro in ICT_MACROS:
        start_min = macro["start"][0] * 60 + macro["start"][1]
        if start_min > current_minutes:
            h, m = divmod(start_min, 60)
            return f"{macro['name']} @ {h:02d}:{m:02d} ET"
    return "Mañana — London Open @ 02:00 ET"


# ═══════════════════════════════════════════════════════
# ENTRY LEVELS
# ═══════════════════════════════════════════════════════

def calculate_entry_levels(
    bias: str,
    obs: List[Dict],
    cisds: List[Dict],
    current_price: float,
    rr_tp1: float = 2.0,
    rr_tp2: float = 3.0,
) -> Optional[Dict]:
    """
    Calcula niveles de entrada basados en OB + CISD.

    Entry: OB zone (top para long, bottom para short)
    SL: Más allá del OB con buffer del 50%
    TP1/TP2: Basados en R:R
    """
    if not obs:
        return None

    # Filtrar OBs no mitigados y alineados con el bias
    valid_obs = [ob for ob in obs if not ob["mitigated"]]
    if bias == "bullish":
        valid_obs = [ob for ob in valid_obs if ob["direction"] == "bullish"]
    elif bias == "bearish":
        valid_obs = [ob for ob in valid_obs if ob["direction"] == "bearish"]

    if not valid_obs:
        return None

    ob = valid_obs[-1]  # OB más reciente

    if ob["direction"] == "bullish":
        entry = ob["top"]
        sl = ob["bottom"] - (ob["top"] - ob["bottom"]) * 0.5
        risk = entry - sl
        return {
            "direction": "LONG",
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "be": round(entry + risk, 2),
            "tp1": round(entry + risk * rr_tp1, 2),
            "tp2": round(entry + risk * rr_tp2, 2),
            "risk_points": round(risk, 2),
            "ob_zone": f"{ob['bottom']} — {ob['top']}",
        }
    else:
        entry = ob["bottom"]
        sl = ob["top"] + (ob["top"] - ob["bottom"]) * 0.5
        risk = sl - entry
        return {
            "direction": "SHORT",
            "entry": round(entry, 2),
            "sl": round(sl, 2),
            "be": round(entry - risk, 2),
            "tp1": round(entry - risk * rr_tp1, 2),
            "tp2": round(entry - risk * rr_tp2, 2),
            "risk_points": round(risk, 2),
            "ob_zone": f"{ob['bottom']} — {ob['top']}",
        }


# ═══════════════════════════════════════════════════════
# FULL MULTI-TF ANALYSIS
# ═══════════════════════════════════════════════════════

def full_analysis(symbol: str) -> Dict:
    """
    Análisis completo ICT 2022 multi-timeframe.

    Flujo: 1H (bias + FVG) → 15m (sweep) → 2m (CISD + OB + entry)
    """
    from ict_mcp.data_provider import fetch_candles

    result = {"symbol": symbol.upper()}

    # ── Paso 1: HTF (1H) — Bias + FVG ──
    df_1h = fetch_candles(symbol, "1h", 100)
    htf_fvgs = find_fvg(df_1h, 50)
    htf_bias = determine_bias(df_1h)
    htf_reaction = check_reaction_to_fvg(df_1h, htf_fvgs)

    result["htf"] = {
        "bias": htf_bias,
        "fvgs_total": len(htf_fvgs),
        "fvgs_active": len([f for f in htf_fvgs if not f["filled"]]),
        "reaction": htf_reaction,
        "last_fvgs": htf_fvgs[-5:] if htf_fvgs else [],
    }

    # ── Paso 2: 15m — Swing Points + Sweep ──
    df_15m = fetch_candles(symbol, "15m", 100)
    swings_15m = find_swing_points(df_15m, left=5, right=5)
    equals_15m = find_equal_levels(swings_15m)
    all_levels = swings_15m + equals_15m
    sweeps_15m = find_sweeps(df_15m, all_levels)

    result["mid_tf"] = {
        "swing_highs": [s for s in swings_15m if s["type"] == "high"][-5:],
        "swing_lows": [s for s in swings_15m if s["type"] == "low"][-5:],
        "equal_levels": equals_15m,
        "sweeps": sweeps_15m[-3:],
    }

    # ── Paso 3: LTF (2m) — Displacement + CISD + OB ──
    df_2m = fetch_candles(symbol, "2m", 100)
    disps_2m = find_displacement(df_2m, factor=1.5)
    obs_2m = find_order_blocks(df_2m, disps_2m)
    cisds_2m = find_cisd(df_2m)
    fvgs_2m = find_fvg(df_2m, 30)

    result["ltf"] = {
        "displacements": disps_2m[-5:],
        "order_blocks": obs_2m[-3:],
        "cisds": cisds_2m[-3:],
        "fvgs": [f for f in fvgs_2m if not f["filled"]][-5:],
    }

    # ── Paso 4: Macro Window ──
    macro = is_in_macro_window()
    result["macro"] = macro

    # ── Paso 5: Scoring ──
    score = 0
    checklist = {}

    checklist["1_htf_bias"] = htf_bias != "neutral"
    if checklist["1_htf_bias"]:
        score += 1

    checklist["2_htf_fvg_reaction"] = htf_reaction is not None
    if checklist["2_htf_fvg_reaction"]:
        score += 1

    checklist["3_sweep_15m"] = len(sweeps_15m) > 0
    if checklist["3_sweep_15m"]:
        score += 1

    checklist["4_displacement_2m"] = len([d for d in disps_2m if d["breaks_structure"]]) > 0
    if checklist["4_displacement_2m"]:
        score += 1

    checklist["5_cisd_2m"] = len(cisds_2m) > 0
    if checklist["5_cisd_2m"]:
        score += 1

    checklist["6_order_block"] = len([ob for ob in obs_2m if not ob["mitigated"]]) > 0
    if checklist["6_order_block"]:
        score += 1

    checklist["7_fvg_2m"] = len([f for f in fvgs_2m if not f["filled"]]) > 0
    if checklist["7_fvg_2m"]:
        score += 1

    checklist["8_macro_window"] = macro["in_macro"]
    if checklist["8_macro_window"]:
        score += 1

    if score >= 6:
        rating = "A+"
    elif score >= 5:
        rating = "A"
    elif score >= 4:
        rating = "B"
    else:
        rating = "C"

    result["rating"] = rating
    result["score"] = f"{score}/8"
    result["checklist"] = checklist

    # ── Paso 6: Entry Levels ──
    current_price = float(df_2m.iloc[-1]["close"])
    result["current_price"] = round(current_price, 2)
    result["levels"] = calculate_entry_levels(htf_bias, obs_2m, cisds_2m, current_price)

    return result


# ═══════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════

def _fmt_time(val) -> str:
    """Formatea timestamp a string legible."""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M")
    return str(val)
