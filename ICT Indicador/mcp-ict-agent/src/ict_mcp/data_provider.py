"""
Data Provider — Fetches OHLCV candle data from yfinance.

Soporta NQ, ES, YM futures con resolución de símbolos automática.
Convierte timestamps a US/Eastern para alineación con macros ICT.
"""

import yfinance as yf
import pandas as pd
import pytz
from datetime import datetime
from typing import Optional

# ═══════════════════════════════════════════════════════
# SYMBOL MAPPING
# ═══════════════════════════════════════════════════════

SYMBOL_MAP = {
    "NQ": "NQ=F",
    "ES": "ES=F",
    "YM": "YM=F",
    "RTY": "RTY=F",
    "GC": "GC=F",
    "CL": "CL=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
}

# yfinance max period por intervalo
INTERVAL_MAX_PERIOD = {
    "1m": "7d",
    "2m": "60d",
    "5m": "60d",
    "15m": "60d",
    "30m": "60d",
    "1h": "730d",
}

ET = pytz.timezone("US/Eastern")


def resolve_symbol(symbol: str) -> str:
    """Convierte alias a ticker de yfinance."""
    key = symbol.upper().strip()
    return SYMBOL_MAP.get(key, symbol)


def fetch_candles(
    symbol: str,
    interval: str = "1h",
    bars: int = 100,
) -> pd.DataFrame:
    """
    Obtiene velas OHLCV para un símbolo y timeframe.

    Args:
        symbol: Ticker o alias (NQ, ES, YM)
        interval: 1m, 2m, 5m, 15m, 30m, 1h
        bars: Número de velas deseadas

    Returns:
        DataFrame con columnas [open, high, low, close, volume] indexado por datetime ET
    """
    ticker = resolve_symbol(symbol)
    norm_interval = interval.lower().replace("min", "m")

    # Resolver período necesario
    period = INTERVAL_MAX_PERIOD.get(norm_interval, "60d")

    data = yf.download(
        ticker,
        period=period,
        interval=norm_interval,
        progress=False,
        auto_adjust=True,
    )

    if data.empty:
        raise ValueError(f"Sin datos para {ticker} en intervalo {norm_interval}")

    # Flatten MultiIndex columns (yfinance 0.2.31+)
    if isinstance(data.columns, pd.MultiIndex):
        data = data.droplevel("Ticker", axis=1)

    # Normalizar columnas
    df = data[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]

    # Convertir timezone a Eastern
    if df.index.tz is not None:
        df.index = df.index.tz_convert(ET)
    else:
        df.index = df.index.tz_localize("UTC").tz_convert(ET)

    # Eliminar filas con NaN
    df = df.dropna()

    return df.tail(bars)


def get_current_price(symbol: str) -> dict:
    """Obtiene precio actual y metadata básica."""
    ticker = resolve_symbol(symbol)
    info = yf.Ticker(ticker)

    try:
        fast = info.fast_info
        return {
            "symbol": symbol.upper(),
            "ticker": ticker,
            "last_price": round(float(fast.last_price), 2),
            "previous_close": round(float(fast.previous_close), 2),
            "day_high": round(float(fast.day_high), 2),
            "day_low": round(float(fast.day_low), 2),
        }
    except Exception:
        # Fallback: last candle close
        df = fetch_candles(symbol, "1m", 1)
        return {
            "symbol": symbol.upper(),
            "ticker": ticker,
            "last_price": round(float(df.iloc[-1]["close"]), 2),
        }


def is_market_open() -> dict:
    """Verifica si el mercado de futuros está abierto (CME)."""
    now_et = datetime.now(ET)
    weekday = now_et.weekday()  # 0=Mon, 6=Sun
    hour = now_et.hour
    minute = now_et.minute

    # Futuros CME: Dom 6pm - Vie 5pm ET (con pausa diaria 5pm-6pm ET)
    is_open = True
    reason = "Sesión activa"

    if weekday == 5:  # Sábado
        is_open = False
        reason = "Mercado cerrado (sábado)"
    elif weekday == 6 and hour < 18:  # Domingo antes de 6pm
        is_open = False
        reason = "Mercado cerrado (abre domingo 6pm ET)"
    elif weekday == 4 and hour >= 17:  # Viernes después de 5pm
        is_open = False
        reason = "Mercado cerrado (cierre viernes 5pm ET)"
    elif 17 <= hour < 18:  # Pausa diaria 5pm-6pm
        is_open = False
        reason = "Pausa diaria (5pm-6pm ET)"

    return {
        "is_open": is_open,
        "reason": reason,
        "time_et": now_et.strftime("%Y-%m-%d %H:%M:%S ET"),
        "weekday": now_et.strftime("%A"),
    }
