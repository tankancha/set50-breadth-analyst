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


# Wait until IV/Greeks cells have actually populated. TFEX computes them
# client-side (the JSON API carries none), lazily as rows enter the viewport —
# so OI/vol/last appear immediately but IV/Greeks lag and only fill for visible
# rows. We use a tall viewport + scroll to force the compute, then poll the
# IV column (cell index 7 = call IV, 15 = put IV) until enough rows are filled.
_IV_READY_JS = """
() => {
  const t = document.querySelector('table'); if (!t) return false;
  let n = 0;
  for (const r of t.rows) {
    const c = r.cells; if (c.length < 23) continue;
    const civ = (c[7].innerText || '').trim();
    const piv = (c[15].innerText || '').trim();
    if ((civ && civ !== '-') || (piv && piv !== '-')) n++;
  }
  return n >= 8;
}
"""


def scrape_board() -> dict:
    """Render the TFEX board and return the capture dict. Live path."""
    from playwright.sync_api import sync_playwright  # imported lazily

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, args=["--disable-blink-features=AutomationControlled"],
        )
        # Stealth context. TFEX gates its client-side IV/Greeks computation on
        # automation signals: a real browser (navigator.webdriver === false) shows
        # IV + Greeks, but a vanilla Playwright launch (webdriver === true) renders
        # OI/vol/last and leaves IV/Greeks blank. Mask the signals + tall viewport.
        context = browser.new_context(
            viewport={"width": 1440, "height": 2400}, locale="th-TH",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
        )
        context.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "window.chrome=window.chrome||{runtime:{}};"
            "Object.defineProperty(navigator,'languages',{get:()=>['th-TH','th','en-US','en']});"
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
        )
        page = context.new_page()
        page.goto(BOARD_URL, wait_until="networkidle")
        # Expand every contract-month accordion.
        page.evaluate(
            "() => { const b=[...document.querySelectorAll('button,a,[role=button]')]"
            ".find(x=>/expand all/i.test(x.textContent||'')); if(b) b.click(); }"
        )
        page.wait_for_timeout(1500)
        # Scroll the whole page so lazily-computed IV/Greeks cells render.
        page.evaluate(
            "async () => { const h = document.body.scrollHeight;"
            " for (let y = 0; y <= h; y += 500) { window.scrollTo(0, y);"
            " await new Promise(r => setTimeout(r, 200)); } window.scrollTo(0, 0); }"
        )
        # Best-effort: if a real-browser environment serves IV quickly, grab it;
        # otherwise move on — extract.py reconstructs IV/Greeks via Black-76.
        try:
            page.wait_for_function(_IV_READY_JS, timeout=6000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
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
