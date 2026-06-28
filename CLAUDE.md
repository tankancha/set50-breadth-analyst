# CLAUDE.md — set50-breadth-analyst

Agent instructions for this repo. The daily pipeline is **hybrid** (see README).

## If you are the cloud analysis routine

Use the **`set50-breadth-analyst`** skill in `.claude/skills/` — it is the source of truth for the analysis schema, computation rules, regime framework, and commit steps. In short:

1. `git pull`.
2. Read `docs/data/manifest.json`, then per active series read `docs/data/series/<SYMBOL>/latest.json`, `previous.json`, recent `history/*.json`.
3. **Staleness check** — skip a series whose `scraped_at` is missing, > 24 h old, or whose chain has < 5 rows. Never fabricate.
4. Compute breadth (PC ratios, max pain, OI walls, GEX gamma flip, 1σ move, delta bands, IV skew, 5-day deltas), classify the **dealer-gamma regime**, and map it to the direction × volatility strategy matrix.
5. Write `docs/data/analysis.json` per `references/analysis-schema.md`, commit, and push.

Lead every claim with a number. Educational only — **never advise executing trades**. Note that pinning is weaker for cash-settled index options.

## If you are working on the code

- Scraper is **Python + Playwright**; `scraper/series.py` is a pure, tested module — keep it dependency-free.
- The `docs/data/` JSON shapes are the contracts between scraper → dashboard → skill; change them deliberately and update all three sides + the README.
- Dashboard is static (Plotly from CDN, no build step); test it against committed JSON fixtures.
- Do **not** call Notion tools — the publication target is the JSON files + GitHub Pages.

## Don't

- Don't scrape from the cloud routine (it can't drive a browser); scraping is the GitHub Action's job.
- Don't commit secrets; the pipeline needs none (TFEX is public).
