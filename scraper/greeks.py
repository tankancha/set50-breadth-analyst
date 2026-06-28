"""Black-76 implied vol + Greeks for SET50 options on the SET50 future.

TFEX computes IV/Greeks client-side and gates that computation on a real
(non-automation) browser, so a headless scrape reliably gets option *prices*
(last/bid/ask) + OI/volume but not IV/Greeks. We reconstruct IV/Greeks from the
price + the futures anchor + DTE with the Black-76 model (options on a future).

All vols are returned in **percent** to match TFEX's display convention; delta
is signed (call 0..1, put -1..0). Pure stdlib (math + statistics.NormalDist).
"""
from __future__ import annotations

import math
from statistics import NormalDist

_N = NormalDist()
def _cdf(x): return _N.cdf(x)
def _pdf(x): return _N.pdf(x)

DEFAULT_R = 0.02  # Thai short rate; for short DTE the discount barely matters


def black76_price(F, K, T, r, sigma, is_call):
    """Undiscounted-forward Black-76 option price."""
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return max(0.0, (F - K) if is_call else (K - F))
    disc = math.exp(-r * T)
    srt = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / srt
    d2 = d1 - srt
    if is_call:
        return disc * (F * _cdf(d1) - K * _cdf(d2))
    return disc * (K * _cdf(-d2) - F * _cdf(-d1))


def implied_vol(price, F, K, T, r, is_call):
    """Invert Black-76 for sigma (decimal); None if undefined. Bisection."""
    if price is None or price <= 0 or T <= 0 or F <= 0 or K <= 0:
        return None
    disc = math.exp(-r * T)
    intrinsic = disc * max(0.0, (F - K) if is_call else (K - F))
    if price <= intrinsic + 1e-7:
        return None  # no extrinsic value → IV not identifiable
    lo, hi = 1e-4, 5.0
    if black76_price(F, K, T, r, hi, is_call) < price:
        return None  # price richer than 500% vol — bad/garbage quote
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if black76_price(F, K, T, r, mid, is_call) < price:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def greeks(F, K, T, r, sigma, is_call):
    """Black-76 Greeks. delta (signed), gamma, vega (per 1% vol), theta (per day)."""
    if T <= 0 or sigma <= 0 or F <= 0 or K <= 0:
        return {"delta": None, "gamma": None, "vega": None, "theta": None}
    disc = math.exp(-r * T)
    srt = sigma * math.sqrt(T)
    d1 = (math.log(F / K) + 0.5 * sigma * sigma * T) / srt
    d2 = d1 - srt
    nd1 = _pdf(d1)
    delta = disc * _cdf(d1) if is_call else -disc * _cdf(-d1)
    gamma = disc * nd1 / (F * srt)
    vega = disc * F * nd1 * math.sqrt(T) / 100.0  # per 1 percentage-point of vol
    term = -F * disc * nd1 * sigma / (2 * math.sqrt(T))
    if is_call:
        theta = (term + r * F * disc * _cdf(d1) - r * K * disc * _cdf(d2)) / 365.0
    else:
        theta = (term - r * F * disc * _cdf(-d1) + r * K * disc * _cdf(-d2)) / 365.0
    return {"delta": round(delta, 4), "gamma": round(gamma, 4),
            "vega": round(vega, 4), "theta": round(theta, 4)}


def fill_leg(leg, F, K, T, is_call, r=DEFAULT_R):
    """Fill a leg's iv (percent) + Greeks in-place if iv is missing, using the
    best available price (mid of bid/ask, else last). Returns the leg."""
    if leg.get("iv") is not None:
        return leg
    bid, ask, last = leg.get("bid"), leg.get("ask"), leg.get("last")
    price = (bid + ask) / 2.0 if (bid is not None and ask is not None and bid > 0 and ask > 0) else last
    sig = implied_vol(price, F, K, T, r, is_call)
    if sig is None:
        return leg
    leg["iv"] = round(sig * 100.0, 4)
    g = greeks(F, K, T, r, sig, is_call)
    for k in ("delta", "gamma", "vega", "theta"):
        if leg.get(k) is None:
            leg[k] = g[k]
    return leg


def fill_chain(chain, F, T, r=DEFAULT_R):
    """Fill missing IV/Greeks across a chain in-place. No-op for legs that
    already carry a scraped IV (we prefer TFEX's own values when present)."""
    if F is None or T is None or T <= 0:
        return chain
    for row in chain:
        K = row.get("strike")
        if K is None:
            continue
        if row.get("call"):
            fill_leg(row["call"], F, K, T, True, r)
        if row.get("put"):
            fill_leg(row["put"], F, K, T, False, r)
    return chain
