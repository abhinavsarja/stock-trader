"""Prior session close via Yahoo Finance (yfinance); caller supplies the ticker symbol."""

from __future__ import annotations

import re

import yfinance as yf


def normalize_ticker(ticker: str) -> str | None:
    """Sanitize structured LLM output to a plausible Yahoo symbol, or reject."""
    raw = ticker.strip().upper()
    raw = raw.replace(" ", "")
    if not raw or len(raw) > 12:
        return None
    # US-style symbols only (reject obvious junk).
    if not re.match(r"^[A-Z0-9][A-Z0-9.\-]*[A-Z0-9]$|^[A-Z]$", raw):
        return None
    return raw


def prior_close_summary(ticker: str) -> str:
    """Human-readable prior close line(s); `ticker` must be a validated symbol."""
    sym = normalize_ticker(ticker)
    if not sym:
        return f'Invalid ticker value `{ticker}` — supply a normalized US equity symbol.'

    try:
        hist = yf.Ticker(sym).history(period="2mo")
    except Exception as exc:
        return f"Price lookup failed for {sym}: {exc}"

    if hist.empty or "Close" not in hist.columns:
        return f"No OHLC history returned for `{sym}` (symbol may be wrong or illiquid)."

    closes = hist["Close"].dropna()
    if len(closes) < 2:
        last_px = closes.iloc[-1]
        dt = closes.index[-1].strftime("%Y-%m-%d")
        return f"{sym}: only one session in window — close ${last_px:.2f} ({dt})."

    last_px = closes.iloc[-1]
    prev_px = closes.iloc[-2]
    last_dt = closes.index[-1].strftime("%Y-%m-%d")
    prev_dt = closes.index[-2].strftime("%Y-%m-%d")
    return (
        f"{sym} previous session close ~${prev_px:.2f} (as of {prev_dt}); "
        f"latest bar in series ${last_px:.2f} ({last_dt})."
    )
