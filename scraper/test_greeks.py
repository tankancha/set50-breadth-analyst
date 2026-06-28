"""Tests for the Black-76 IV/Greeks reconstruction.

Run: pytest scraper/  or  python scraper/test_greeks.py
"""
from __future__ import annotations

from greeks import black76_price, fill_chain, greeks, implied_vol


def test_iv_roundtrip():
    F, K, T, r = 1012.5, 1010, 2 / 365, 0.02
    price = black76_price(F, K, T, r, 0.18, True)
    iv = implied_vol(price, F, K, T, r, True)
    assert iv is not None and abs(iv - 0.18) < 1e-3


def test_iv_none_without_extrinsic():
    # A price at/below intrinsic carries no vol information.
    assert implied_vol(0.0, 1012.5, 1010, 2 / 365, 0.02, True) is None


def test_atm_delta_near_half():
    g = greeks(1010, 1010, 30 / 365, 0.02, 0.20, True)
    assert 0.45 < g["delta"] < 0.60
    gp = greeks(1010, 1010, 30 / 365, 0.02, 0.20, False)
    assert -0.60 < gp["delta"] < -0.40  # puts are negative-delta


def test_fill_chain_reconstructs_missing_only():
    chain = [{
        "strike": 1010,
        "call": {"oi": 1, "last": 6.0, "bid": 5.9, "ask": 8.5,
                 "iv": None, "delta": None, "gamma": None, "vega": None, "theta": None},
        "put": {"oi": 1, "last": 3.5, "bid": 3.4, "ask": 3.8,
                "iv": 99.0, "delta": -0.4, "gamma": None, "vega": None, "theta": None},
    }]
    fill_chain(chain, 1012.5, 2 / 365)
    c, p = chain[0]["call"], chain[0]["put"]
    # call was empty → reconstructed
    assert c["iv"] is not None and 8 < c["iv"] < 40
    assert 0.4 < c["delta"] < 0.7
    # put already had a scraped iv → left untouched (prefer TFEX's own value)
    assert p["iv"] == 99.0 and p["delta"] == -0.4


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
