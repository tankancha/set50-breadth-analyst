"""Tests for the pure active-series selector (seam #3).

Runnable two ways:
    pytest scraper/test_series.py
    python scraper/test_series.py     # plain-assert fallback, no pytest needed
"""
from __future__ import annotations

from datetime import date

from series import active_series, parse_quarterly_series

# Synthetic series-list payload: four quarterly futures + one serial month
# (S50N26 = July) that MUST be excluded, + an option contract row that MUST
# be ignored (it carries a strike).
SERIES_LIST = [
    {"symbol": "S50H26", "underlying": "SET50", "strikePrice": None,
     "contractMonth": "03/2026", "lastTradingDate": "2026-03-30T16:30:00+07:00"},
    {"symbol": "S50M26", "underlying": "SET50", "strikePrice": None,
     "contractMonth": "06/2026", "lastTradingDate": "2026-06-29T16:30:00+07:00"},
    {"symbol": "S50U26", "underlying": "SET50", "strikePrice": None,
     "contractMonth": "09/2026", "lastTradingDate": "2026-09-29T16:30:00+07:00"},
    {"symbol": "S50Z26", "underlying": "SET50", "strikePrice": None,
     "contractMonth": "12/2026", "lastTradingDate": "2026-12-29T16:30:00+07:00"},
    {"symbol": "S50N26", "underlying": "SET50", "strikePrice": None,  # serial, excluded
     "contractMonth": "07/2026", "lastTradingDate": "2026-07-30T16:30:00+07:00"},
    {"symbol": "S50M26C1010", "underlying": "SET50", "strikePrice": 1010,  # option, ignored
     "contractMonth": "06/2026", "lastTradingDate": "2026-06-29T16:30:00+07:00"},
]


def test_serial_and_option_rows_excluded():
    syms = [s.symbol for s in parse_quarterly_series(SERIES_LIST)]
    assert syms == ["S50H26", "S50M26", "S50U26", "S50Z26"]


def test_mid_quarter_single_series():
    # Early in H's life, before the 16th of March: only H is active.
    assert active_series(date(2026, 1, 10), SERIES_LIST) == ["S50H26"]


def test_roll_overlap_starts_on_the_16th():
    # 16 Mar: M is added alongside H (spec: "scrape series M during 16 March").
    assert active_series(date(2026, 3, 16), SERIES_LIST) == ["S50H26", "S50M26"]
    assert active_series(date(2026, 3, 20), SERIES_LIST) == ["S50H26", "S50M26"]


def test_after_front_expiry_next_becomes_sole_front():
    # 1 Apr: H has expired (LTD 30 Mar); M alone until its own roll.
    assert active_series(date(2026, 4, 1), SERIES_LIST) == ["S50M26"]


def test_june_overlap_adds_u():
    # 20 Jun: M still trading, U added (spec: "start scraping series U from 16 June").
    assert active_series(date(2026, 6, 20), SERIES_LIST) == ["S50M26", "S50U26"]


def test_expiry_day_still_includes_front():
    # On M's last trading day both M and U are active.
    assert active_series(date(2026, 6, 29), SERIES_LIST) == ["S50M26", "S50U26"]


def test_day_after_expiry_drops_front():
    assert active_series(date(2026, 6, 30), SERIES_LIST) == ["S50U26"]


if __name__ == "__main__":
    import sys

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e!r}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
