"""Active-series selection for the SET50 quarterly options roll.

Pure functions: given a trading date and the TFEX ``/api/set/tfex/series/list``
payload, return the 1-2 active quarterly series symbols (H/M/U/Z) under the
roll rule.

Roll rule (matches the project spec):
    The next quarter becomes active on the **16th of the front series' expiry
    month**; the front series keeps being scraped until its own **last trading
    day**. So one series is active most of the time, and two overlap for the
    ~2 weeks between the 16th of the expiry month and the last trading day.

Worked example from the spec:
    series M (Jun) is scraped from 16 Mar (the 16th of H's expiry month, when
    M is added alongside H) through M's last trading day in late June; series U
    (Sep) is added on 16 Jun and runs to late September; and so on.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

# TFEX quarter codes -> expiry month. Serial months (N=Jul, Q=Aug, ...) are
# deliberately excluded: only these four are tracked.
QUARTER_CODES = {"H": 3, "M": 6, "U": 9, "Z": 12}  # Mar, Jun, Sep, Dec
_QUARTERLY_RE = re.compile(r"^S50([HMUZ])\d{2}$")


@dataclass(frozen=True)
class Series:
    symbol: str           # e.g. "S50M26"
    quarter_code: str     # "H" | "M" | "U" | "Z"
    expiry_year: int      # e.g. 2026
    expiry_month: int     # e.g. 6
    last_trading_date: date


def _parse_date(s: str) -> date:
    """Accept ``2026-06-29T16:30:00+07:00`` or ``2026-06-29``."""
    return datetime.fromisoformat(s).date()


def parse_quarterly_series(series_list: list[dict]) -> list[Series]:
    """Extract SET50 quarterly *futures* entries from a series-list payload.

    The roll is driven off the futures quarterly entries because they carry a
    clean ``symbol`` + ``lastTradingDate`` + ``contractMonth``, and the option
    series of the same root (e.g. ``S50M26``) shares that expiry. Individual
    option contracts (``S50M26C1010``) and serial months are filtered out.

    Returned list is de-duplicated by symbol and sorted by last trading date.
    """
    found: dict[str, Series] = {}
    for row in series_list:
        sym = str(row.get("symbol") or "").strip()
        m = _QUARTERLY_RE.match(sym)
        if not m:
            continue
        if str(row.get("underlying") or "") != "SET50":
            continue
        # Futures rows have a null strike; option contract rows carry a strike.
        if row.get("strikePrice") is not None:
            continue
        ltd = row.get("lastTradingDate")
        if not ltd:
            continue
        code = m.group(1)
        cm = str(row.get("contractMonth") or "").split("/")  # "06/2026"
        year = int(cm[1]) if len(cm) == 2 and cm[1].isdigit() else _parse_date(ltd).year
        found.setdefault(
            sym, Series(sym, code, year, QUARTER_CODES[code], _parse_date(ltd))
        )
    return sorted(found.values(), key=lambda s: s.last_trading_date)


def active_series(trading_date: date, series_list: list[dict]) -> list[str]:
    """Return the active quarterly series symbols for ``trading_date``.

    Front series = the nearest quarterly whose last trading day is on/after
    ``trading_date``. If ``trading_date`` is on/after the 16th of the front
    series' expiry month, the next quarter is also active (the roll overlap).
    """
    quarterly = parse_quarterly_series(series_list)
    upcoming = [s for s in quarterly if s.last_trading_date >= trading_date]
    if not upcoming:
        return []
    front = upcoming[0]
    active = [front.symbol]
    roll_start = date(front.expiry_year, front.expiry_month, 16)
    if trading_date >= roll_start and len(upcoming) >= 2:
        active.append(upcoming[1].symbol)
    return active
