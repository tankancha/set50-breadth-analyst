# Regime -> Strategy Matrix

How a dealer-gamma regime maps to a position on the **direction x volatility** matrix, and then to a concrete **defined-risk** SET50 structure. Every strategy is just call/put legos assembled to fit a two-axis view (`option-strategy-building-blocks.md`). Defined-risk only - never naked short options (`short-volatility-risk.md`).

## The two axes (the foundation)

From `option-strategy-building-blocks.md`: choosing an option strategy answers **two** questions, not one - direction (up/down/neither) **and** volatility (still vs violent).

|  | Directional | Direction-agnostic |
|---|---|---|
| **Long vol (bet on a big move)** | long call / put; debit vertical | straddle / strangle |
| **Short vol (bet on calm)** | covered call / cash-secured put (credit vertical) | iron condor |

The regime fixes both axes. **Long-gamma + compressed IV pushes you short-vol; short-gamma squeeze risk or cheap IV before a catalyst pushes you long-vol.**

## Regime -> axes -> structure

| Dealer gamma | Zone | IV state | Direction x Volatility | Defined-risk structure | Grounding |
|---|---|---|---|---|---|
| **Long** | Pinning | compressed | neutral x **short** | **Iron condor** outside the near-money walls; or a credit vertical leaning toward max pain | `option-pinning.md`, `max-pain.md`, `option-strategy-building-blocks.md` (iron condor = defined-risk short-vol) |
| **Long** | Pinning, spot above max pain | compressed | neutral-bullish x **short** | **Put credit spread** below spot toward the pin (sell near-money put, buy lower) | `max-pain.md`, building-blocks |
| **Long** | Pinning, spot below max pain | compressed | neutral-bearish x **short** | **Call credit spread** above spot toward the pin | `max-pain.md`, building-blocks |
| **Short** | Squeeze (break above call wall) | normal/elevated | bullish x **long** | **Call debit spread** above the wall (defined-risk momentum) | `heatmap-zones.md` (short gamma -> amplify), building-blocks (debit vertical = defined-risk directional) |
| **Short** | Squeeze (break below put wall) | normal/elevated | bearish x **long** | **Put debit spread** below the wall | `heatmap-zones.md`, building-blocks |
| **Short** | Squeeze, direction unclear, near catalyst | cheap/expanding | neutral x **long** | **Long strangle / straddle** (defined-risk = premium paid) - only when IV is cheap; mind IV crush | building-blocks, `iv-crush.md`, `short-volatility-risk.md` |
| **Neutral** | Protection (young series, put-rich, OI building) | normal | hedge / bearish-hedge x **long** | **Put debit spread** as cheap defined-risk downside insurance for the book | `volatility-skew.md`, `facebook-open-interest-options.md`, `implied-volatility-surface.md` |
| any | **Unwind** (OI falling fast) | any | reduce / stand aside | No new structure; flag that the prior force is fading | `heatmap-zones.md`, `volume-vs-open-interest.md` |
| **Long** | Pinning **but** max-pain **failure** confirmed | expanding | trade with the break, **long** | Debit spread in the break direction - do **not** fade toward max pain | `max-pain-failure-pattern.md` |

## Why short-vol structures are sized small

Short-vol payoff is **negative-skew**: small frequent gains, rare large losses ("เก็บเหรียญสิบตัดหน้าสิบล้อ", `short-volatility-risk.md`). Survival comes from **position size**, not prediction accuracy. Hence:
- always **defined-risk** (spread / condor), never naked - but **defined-risk != risk-free**; the capped max loss still happens;
- prefer condors/credit spreads only when IV is genuinely compressed and the long-gamma pin is intact;
- carry the cash-settlement caveat (below).

## Cash-settlement caveat (must appear in every risk_note)

SET50 options are **cash-settled on the SET50 index** - no physical share delivery. The dealer-hedging mechanics that drive pinning are weaker than for single stocks that settle in shares, so treat every pin/max-pain magnet as a **tendency, not a guarantee** (`option-pinning.md`, `max-pain-failure-pattern.md`). Macro/news flow can override the option structure outright.

## Note on the gamma-exposure concept

The KB references `[[gamma-exposure-and-dealer-hedging]]` as a wikilink, but no standalone file exists in `Option knowledge/`. Its substance is carried by `option-heatmap-zones.md` (long vs short gamma table), `option-pinning.md` (ATM short-gamma re-hedge mechanism, gamma -> infinity as t -> 0), and `oi-vol2vol-heatmap-edge.md`. Cite those for any dealer-gamma claim.
