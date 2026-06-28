# Heatmap Zones & the Vol2Vol Filter

Distilled from `option-heatmap-zones.md` and `oi-vol2vol-heatmap-edge.md` (M traders). The edge is **not** predicting direction - it is reading **forced flow**: who will be *forced* to hedge/protect/unwind if price reaches a zone. OI is a **burden map** ("แผนที่ภาระความเสี่ยง"), not a directional signal.

## Dealer long gamma vs short gamma - the master switch

| Dealer posture | Price up | Price down | Effect on price |
|---|---|---|---|
| **Short gamma** | buys futures | sells futures | **amplifies** -> momentum / squeeze |
| **Long gamma** | sells futures | buys futures | **fades** -> mean-reversion / range / pin |

Determine posture from net GEX around the anchor and spot vs the gamma flip (`computation-formulas.md`). This single fact decides whether a thick-OI zone is an *accelerator* or a *magnet*. (Mechanism per `option-pinning.md`: dealers short gamma at the ATM strike re-hedge by buying low / selling high, pulling price back; ATM gamma -> infinity as t -> 0, so pins tighten near expiry.)

## The four zones

| Zone | Definition | Price behaviour | Maps to |
|---|---|---|---|
| **Protection** | Option used to insure a future/spot book; put (or call) OI thick as insurance. Often a young series still building OI, no dominant near-money wall. | Absorbs / cushions moves. | put-rich skew, high DTE -> `Protection`. (`facebook-open-interest-options.md`, `volatility-skew.md`) |
| **Squeeze** | A break through the wall forces dealers to hedge *with* the move. | Accelerates - momentum continuation. | short gamma beyond a wall -> `Squeeze`. |
| **Pinning** | Price magnetised toward a big strike, especially near expiry. | Range-bound around the strike / max pain. | long gamma + heavy near-money OI + low DTE -> `Pinning`. (`option-pinning.md`, `max-pain.md`) |
| **Unwind** | OI shrinking fast vs prior sessions - players closing. | Prior force fading; behaviour may change. | history shows OI falling -> `Unwind`. (`volume-vs-open-interest.md`) |

## Vol2Vol - separate real flow from fake

Thick OI alone lies: it may be stale, a spread, a hedge, or already priced in. Before leaning on any wall, confirm it is **live** across several dimensions at once:

> new **Volume** entering? + **OI** building (not falling)? + **IV** moving? + **Skew** tilting which way? + price **near** the strike? + near **expiry**? + does the **future** confirm?

- **Real flow:** price down + put volume up + put OI up + IV up -> genuine downside-insurance demand.
- **Fake flow:** heavy put OI but no volume + IV flat + price far from strike -> that zone has no current effect; do not weight it.

In the S50M26 sample, the 780 put wall (OI ~16,000) is **stale structural** (price far, no volume), while 970 (OI ~3,300) is the **live** near-money support - Vol2Vol is exactly what tells them apart.

## Limits - the edge is not always right

OI does not reveal who is long/short, hedge vs speculation, or whether it is a spread or a dead old position. A news / liquidity shock can overrun the option structure entirely (this is the **max-pain failure pattern**: price far from max pain near expiry + volume + IV expansion confirming = real flow wins; do **not** fade it). The edge is "a repeatable advantage in the right context", not 100% confidence - always combine with price action, future volume, IV change, skew, time-to-expiry, and position sizing.
