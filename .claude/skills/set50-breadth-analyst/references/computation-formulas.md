# Computation Formulas

The scraper pre-computes `max_pain`, `pc_oi_ratio`, `pc_vol_ratio`, `delta_bands`, `one_sigma_move`. Use them. Recompute only if a field is missing. Everything else is derived from the `chain`.

**SET50 contract multiplier = 200 baht per index point.** Use it for any GEX / notional figure. SET50 options are options *on the SET50 future*, cash-settled on the index.

## Spot anchor & DTE

- **Anchor** = `future_last` (the SET50 future). The cash index (`underlying_index`) is usually `null`; do not depend on it.
- **DTE** = days from `trading_date` to `last_trading_date`.

## P/C ratios

```
pc_oi_ratio  = total_put_oi  / total_call_oi
pc_vol_ratio = total_put_vol / total_call_vol
```
`> 1` = put-heavy. OI ratio = standing positioning; vol ratio = today's flow. Heavy put OI is frequently hedging/support, not a bearish vote (see `breadth-metric-playbook.md`, `reading-oi-with-option-logic.md`).

## Max pain

For each candidate strike S in the chain:
```
pain(S) = SUM over x [ call_oi[x] * max(0, x - S) ]
        + SUM over x [ put_oi[x]  * max(0, S - x) ]
```
Max pain = the S with **minimum** pain. It is an **anchor, not a target** (`max-pain.md`). Restrict candidates to within ~+/-5% of the anchor for speed.

## Call / put walls

- **call_wall** = strike with the largest `call.oi` overall (resistance).
- **put_wall** = strike with the largest `put.oi` overall (support).
- **near_call_wall** = largest `call.oi` at a strike **above** the anchor, within ~+/-5%.
- **near_put_wall** = largest `put.oi` at a strike **below/near** the anchor, within ~+/-5%.

Near-money walls outrank deep static walls: in the S50M26 sample the overall put_wall is the deep **780** structural floor (OI ~16,000) but the *active* near-money put support is **970** (OI ~3,300). Report both; weight the near one. Validate liveness with Vol2Vol (`heatmap-zones.md`).

## GEX (gamma exposure) per strike

Dealers are net short the options the public is long, so:
```
gex_call(s) = + gamma_call(s) * call_oi(s) * 200
gex_put(s)  = - gamma_put(s)  * put_oi(s)  * 200
net_gex(s)  = gex_call(s) + gex_put(s)
```
- If `gamma` is null at a strike (deep ITM/OTM rows in the feed), treat its contribution as ~0.
- **Positive net GEX -> dealer long gamma** (price stabiliser; dampens moves).
- **Negative net GEX -> dealer short gamma** (price amplifier; accelerates moves).
(`option-heatmap-zones.md`, `option-pinning.md`.)

## Gamma flip

Scan strikes **low -> high**, accumulating `net_gex`. The **gamma flip** is the strike where the cumulative sum crosses zero.
- Below the flip: dealers typically **short gamma** (amplify).
- Above the flip: dealers typically **long gamma** (dampen).
Spot's position vs the flip + the sign of net GEX at the ATM sets `gamma_posture`.

## 1-sigma daily move

```
one_sigma_daily = anchor * (iv_atm / 100) / sqrt(252)
```
Use the scraper's `one_sigma_move` when present.

## Delta bands

From `delta_bands` (`call_25d`, `call_10d`, `put_25d`, `put_10d`). Delta ~ risk-neutral probability of finishing ITM, so the bands visualise the market's implied distribution (`delta-bands.md`):
- **16-delta ~ 1-sigma** one-sided; **10-delta / 2.5-delta** = progressively tail.
- **25-delta** marks the edge of the "normal range".

## IV skew (25-delta)

```
iv_skew_25d = IV(put @ put_25d strike) - IV(call @ call_25d strike)
```
- **Positive = put-rich** = downside-protection bid = the normal index state (`volatility-skew.md`, `implied-volatility-surface.md` - skew was born after Black Monday 1987; leverage effect + crashophobia keep OTM puts permanently dearer).
- **Negative = call-rich** = upside / FOMO.

## 5-day deltas (for the thesis)

From `history/<date>.json` (fall back to `previous.json` if history is empty):
- **max-pain drift** - direction + points moved.
- **wall migration** - call_wall / put_wall strike sequence across sessions.
- **GEX sign flips** - dealer regime change (long <-> short gamma) is the highest-signal event.
- **IV compression / expansion** - `iv_atm` trend; compression favours premium sellers, expansion favours buyers / warns of a catalyst (`iv-crush.md`).
