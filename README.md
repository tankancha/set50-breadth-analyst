# SET50 Options Breadth Analysis

Daily breadth analysis for **TFEX SET50 index options** — EOD volume, open interest (OI), and implied volatility (IV) by strike — turned into a regime-based, defined-risk strategy guide. Sibling of [gold-breadth-analyst](https://github.com/tankancha/gold-breadth-analyst).

**Live dashboard:** https://tankancha.github.io/set50-breadth-analyst/ *(after Pages is enabled)*

## Architecture (hybrid)

```
GitHub Actions (Python + Playwright, 23:00 BKK Mon–Fri)
  renders the TFEX board → full chain incl. IV/Greeks → docs/data/series/<SYMBOL>/*.json
Anthropic cloud routine (set50-breadth-analyst skill, 23:20 BKK)
  reads JSON → dealer-gamma regime + strategies → docs/data/analysis.json
GitHub Pages (Investory light + Plotly)
  Volume / Open Interest (+IV +delta-bands) / OI-Change / Analytics
```

Why GitHub Actions scrapes instead of the cloud routine: the TFEX JSON API exposes only the top-5 most-active strikes with no IV/Greeks; the full chain with IV + Delta/Gamma/Vega/Theta exists only in the rendered board DOM, and the cloud agent can't drive a browser. See the vault ADR `0001`.

## Layout

| Path | What |
|------|------|
| `scraper/` | Python + Playwright EOD scraper. `series.py` = the pure active-series roll selector. |
| `docs/` | Static dashboard (GitHub Pages root): `index.html` + `assets/`. |
| `docs/data/` | The JSON database: `series/<SYMBOL>/{latest,previous,history/<date>}.json`, `manifest.json`, `analysis.json`. |
| `.github/workflows/scrape.yml` | Scheduled scrape (Slice 3). |
| `.claude/skills/set50-breadth-analyst/` | The analysis skill (Slice 7). |

## Series scope & roll

Quarterly series only — **H** (Mar), **M** (Jun), **U** (Sep), **Z** (Dec). The next quarter is added on the **16th of the front series' expiry month**; the front series is scraped until its **last trading day**. So one series is active most of the time, two overlap for ~2 weeks at each roll. Logic + tests: `scraper/series.py`, `scraper/test_series.py`.

## Data contract (per series, `docs/data/series/<SYMBOL>/`)

- `latest.json` — today's full chain + totals + `max_pain` + `delta_bands` + futures anchor (`scraped_at`, `trading_date`).
- `previous.json` — prior session (same schema) → the page computes per-strike OI change = latest − previous.
- `history/<date>.json` — dated archive of every session's full chain.
- `../../manifest.json` — `{ active_series: [...], updated }` (drives the series dropdown).
- `../../analysis.json` — the skill's output (regime + breadth + strategies).

Each chain row: `{ strike, call: {oi, vol, last, bid, ask, iv, delta, gamma, vega, theta}, put: {…} }`. IV/Greeks come from TFEX; deep-OTM blanks are `null`.

## Local dev

```bash
# selector tests (no deps)
python scraper/test_series.py            # or: pytest scraper/

# scraper (Slice 2+)
pip install -r scraper/requirements.txt && python -m playwright install chromium
python scraper/run.py

# dashboard
python -m http.server 8765 --directory docs   # open http://localhost:8765/
```

> Educational analysis only — never advises executing trades.
