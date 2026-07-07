---
name: set50-breadth-analyst
description: Cloud-agent skill that turns scraped SET50 options breadth into a regime-based, defined-risk strategy narrative and commits it as JSON to the self-hosted GitHub Pages dashboard. Reads pre-scraped data from docs/data/series/<SYMBOL>/*.json. Triggers on requests for SET50 options market breadth, OI profile, implied volatility, gamma exposure / max pain, dealer-gamma regime, or the daily SET50 options report.
compatibility: Cloud Claude Code agent (no browser, no scraping). Hybrid architecture — a GitHub Actions Playwright scraper feeds docs/data/series/<SYMBOL>/{latest,previous,history/<date>}.json; this skill writes docs/data/analysis.json which the static dashboard reads in the browser. Optionally shells out to the sibling options-strategy-advisor (Black-Scholes) for payoff/Greeks, but never requires it.
---

# SET50 Breadth Analyst (Cloud Skill — JSON publisher)

Cloud-side of the SET50 Breadth pipeline. A GitHub Actions workflow scrapes TFEX SET50 options for each active futures series and commits per-day JSON snapshots under `docs/data/series/<SYMBOL>/`. This skill runs after the scraper, reads the active series + 5-session history, classifies the **dealer-gamma regime** for each, selects **defined-risk** structures, writes one `docs/data/analysis.json`, and pushes. The static dashboard fetches that JSON client-side and renders the visual report.

**This is educational analysis, not trade advice. NEVER advise executing trades.** Lead every claim with a number.

## What makes this skill different from generic options talk

The whole point is to speak the **forced-flow** framework from the knowledge base, not options clichés. Concretely:

- OI is a **burden map** ("แผนที่ภาระความเสี่ยง") — where risk is parked and who will be *forced* to hedge — not a directional signal (`reading-oi-with-option-logic.md`, `oi-requires-option-logic.md`, `open-interest.md`).
- The edge is **dealer long-gamma vs short-gamma**: long gamma → dealers fade moves → mean-reversion/pin; short gamma → dealers chase moves → momentum/squeeze (`option-heatmap-zones.md`, `oi-vol2vol-heatmap-edge.md`).
- Every series lands in one of **four zones — Protection / Squeeze / Pinning / Unwind** (`option-heatmap-zones.md`).
- OI must be filtered through **Vol2Vol** — real flow needs volume + OI build + IV move + price near strike, else the OI is stale/fake (`oi-vol2vol-heatmap-edge.md`).
- Strategy is chosen on **two axes — direction × volatility** — and every structure is just call/put legos (`option-strategy-building-blocks.md`).

If a paragraph could have been written without reading these files, rewrite it.

## Style

Professional, concise, expert-level — written for an options trader's morning scan. Lead every claim with a specific number (strike, OI, IV%, GEX, points). No disclaimers in the body prose, no boilerplate, no emoji. Narrate one plain-text sentence before every tool-call batch to keep the stream alive. No Notion — the publication target is the JSON file + GitHub Pages.

---

## Pass A — Read scraped data

→ text: "Pulling the SET50 options manifest and per-series snapshots…"

1. `git pull --rebase origin main || true` — get the freshest scraper output.
2. Read `docs/data/manifest.json` → `active_series[]`, `trading_date`, `updated`.
3. For **each** symbol in `active_series`, read:
   - `docs/data/series/<SYMBOL>/latest.json` (today's full chain)
   - `docs/data/series/<SYMBOL>/previous.json` (prior session — for 1-day deltas)
   - `docs/data/series/<SYMBOL>/history/<date>.json` for the last ~5 sessions if present (for the 5-day thesis). If the `history/` directory is empty, fall back to `previous.json` only and say so in the thesis.

The `latest.json` shape (see `references/analysis-schema.md` for the full field list):

```json
{
  "scraped_at": "2026-06-27T23:00:00+07:00",
  "trading_date": "2026-06-27",
  "symbol": "S50M26",
  "series_label": "2026-06 (M)",
  "quarter_code": "M",
  "last_trading_date": "2026-06-29",
  "future_last": 1012.5,
  "future_chg": -2,
  "iv_atm": 15.858,
  "atm_strike": 1010.0,
  "totals": {"call_oi": ..., "put_oi": ..., "call_vol": ..., "put_vol": ..., "pc_oi_ratio": ..., "pc_vol_ratio": ...},
  "max_pain": 990.0,
  "delta_bands": {"call_25d": 1020.0, "call_10d": 1030.0, "put_25d": 1000.0, "put_10d": 990.0},
  "one_sigma_move": 10.11,
  "chain": [{"strike": 1010.0, "call": {"oi","vol","last","bid","ask","iv","delta","gamma","vega","theta"}, "put": {...}}, ...]
}
```

**DTE** = trading days (or calendar days) from `trading_date` to `last_trading_date`. **Spot anchor** = `future_last` — the front SET50 future, used as a tradable proxy for the index; the SET50 cash index is usually `null` in the feed. (SET50 options are European and **cash-settled on the SET50 index** — see the cash-settlement caveat under Constraints.)

### Staleness check — per series, never fabricate

Skip a series and emit a one-line note (do NOT invent numbers) when **any** of:

- `scraped_at` is missing, or more than **24 hours** older than `manifest.updated`;
- `chain` has **fewer than 5 rows**;
- `future_last` is null.

Skipped-series note format: `"<SYMBOL>: data stale/thin (<reason>) — skipped."` Still publish the other series. If *all* active series are stale, write nothing, do not commit, and return: `"DATA UNAVAILABLE — scraper has not produced fresh data. Run skipped."`

---

## Computations

The scraper provides `max_pain`, `pc_oi_ratio`, `pc_vol_ratio`, `delta_bands`, `one_sigma_move` pre-computed — use them. Derive the rest from the `chain`. Full formulas in `references/computation-formulas.md`. **SET50 contract multiplier = 200 baht per index point** — use it for any GEX / notional figure.

- **P/C ratios** — `totals.pc_oi_ratio` (positioning bias) and `pc_vol_ratio` (today's flow). >1 = put-heavy. Read with caution: heavy put OI is often *hedging/support*, not a bearish call (`reading-oi-with-option-logic.md`).
- **Max pain** — use `max_pain`; if absent, minimize total intrinsic value across strikes (formula in references). Treat it as an **anchor, not a target** (`max-pain.md`).
- **Call wall / put wall** — strike with the single largest `call.oi` (resistance) and largest `put.oi` (support). **Near-money walls** = the largest call OI *above* spot and largest put OI *below* spot within ±~5% of the anchor — these matter more than a deep static wall (the 780 put wall in the sample is structural, not active).
- **GEX per strike** — `gex(s) = gamma(s) · OI(s) · multiplier`, signed **+ for calls, − for puts** (dealers are short the options the public is long). Sum calls and puts at each strike for net GEX. If `gamma` is null at a strike (deep ITM/OTM rows), treat its contribution as ~0.
- **Gamma flip** — scan strikes low→high; the strike where **cumulative net GEX crosses zero** is the flip. Below it dealers are typically short gamma (amplify); above it long gamma (dampen) (`option-pinning.md`, `option-heatmap-zones.md`).
- **1σ daily move** — use `one_sigma_move`; else `anchor · (iv_atm/100) / √252`.
- **Delta bands** — use `delta_bands`; the 16Δ ≈ 1σ one-sided, 10Δ/2.5Δ = tails (`delta-bands.md`). 25Δ marks the "normal range" edge.
- **IV skew (25Δ)** — `iv_skew_25d = IV(25Δ put) − IV(25Δ call)`. **Positive = put-rich** = downside-protection bid (the normal index state, `volatility-skew.md`, `implied-volatility-surface.md`); negative = call-rich = upside/FOMO.
- **5-day deltas** — from history: max-pain drift, call/put-wall migration, GEX sign flips, IV compression/expansion. These are the center of gravity of the thesis.

---

## Regime classification

For each surviving series, set `regime` from the data, in this order:

1. **Dealer gamma posture** — sign of net GEX around the anchor and where spot sits vs the gamma flip. `long` (positive net GEX at ATM → mean-reverting hedging), `short` (negative → trend-amplifying), or `neutral` (mixed / thin OI still forming). (`option-heatmap-zones.md`, `option-pinning.md`.)
2. **Zone** — one of:
   - **Pinning** — long gamma + heavy near-money OI + near expiry (low DTE); price magnetized toward max pain / big strike (`option-pinning.md`, `max-pain.md`).
   - **Protection** — put-rich skew, OI still building, no dominant near-money wall; downside-insurance demand (`volatility-skew.md`, `facebook-open-interest-options.md`). Typical of a young back-quarter (high DTE).
   - **Squeeze** — short gamma above/below a wall; a break forces dealers to hedge *with* the move → acceleration (`option-heatmap-zones.md`).
   - **Unwind** — OI falling fast vs prior sessions (history shows OI shrinking); the prior force is fading (`option-heatmap-zones.md`, `volume-vs-open-interest.md`).
3. **IV state** — `compressed` / `normal` / `elevated` from `iv_atm` (and vs the 5-day trend if available). Low IV + short DTE = structurally small realized range.
4. **Skew** — a short phrase from `iv_skew_25d` ("put-rich, downside-protection bid" / "call-side rich near ATM" / "balanced").
5. **Vol2Vol sanity** — before leaning on any wall, confirm it is *live*: volume entering + OI built + price near the strike. Flag stale walls (heavy OI but no volume, IV flat, price far) so they are not over-weighted (`oi-vol2vol-heatmap-edge.md`).

Compose `label` (one line) + `evidence[]` (2–4 numbered bullets, each leading with a number).

Then map regime → the **direction × volatility matrix** (`option-strategy-building-blocks.md`): decide the **direction axis** (bullish / bearish / neutral / hedge) and the **volatility axis** (short-vol if long-gamma pin + compressed IV; long-vol if short-gamma squeeze risk or cheap IV ahead of a catalyst). See `references/regime-strategy-matrix.md`.

---

## Strategy selection

Pick **1–3 defined-risk** SET50 structures per series, from `references/regime-strategy-matrix.md`. Each must have:

- `name` with concrete strikes (use the chain's 10-point grid),
- `dir_axis` + `vol_axis` (the two-axis position),
- `rationale` tying it to *this* series' regime and the KB,
- `example_legs[]` (e.g. `["-1 990 put", "+1 970 put"]`),
- `defined_risk` — the explicit max loss in points (e.g. "wing width 20 − net credit"),
- `invalidation` — the price level that breaks the thesis (usually a wall or the flip).

Rules:
- **Defined-risk only.** Spreads, iron condors, debit/credit verticals — never naked short options. Defined-risk ≠ risk-free; max loss is real (`short-volatility-risk.md`).
- Short-vol structures suit long-gamma pins + compressed IV; size small — short-vol payoff is negative-skew (small frequent gains, rare large losses) (`short-volatility-risk.md`).
- Long-vol / hedge structures suit short-gamma squeeze setups, Protection zones, or cheap IV before a catalyst.
- For payoff / Greeks / breakevens, optionally shell out to the sibling `options-strategy-advisor` Black-Scholes engine:
  `python3 <path>/options-strategy-advisor/scripts/black_scholes.py --stock-price <anchor> --strike <K> --days <DTE> --volatility <iv/100> [--option-type put]`.
  It is optional — if Python/the script is unavailable, compute payoff from intrinsic value and skip Greeks. Never block the run on it.

Educational framing only. Do not state position sizes in baht or tell the user to place a trade.

---

## Pass B — Write analysis JSON, commit, push

→ text: "Writing today's SET50 analysis to docs/data/analysis.json…"

Build the object **exactly** per `references/analysis-schema.md`:

- Top level: `generated_at` (ISO 8601 `+07:00`), `primary` (the **front** series — lowest DTE among survivors), `by_series` (one entry per surviving series).
- Each `by_series[SYMBOL]`: `symbol, series_label, trading_date, dte, spot_anchor, regime{gamma_posture, zone, iv_state, skew, label, evidence[]}, breadth{pc_oi_ratio, pc_vol_ratio, max_pain, call_wall, near_call_wall, put_wall, near_put_wall, gamma_flip, one_sigma_move, iv_atm, iv_skew_25d}, today_summary, what_changed[], five_day_thesis, strategies[], prediction, risk_note`.
- **Do NOT** include the `_sample` key on real runs.
- Keep `today_summary` ≤ 4 sentences, `evidence` ≤ 4, `what_changed` ≤ 4 bullets (each starts with the thing that moved), `five_day_thesis` ≤ 5 sentences referencing specific cross-day deltas.
- `five_day_thesis` is the center of gravity: spend words on what changed vs ~5 sessions ago (max-pain drift, wall migration, GEX sign flips, IV compression) — the user sees today's numbers above it on the dashboard.
- `risk_note` must include the cash-settlement caveat (next section).

→ `Write docs/data/analysis.json` (overwrite — only one analysis file exists at a time).

→ text: "Committing and pushing to GitHub Pages…"

```
git add docs/data/analysis.json
git commit -m "analysis: $(TZ=Asia/Bangkok date +%F)"
```

If the commit is a no-op (re-run, nothing changed), exit cleanly without retry.

Some cloud environments force this skill to develop on a per-run feature branch (e.g. `claude/<slug>`) instead of committing to `main` directly — GitHub Pages only serves `main`, so a commit stranded on a feature branch never reaches the dashboard. Self-heal at push time instead of assuming you're already on `main`:

```
git fetch origin main
BRANCH=$(git branch --show-current)

if [ "$BRANCH" = "main" ]; then
  git pull --rebase origin main || true
  git push origin main
else
  git push -u origin "$BRANCH"
  if git merge-base --is-ancestor origin/main HEAD; then
    # main hasn't moved since this branch was cut — safe fast-forward, no merge commit needed.
    git push origin HEAD:main
  else
    echo "main has diverged since this branch was cut — cannot fast-forward-merge analysis.json into main automatically. Report this in the run summary; a manual merge/PR is needed."
  fi
fi
```

The push (direct or fast-forwarded) triggers GitHub Pages to redeploy (~30s).

→ Return the dashboard URL and a one-line per-series regime summary. If the fast-forward wasn't possible, say so explicitly instead of implying the dashboard is live.

---

## Constraints

- Do NOT scrape or call `WebFetch` for market data — the cloud agent can't drive a browser; scraping is the GitHub Action's job.
- Do NOT call any Notion MCP tool — Notion is not the publication target.
- Do NOT write any local file other than `docs/data/analysis.json`.
- All user-facing times in Asia/Bangkok (UTC+7); ISO 8601 with `+07:00` in JSON.
- Lead every claim with a number; concise expert tone.
- **SET50 options are cash-settled on the SET50 index → there is no physical delivery, so pinning is structurally weaker than for single stocks that settle in shares.** State the pin as a *tendency*, not a guarantee, in every `risk_note` (`option-pinning.md`, `max-pain-failure-pattern.md`).
- Watch for **max-pain failure**: if the front series sits far from max pain near expiry with volume + IV expansion confirming the move, do NOT call mean-reversion — the real flow is beating the option structure (`max-pain-failure-pattern.md`).

## References

- `references/analysis-schema.md` — exact `analysis.json` shape, field by field.
- `references/computation-formulas.md` — max pain, GEX, gamma flip, 1σ, delta bands, IV skew (with the 200-baht multiplier).
- `references/regime-strategy-matrix.md` — dealer-gamma regime → direction×volatility → concrete defined-risk structure.
- `references/breadth-metric-playbook.md` — how to read each metric + the OI±price patterns.
- `references/heatmap-zones.md` — Protection / Squeeze / Pinning / Unwind + the Vol2Vol filter.
