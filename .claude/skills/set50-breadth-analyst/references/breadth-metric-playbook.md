# Breadth Metric Playbook

How to read each metric in the SET50 chain. Distilled from the knowledge base; cited per rule. **Always lead with a number, and read OI as a burden map, not a verdict.**

## The cardinal rule: OI is a burden map, not a direction

The same OI number means opposite things depending on *who holds it and why* (`reading-oi-with-option-logic.md`, `oi-requires-option-logic.md`, `open-interest.md`):

| Held for | Effect as price nears the strike |
|---|---|
| Speculation (buy call/put) | supports the bought direction |
| Premium selling (sell call/put) | builds a **wall** - seller defends the strike |
| Hedge / dealer | re-hedge flow accelerates or pins price (`option-pinning.md`) |
| Spread / market-making | net effect depends on the book |

So: **Call OI high != must rise** (could be call sellers -> resistance). **Put OI high != must fall** (could be a hedge zone or put sellers -> support). Always ask: which strike, near spot?, near expiry?, what IV?, is price moving toward it with volume?

## OI x price pattern (positioning)

From `reading-oi-with-option-logic.md`:

| OI | Price | Likely meaning |
|---|---|---|
| up | flat | accumulating energy |
| up | up | new money on the up-side (strong uptrend) |
| up | down | hedging / bearish positioning building |
| down | up | short covering (weak uptrend) |
| down | down | long liquidation / de-risking |

## Volume vs OI

Volume resets each session; OI is cumulative state (`volume-vs-open-interest.md`, `open-interest.md`). Rising volume = activity intensity; rising OI = capital committing. **A breakout with expanding OI has fuel; a breakout with flat OI tends to fail.** Price-up + OI-flat often = closing of old positions (short covering), not new money - the chart looks identical but the meaning differs.

## P/C ratios

- `pc_oi_ratio` = standing positioning bias; `pc_vol_ratio` = today's flow.
- `> 1` = put-heavy, but in an index that is usually the structural **downside-protection** state, not a bearish signal - check whether the put OI is near-money/live or a deep static floor.

## Max pain

Anchor strike where total option intrinsic is minimised (`max-pain.md`). **Anchor, not a target.** Works as a magnet only when OI clusters, expiry is near, price is close, and no macro news overrides. Watch for the **failure pattern** (`max-pain-failure-pattern.md`): price far from max pain near expiry + supportive volume + IV expansion + macro flow = real demand/supply beating the option structure -> do not fade; the distant wall becomes the new target.

## Walls (support / resistance)

Largest put OI = support (`put_wall`); largest call OI = resistance (`call_wall`). Prefer the **near-money** wall (largest OI on the correct side within ~+/-5% of spot) over a deep static one. Validate with Vol2Vol before trusting it (`heatmap-zones.md`).

## GEX & gamma flip

Net GEX sign = dealer posture; the **gamma flip** strike splits short-gamma (below, amplifies) from long-gamma (above, dampens). This is the master switch for whether a zone accelerates or pins price (`heatmap-zones.md`, `option-pinning.md`). A **GEX sign flip across sessions is the single highest-signal change** for the 5-day thesis.

## IV level & state

IV is the **price of expected volatility**, not a forecast or a direction (`implied-volatility.md`, `iv-requires-option-oi-first.md`). High IV != must rise; high put IV != must fall. Compressed IV + short DTE = structurally small realised range (favours premium sellers); expanding IV warns of a catalyst and **IV crush** risk for buyers (`iv-crush.md`). OI filters IV's weight: high IV on thin OI is a noisy quote, not market logic (`options-learning-order-option-oi-iv.md`).

## IV skew (25-delta)

`IV(25d put) - IV(25d call)`. **Positive = put-rich** = downside-protection bid, the normal equity-index shape born after Black Monday 1987 (leverage effect + crashophobia, `implied-volatility-surface.md`, `volatility-skew.md`, `facebook-volatility-skew-smile.md`). A flattening put skew during a drop can precede a bounce (panic hedges monetised + dealer re-hedge). **Negative = call-rich** = FOMO / convex upside.

## Delta bands

Delta ~ probability of finishing ITM, so the bands are the market's implied distribution (`delta-bands.md`): 16d ~ 1-sigma one-sided, 10d / 2.5d = tails, 25d = edge of the normal range. Forward-looking, unlike ATR / Bollinger.

## Put-call parity sanity check

Covered call == cash-secured put in payoff (`put-call-parity.md`). Different names can hide the **same exposure** - read the real payoff, not the label, so the skill never double-counts the same short-vol bet under two names.
