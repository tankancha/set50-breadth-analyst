# `docs/data/analysis.json` schema

The file this skill writes. The dashboard fetches it client-side and renders one card per series. The shape is **fixed by the committed sample** at `docs/data/analysis.json`. Match it exactly. On real runs, **omit `_sample`**.

```json
{
  "generated_at": "2026-06-27T23:20:00+07:00",
  "primary": "S50M26",
  "by_series": {
    "S50M26": {
      "symbol": "S50M26",
      "series_label": "Jun '26 (M)",
      "trading_date": "2026-06-27",
      "dte": 2,
      "spot_anchor": 1012.5,
      "regime": {
        "gamma_posture": "long",
        "zone": "Pinning",
        "iv_state": "compressed",
        "skew": "call-side rich near ATM",
        "label": "Dealer long-gamma pin into a 2-day expiry",
        "evidence": [
          "Net dealer gamma is positive around the 1010 ATM ...",
          "Max pain 990 sits below spot 1012.5 ...",
          "ATM IV 15.9% is low and there are only 2 sessions to expiry ..."
        ]
      },
      "breadth": {
        "pc_oi_ratio": 1.94,
        "pc_vol_ratio": 1.82,
        "max_pain": 990,
        "call_wall": 1080,
        "near_call_wall": 970,
        "put_wall": 780,
        "near_put_wall": 970,
        "gamma_flip": 1000,
        "one_sigma_move": 10.1,
        "iv_atm": 15.9,
        "iv_skew_25d": 4.6
      },
      "today_summary": "...2-4 sentences, lead with a number...",
      "what_changed": ["...", "..."],
      "five_day_thesis": "...<=5 sentences on what changed vs ~5 sessions ago...",
      "strategies": [
        {
          "name": "Iron condor 970P / 950P x 1030C / 1050C",
          "dir_axis": "neutral",
          "vol_axis": "short",
          "rationale": "...ties to this series' regime + KB...",
          "example_legs": ["+1 950 put", "-1 970 put", "-1 1030 call", "+1 1050 call"],
          "defined_risk": "Max loss = wing width (20) - net credit, per side.",
          "invalidation": "A close beyond the 970 put wall or the 1030 call strike."
        }
      ],
      "prediction": "...2-3 sentences; bias + the level that invalidates it...",
      "risk_note": "Educational only - not trade advice. SET50 options are cash-settled on the index, so pinning is weaker here than for physically-settled single stocks."
    }
  }
}
```

## Top level

| Field | Type | Rule |
|---|---|---|
| `generated_at` | string | ISO 8601 with `+07:00` (Asia/Bangkok). Required. |
| `primary` | string | The **front** series symbol - the lowest-DTE survivor. Drives which card the dashboard highlights. |
| `by_series` | object | Map of `SYMBOL -> series object`. One entry per **surviving** (non-stale) active series. |
| `_sample` | bool | Sample marker only. **Omit on real runs.** |

## `by_series[SYMBOL]`

| Field | Type | Rule |
|---|---|---|
| `symbol` | string | e.g. `S50M26`. |
| `series_label` | string | Human label, e.g. `Jun '26 (M)`. Derive from `quarter_code` + `last_trading_date` year. |
| `trading_date` | string | `YYYY-MM-DD` from `latest.json`. |
| `dte` | number | Days to `last_trading_date`. |
| `spot_anchor` | number | `future_last` (the SET50 future). |
| `regime` | object | See below. |
| `breadth` | object | See below. |
| `today_summary` | string | 2-4 sentences, lead with a number. |
| `what_changed` | string[] | <= 4 bullets, each starts with the thing that moved. |
| `five_day_thesis` | string | <= 5 sentences on cross-day deltas. Center of gravity. |
| `strategies` | object[] | 1-3 defined-risk structures. See below. |
| `prediction` | string | 2-3 sentences; directional bias + invalidation level. |
| `risk_note` | string | Educational disclaimer **+ the cash-settlement / weaker-pinning caveat**. |

## `regime`

| Field | Type | Allowed / rule |
|---|---|---|
| `gamma_posture` | string | `long` \| `short` \| `neutral`. Dealer gamma around the anchor. |
| `zone` | string | `Protection` \| `Squeeze` \| `Pinning` \| `Unwind`. |
| `iv_state` | string | `compressed` \| `normal` \| `elevated`. |
| `skew` | string | Short phrase, e.g. `put-rich (downside-protection bid)`. |
| `label` | string | One-line regime headline. |
| `evidence` | string[] | 2-4 bullets, each leads with a number. |

## `breadth`

All numbers. Round IVs/ratios to 1-2 dp, strikes to the 10-point grid.

| Field | Meaning |
|---|---|
| `pc_oi_ratio` | Put OI / Call OI (positioning bias). |
| `pc_vol_ratio` | Put Vol / Call Vol (today's flow). |
| `max_pain` | Anchor strike (min total intrinsic). |
| `call_wall` | Strike with the largest call OI overall (resistance). |
| `near_call_wall` | Largest call OI **above** spot within ~+/-5%. |
| `put_wall` | Strike with the largest put OI overall (support). |
| `near_put_wall` | Largest put OI **below/near** spot within ~+/-5%. |
| `gamma_flip` | Strike where cumulative net GEX crosses zero. |
| `one_sigma_move` | 1-sigma daily move in index points. |
| `iv_atm` | ATM implied vol, %. |
| `iv_skew_25d` | `IV(25d put) - IV(25d call)`. **Positive = put-rich.** |

## `strategies[]`

| Field | Type | Rule |
|---|---|---|
| `name` | string | Includes concrete strikes. |
| `dir_axis` | string | `bullish` \| `bearish` \| `neutral` \| `neutral-bullish` \| `bearish-hedge` ... (direction axis). |
| `vol_axis` | string | `short` \| `long` (volatility axis). |
| `rationale` | string | One sentence tying it to this series + the KB. |
| `example_legs` | string[] | Signed legs, e.g. `["-1 990 put", "+1 970 put"]`. |
| `defined_risk` | string | Explicit max loss in points. |
| `invalidation` | string | Price level that breaks the thesis. |

## Style

Concise, quantitative, every claim leads with a number. The dashboard renders this verbatim - over-long prose breaks the layout. No emoji.
