"""Pure parsing + breadth math for the TFEX SET50 options board.

The I/O (rendering the board, clicking, fetching JSON) lives in ``run.py``.
Everything here is pure: it takes already-extracted table rows (lists of cell
strings) plus the futures anchor, and returns the ``latest.json`` dict. That
makes the breadth math unit-testable without a browser.

TFEX board column order (23 cells per strike row), confirmed against the live
board — Call legs on the left, Put legs mirrored on the right:

    0  call symbol      8  call bid        16 put delta
    1  call OI          9  call ask        17 put gamma
    2  call volume      10 call last       18 put vega
    3  call theta       11 STRIKE          19 put theta
    4  call vega        12 put last        20 put volume
    5  call gamma       13 put bid         21 put OI
    6  call delta       14 put ask         22 put symbol
    7  call IV          15 put IV
"""
from __future__ import annotations

import math

# Column indices
C_SYM, C_OI, C_VOL, C_THETA, C_VEGA, C_GAMMA, C_DELTA, C_IV = 0, 1, 2, 3, 4, 5, 6, 7
C_BID, C_ASK, C_LAST = 8, 9, 10
STRIKE = 11
P_LAST, P_BID, P_ASK, P_IV, P_DELTA, P_GAMMA, P_VEGA, P_THETA = 12, 13, 14, 15, 16, 17, 18, 19
P_VOL, P_OI, P_SYM = 20, 21, 22

_TRADING_DAYS = 252


def parse_num(s):
    """'-' / '' -> None; '15,973' -> 15973.0; '131.1541' -> 131.1541."""
    if s is None:
        return None
    s = str(s).strip().replace(",", "")
    if s in ("", "-", "N/A", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _leg(row, oi, vol, last, bid, ask, iv, delta, gamma, vega, theta):
    return {
        "oi": parse_num(row[oi]),
        "vol": parse_num(row[vol]),
        "last": parse_num(row[last]),
        "bid": parse_num(row[bid]),
        "ask": parse_num(row[ask]),
        "iv": parse_num(row[iv]),
        "delta": parse_num(row[delta]),
        "gamma": parse_num(row[gamma]),
        "vega": parse_num(row[vega]),
        "theta": parse_num(row[theta]),
    }


def series_of(row):
    """Series root from the call symbol, e.g. 'S50M26C1010' -> 'S50M26'."""
    sym = (row[C_SYM] or "").strip()
    return sym[:6] if len(sym) >= 7 else ""


def build_chain(rows, symbol):
    """Rows for one series -> sorted, de-duplicated chain of {strike, call, put}."""
    by_strike = {}
    for row in rows:
        if series_of(row) != symbol:
            continue
        strike = parse_num(row[STRIKE])
        if strike is None:
            continue
        by_strike[strike] = {
            "strike": strike,
            "call": _leg(row, C_OI, C_VOL, C_LAST, C_BID, C_ASK, C_IV, C_DELTA, C_GAMMA, C_VEGA, C_THETA),
            "put": _leg(row, P_OI, P_VOL, P_LAST, P_BID, P_ASK, P_IV, P_DELTA, P_GAMMA, P_VEGA, P_THETA),
        }
    return [by_strike[k] for k in sorted(by_strike)]


def _f(x):
    return x if isinstance(x, (int, float)) else 0.0


def totals(chain):
    call_oi = sum(_f(r["call"]["oi"]) for r in chain)
    put_oi = sum(_f(r["put"]["oi"]) for r in chain)
    call_vol = sum(_f(r["call"]["vol"]) for r in chain)
    put_vol = sum(_f(r["put"]["vol"]) for r in chain)
    return {
        "call_oi": call_oi,
        "put_oi": put_oi,
        "call_vol": call_vol,
        "put_vol": put_vol,
        "pc_oi_ratio": round(put_oi / call_oi, 4) if call_oi else None,
        "pc_vol_ratio": round(put_vol / call_vol, 4) if call_vol else None,
    }


def max_pain(chain):
    """Strike that minimises total option-holder intrinsic payout at expiry."""
    strikes = [r["strike"] for r in chain]
    best_k, best_pay = None, None
    for p in strikes:  # candidate expiry prices = listed strikes
        pay = 0.0
        for r in chain:
            k = r["strike"]
            pay += _f(r["call"]["oi"]) * max(0.0, p - k)
            pay += _f(r["put"]["oi"]) * max(0.0, k - p)
        if best_pay is None or pay < best_pay:
            best_pay, best_k = pay, p
    return best_k


def _nearest_strike_by_delta(chain, leg, target):
    """Strike whose |leg delta| is closest to target (e.g. 0.25, 0.10)."""
    best_k, best_d = None, None
    for r in chain:
        d = r[leg]["delta"]
        if d is None:
            continue
        diff = abs(abs(d) - target)
        if best_d is None or diff < best_d:
            best_d, best_k = diff, r["strike"]
    return best_k


def delta_bands(chain):
    return {
        "call_25d": _nearest_strike_by_delta(chain, "call", 0.25),
        "call_10d": _nearest_strike_by_delta(chain, "call", 0.10),
        "put_25d": _nearest_strike_by_delta(chain, "put", 0.25),
        "put_10d": _nearest_strike_by_delta(chain, "put", 0.10),
    }


def atm_strike(chain, anchor):
    if anchor is None or not chain:
        return None
    return min((r["strike"] for r in chain), key=lambda k: abs(k - anchor))


def atm_iv(chain, atm):
    for r in chain:
        if r["strike"] == atm:
            ivs = [v for v in (r["call"]["iv"], r["put"]["iv"]) if v is not None]
            return round(sum(ivs) / len(ivs), 4) if ivs else None
    return None


def one_sigma_move(anchor, iv_atm):
    if anchor is None or iv_atm is None:
        return None
    return round(anchor * (iv_atm / 100.0) / math.sqrt(_TRADING_DAYS), 2)


def assemble_series(symbol, rows, *, scraped_at, trading_date, series_meta, anchor):
    """Build the full ``latest.json`` dict for one series.

    ``series_meta`` is the matching :class:`series.Series`; ``anchor`` is the
    front-month future {last, change} (or None) used as the ATM reference.
    """
    chain = build_chain(rows, symbol)
    fut_last = (anchor or {}).get("last")
    atm = atm_strike(chain, fut_last)
    iv = atm_iv(chain, atm)
    return {
        "scraped_at": scraped_at,
        "trading_date": trading_date,
        "symbol": symbol,
        "series_label": f"{series_meta.expiry_year}-{series_meta.expiry_month:02d} ({series_meta.quarter_code})"
        if series_meta else symbol,
        "quarter_code": series_meta.quarter_code if series_meta else symbol[3:4],
        "last_trading_date": series_meta.last_trading_date.isoformat() if series_meta else None,
        "future_last": fut_last,
        "future_chg": (anchor or {}).get("change"),
        "underlying_index": (anchor or {}).get("underlying_index"),
        "atm_strike": atm,
        "iv_atm": iv,
        "totals": totals(chain),
        "max_pain": max_pain(chain),
        "delta_bands": delta_bands(chain),
        "one_sigma_move": one_sigma_move(fut_last, iv),
        "chain": chain,
    }
