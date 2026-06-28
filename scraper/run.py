"""SET50 options EOD scraper — orchestrator.

Live (GitHub Actions):   python scraper/run.py
Offline (build/test):    python scraper/run.py --capture scraper/fixtures/capture-YYYY-MM-DD.json

The live path renders the TFEX board with Playwright and produces the same
"capture" dict the offline path loads from disk. All breadth math lives in
``extract.py`` (pure); all roll logic in ``series.py`` (pure). This file is the
thin I/O + file-writing shell.

Capture shape:
    {sessionDate, marketStatus, present:[...], quarterly:[{symbol,contractMonth,
     lastTradingDate,underlying,strikePrice}], futures:[{symbol,last,change}],
     rows:[[23 cell strings], ...]}
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

from extract import assemble_series, series_of
from series import active_series, parse_quarterly_series

BKK = timezone(timedelta(hours=7))
BOARD_URL = "https://www.tfex.co.th/th/products/equity/set50-index-options/market-data"
REPO_ROOT = Path(__file__).resolve().parent.parent

# JS run in the page to harvest the rendered chain + the JSON endpoints.
_HARVEST_JS = r"""
async () => {
  const QRE = /^S50[HMUZ]\d{2}$/;
  const t = document.querySelector('table');
  const allRows = t ? [...t.rows].map(r => [...r.cells].map(c => c.innerText.trim().replace(/\s+/g,' '))) : [];
  const rows = allRows.filter(r => r.length >= 23 && /^S50[HMUZ]\d{2}C/.test(r[0]||''));
  const fut = await (await fetch('/api/set/tfex/instrument/SET50_FC/overview',{headers:{accept:'application/json'}})).json();
  const sl  = await (await fetch('/api/set/tfex/series/list',{headers:{accept:'application/json'}})).json();
  const quarterly = (sl.series||[]).filter(s => QRE.test(s.symbol||'') && s.underlying==='SET50' && s.strikePrice==null)
    .map(s => ({symbol:s.symbol, contractMonth:s.contractMonth, lastTradingDate:s.lastTradingDate, underlying:s.underlying, strikePrice:s.strikePrice}));
  const futures = (fut.series||[]).map(s => ({symbol:s.symbol, last:s.last, change:s.change}));
  const present = [...new Set(rows.map(r => (r[0]||'').slice(0,6)))];
  return { sessionDate:(fut.marketTime||'').slice(0,10), marketStatus:fut.marketStatus, present, quarterly, futures, rows };
}
"""


def scrape_board() -> dict:
    """Render the TFEX board and return the capture dict. Live path."""
    from playwright.sync_api import sync_playwright  # imported lazily

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(BOARD_URL, wait_until="networkidle")
        # Expand every contract-month accordion, then let rows render.
        page.evaluate(
            "() => { const b=[...document.querySelectorAll('button,a,[role=button]')]"
            ".find(x=>/expand all/i.test(x.textContent||'')); if(b) b.click(); }"
        )
        page.wait_for_timeout(3000)
        capture = page.evaluate(_HARVEST_JS)
        browser.close()
    return capture


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_outputs(capture: dict, repo_root: Path = REPO_ROOT, scraped_at: str | None = None) -> list[str]:
    """Turn a capture into the docs/data JSON database. Returns written symbols."""
    if scraped_at is None:
        scraped_at = datetime.now(BKK).isoformat(timespec="seconds")
    rows = capture["rows"]
    quarterly = capture["quarterly"]
    trading_date = capture["sessionDate"]
    metas = {s.symbol: s for s in parse_quarterly_series(quarterly)}
    anchors = {f["symbol"]: f for f in capture.get("futures", [])}
    present = {series_of(r) for r in rows}

    active = active_series(date.fromisoformat(trading_date), quarterly)
    data_dir = repo_root / "docs" / "data"
    written: list[str] = []

    for sym in active:
        if sym not in present:
            continue  # active but no rows scraped (e.g. board not expanded) — skip, don't fabricate
        anchor = anchors.get(sym, {})
        latest = assemble_series(
            sym, rows, scraped_at=scraped_at, trading_date=trading_date,
            series_meta=metas.get(sym), anchor=anchor,
        )
        sdir = data_dir / "series" / sym
        latest_path = sdir / "latest.json"
        # Roll the prior session to previous.json (only when the date actually changed).
        if latest_path.exists():
            old = json.loads(latest_path.read_text(encoding="utf-8"))
            if old.get("trading_date") != trading_date:
                _write_json(sdir / "previous.json", old)
        _write_json(latest_path, latest)
        _write_json(sdir / "history" / f"{trading_date}.json", latest)
        written.append(sym)

    _write_json(data_dir / "manifest.json", {
        "active_series": written,
        "trading_date": trading_date,
        "updated": scraped_at,
    })
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description="SET50 options EOD scraper")
    ap.add_argument("--capture", help="build from a saved capture JSON instead of scraping live")
    ap.add_argument("--scraped-at", help="override scraped_at ISO timestamp (for reproducible fixtures)")
    args = ap.parse_args()

    capture = json.loads(Path(args.capture).read_text(encoding="utf-8")) if args.capture else scrape_board()
    if not capture.get("rows"):
        print("No rows scraped — leaving existing data untouched (staleness-safe).")
        return
    written = build_outputs(capture, scraped_at=args.scraped_at)
    print(f"Wrote {len(written)} series: {', '.join(written) or '(none)'} for {capture.get('sessionDate')}")


if __name__ == "__main__":
    main()
