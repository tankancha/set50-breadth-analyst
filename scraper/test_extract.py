"""Tests for the pure extraction + breadth math (seam #1).

Uses a committed real capture (2026-06-27) as a regression fixture, plus
hand-computed cases. Run: pytest scraper/  or  python scraper/test_extract.py
"""
from __future__ import annotations

import json
from pathlib import Path

from extract import assemble_series, build_chain, max_pain, parse_num, totals
from series import parse_quarterly_series

FIX = Path(__file__).parent / "fixtures" / "capture-2026-06-27.json"


def _cap():
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_parse_num():
    assert parse_num("-") is None
    assert parse_num("") is None
    assert parse_num(None) is None
    assert parse_num("15,973") == 15973.0
    assert parse_num("131.1541") == 131.1541
    assert parse_num("-0.0722") == -0.0722


def test_build_chain_maps_columns_from_real_board():
    chain = build_chain(_cap()["rows"], "S50M26")
    assert len(chain) == 31
    r = next(x for x in chain if x["strike"] == 1010)
    assert r["call"]["oi"] == 1701 and r["call"]["delta"] == 0.5306
    assert r["call"]["iv"] == 18.3437 and r["call"]["last"] == 6.0
    assert r["put"]["oi"] == 1711 and r["put"]["iv"] == 13.3723
    assert r["put"]["delta"] == -0.4691
    # deep-OTM blanks become None; the 780 put wall survives
    r780 = next(x for x in chain if x["strike"] == 780)
    assert r780["call"]["vol"] is None
    assert r780["put"]["oi"] == 15973


def test_totals_and_pc_ratio():
    t = totals(build_chain(_cap()["rows"], "S50M26"))
    assert t["call_oi"] == 28735 and t["put_oi"] == 55655
    assert round(t["pc_oi_ratio"], 2) == 1.94
    assert round(t["pc_vol_ratio"], 2) == 1.82


def test_max_pain_hand_computed():
    chain = [
        {"strike": 100, "call": {"oi": 0}, "put": {"oi": 10}},
        {"strike": 110, "call": {"oi": 5}, "put": {"oi": 5}},
        {"strike": 120, "call": {"oi": 10}, "put": {"oi": 0}},
    ]
    assert max_pain(chain) == 110  # zero total intrinsic payout at 110


def test_two_series_present_and_isolated():
    cap = _cap()
    m = build_chain(cap["rows"], "S50M26")
    u = build_chain(cap["rows"], "S50U26")
    assert len(m) == 31 and len(u) == 18
    assert {r["strike"] for r in m}.isdisjoint([]) and all(r["strike"] for r in u)


def test_assembled_schema_and_atm():
    cap = _cap()
    metas = {s.symbol: s for s in parse_quarterly_series(cap["quarterly"])}
    d = assemble_series(
        "S50M26", cap["rows"], scraped_at="2026-06-27T23:00:00+07:00",
        trading_date="2026-06-27", series_meta=metas["S50M26"],
        anchor={"last": 1012.5, "change": -2},
    )
    for k in ("scraped_at", "trading_date", "symbol", "future_last", "atm_strike",
              "iv_atm", "totals", "max_pain", "delta_bands", "one_sigma_move", "chain"):
        assert k in d, f"missing {k}"
    assert d["atm_strike"] == 1010
    assert d["max_pain"] == 990
    assert d["delta_bands"] == {"call_25d": 1020, "call_10d": 1030, "put_25d": 1000, "put_10d": 990}
    row = d["chain"][0]
    assert set(row) == {"strike", "call", "put"}
    assert set(row["call"]) == {"oi", "vol", "last", "bid", "ask", "iv", "delta", "gamma", "vega", "theta"}


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
