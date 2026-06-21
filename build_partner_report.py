"""
Partner Performance Reporting Pipeline  (synthetic-data demo)
=============================================================

A self-contained demonstration of an end-to-end reporting pipeline:

    monthly Excel "datagrid" exports  ->  tidy time-series  ->  interactive HTML report

The real pipeline at work runs on confidential partner data. This demo
generates its own SYNTHETIC data so the whole thing is runnable by anyone,
while showing the same techniques: incremental compilation, rolling
baseline-vs-recent comparison windows, and automatic riser/faller detection.

Run:
    pip install -r requirements.txt
    python build_partner_report.py

Outputs:
    data/Datagrid-<Month>.xlsx     synthetic monthly exports
    data/compiled_residuals.csv    tidy compiled time-series
    assets/residual_trend.svg      total residual by month
    assets/top_movers.svg          biggest risers & fallers
    Partner_Report.html            self-contained interactive report

Author: Sabbir  |  github.com/sab-bir08
"""
from __future__ import annotations

import calendar
import datetime as dt
import random
from pathlib import Path
from xml.sax.saxutils import escape as _xesc

import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
N_PARTNERS = 30
N_MONTHS = 13
SEED = 8  # reproducible synthetic data

# ---------------------------------------------------------------------------
# 1. Synthetic data generation  (stands in for the confidential datagrids)
# ---------------------------------------------------------------------------
WORDS_A = ["Riverside", "Metro", "Coastal", "Summit", "Oakwood", "Crown",
           "Harbour", "Vertex", "Maple", "Beacon", "Pinnacle", "Willow",
           "Granite", "Aurora", "Bridge", "Halcyon", "Ironside", "Cedar",
           "Northgate", "Sterling", "Linden", "Marble", "Quay", "Hollow",
           "Amber", "Thistle", "Verde", "Onyx", "Solace", "Ravenswood"]
WORDS_B = ["Retail", "Foods", "Motors", "Logistics", "Pharmacy", "Leisure",
           "Trading", "Hospitality", "Wholesale", "Services"]


def esc(s) -> str:
    """XML-escape text placed inside SVG <text> elements."""
    return _xesc(str(s))


def month_labels(n: int) -> list[str]:
    """Return the last `n` month labels ending at the current month."""
    today = dt.date.today().replace(day=1)
    labels, y, m = [], today.year, today.month
    for _ in range(n):
        labels.append(f"{calendar.month_abbr[m]}-{str(y)[2:]}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(labels))


def generate_datagrids() -> list[str]:
    """Create one synthetic Excel 'datagrid' per month and return the labels."""
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    labels = month_labels(N_MONTHS)

    partners = []
    for i in range(N_PARTNERS):
        name = f"{rng.choice(WORDS_A)} {rng.choice(WORDS_B)}"
        partners.append({
            "mid": 1000 + i,
            "partner": f"{name} (#{1000 + i})",
            "base": rng.uniform(400, 4500),      # baseline monthly residual (GBP)
            "trend": rng.uniform(-0.06, 0.07),    # monthly growth rate
            "noise": rng.uniform(0.04, 0.16),     # volatility
        })

    for month_idx, label in enumerate(labels):
        rows = []
        for p in partners:
            growth = (1 + p["trend"]) ** month_idx
            shock = 1 + rng.gauss(0, p["noise"])
            residual = max(0.0, p["base"] * growth * shock)
            volume = int(max(5, residual / rng.uniform(1.5, 4.0)))   # txn count
            turnover = residual * rng.uniform(45, 75)                # GBP processed
            rows.append({
                "MID": p["mid"],
                "Partner": p["partner"],
                "Transactions": volume,
                "Turnover (GBP)": round(turnover, 2),
                "Earnings- Local Currency": round(residual, 2),   # mirrors real column
            })
        pd.DataFrame(rows).to_excel(DATA / f"Datagrid-{label}.xlsx", index=False)
    return labels


# ---------------------------------------------------------------------------
# 2. Compile every monthly datagrid into one tidy time-series
# ---------------------------------------------------------------------------
def compile_datagrids(labels: list[str]) -> pd.DataFrame:
    frames = []
    for label in labels:
        d = pd.read_excel(DATA / f"Datagrid-{label}.xlsx")
        d = d.rename(columns={"Earnings- Local Currency": "Residual"})
        d["Month"] = label
        frames.append(d[["Month", "MID", "Partner", "Transactions",
                         "Turnover (GBP)", "Residual"]])
    tidy = pd.concat(frames, ignore_index=True)
    tidy["MonthOrder"] = tidy["Month"].map({m: i for i, m in enumerate(labels)})
    tidy.to_csv(DATA / "compiled_residuals.csv", index=False)
    return tidy


# ---------------------------------------------------------------------------
# 3. Rolling baseline-vs-recent comparison + riser/faller detection
# ---------------------------------------------------------------------------
def movers(tidy: pd.DataFrame, labels: list[str], window: int = 4) -> pd.DataFrame:
    base = (tidy[tidy.Month.isin(labels[:window])]
            .groupby(["MID", "Partner"]).Residual.mean())
    recent = (tidy[tidy.Month.isin(labels[-window:])]
              .groupby(["MID", "Partner"]).Residual.mean())
    out = pd.DataFrame({"baseline": base, "recent": recent}).reset_index()
    out["delta"] = out.recent - out.baseline
    out["pct"] = 100 * out.delta / out.baseline
    return out.sort_values("delta", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 4. Minimal, dependency-free SVG chart helpers
# ---------------------------------------------------------------------------
INK, GRID, ACCENT, UP, DOWN, MUTED = (
    "#1f2937", "#e5e7eb", "#2563eb", "#16a34a", "#dc2626", "#6b7280")


def _svg_header(w, h):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">'
            f'<rect width="{w}" height="{h}" fill="#ffffff"/>')


def line_chart_svg(labels, values, title) -> str:
    w, h, ml, mr, mt, mb = 720, 320, 56, 24, 48, 44
    pw, ph = w - ml - mr, h - mt - mb
    vmax, vmin = max(values) * 1.1, min(min(values) * 0.9, 0)
    def x(i): return ml + pw * i / (len(values) - 1)
    def y(v): return mt + ph * (1 - (v - vmin) / (vmax - vmin))
    s = [_svg_header(w, h)]
    s.append(f'<text x="{ml}" y="28" font-size="17" font-weight="700" fill="{INK}">{esc(title)}</text>')
    for g in range(5):
        gv = vmin + (vmax - vmin) * g / 4
        gy = y(gv)
        s.append(f'<line x1="{ml}" y1="{gy:.1f}" x2="{w-mr}" y2="{gy:.1f}" stroke="{GRID}"/>')
        s.append(f'<text x="{ml-8}" y="{gy+4:.1f}" font-size="11" text-anchor="end" fill="{MUTED}">&#163;{gv/1000:.0f}k</text>')
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values))
    s.append(f'<polygon points="{ml},{mt+ph} {pts} {w-mr},{mt+ph}" fill="{ACCENT}" opacity="0.08"/>')
    s.append(f'<polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="2.5"/>')
    for i, v in enumerate(values):
        s.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="{ACCENT}"/>')
        if i % 2 == 0:
            s.append(f'<text x="{x(i):.1f}" y="{h-mb+18}" font-size="10" text-anchor="middle" fill="{MUTED}">{esc(labels[i])}</text>')
    s.append('</svg>')
    return "".join(s)


def movers_chart_svg(top, bottom, title) -> str:
    rows = list(top.itertuples()) + list(bottom.itertuples())
    w, rowh, mt, ml = 720, 30, 52, 220
    h = mt + rowh * len(rows) + 16
    maxabs = max(abs(r.delta) for r in rows)
    zero, span = ml + 6, w - (ml + 6) - 90
    s = [_svg_header(w, h)]
    s.append(f'<text x="16" y="28" font-size="17" font-weight="700" fill="{INK}">{esc(title)}</text>')
    for i, r in enumerate(rows):
        cy = mt + i * rowh
        name = r.Partner if len(r.Partner) <= 30 else r.Partner[:29] + "…"
        bw = span * abs(r.delta) / maxabs
        col = UP if r.delta >= 0 else DOWN
        sign = "+" if r.delta >= 0 else "−"
        s.append(f'<text x="{ml-10}" y="{cy+15}" font-size="12" text-anchor="end" fill="{INK}">{esc(name)}</text>')
        s.append(f'<rect x="{zero}" y="{cy+4}" width="{bw:.1f}" height="16" rx="3" fill="{col}" opacity="0.85"/>')
        s.append(f'<text x="{zero+bw+8:.1f}" y="{cy+16}" font-size="11" fill="{col}" font-weight="600">{sign}&#163;{abs(r.delta):,.0f}</text>')
    s.append('</svg>')
    return "".join(s)


# ---------------------------------------------------------------------------
# 5. Self-contained interactive HTML report
# ---------------------------------------------------------------------------
def build_html(mv, labels, totals, trend_svg, movers_svg) -> str:
    recent, base = totals[-1], totals[0]
    pct = 100 * (recent - base) / base
    n_up, n_down = int((mv.delta > 0).sum()), int((mv.delta < 0).sum())
    rows = ""
    for r in pd.concat([mv.head(5), mv.tail(5)]).itertuples():
        col = "#16a34a" if r.delta >= 0 else "#dc2626"
        sign = "+" if r.delta >= 0 else "&minus;"
        rows += (f"<tr><td>{r.Partner}</td><td>&pound;{r.baseline:,.0f}</td>"
                 f"<td>&pound;{r.recent:,.0f}</td>"
                 f"<td style='color:{col};font-weight:600'>{sign}&pound;{abs(r.delta):,.0f} ({r.pct:+.0f}%)</td></tr>")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Partner Performance Report</title><style>
body{{font-family:Segoe UI,Helvetica,Arial,sans-serif;margin:0;background:#f8fafc;color:#1f2937}}
.wrap{{max-width:820px;margin:0 auto;padding:32px}}
h1{{font-size:24px;margin:0 0 4px}} .sub{{color:#6b7280;margin-bottom:24px}}
.kpis{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
.kpi{{flex:1;min-width:150px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px}}
.kpi .v{{font-size:26px;font-weight:700}} .kpi .l{{color:#6b7280;font-size:13px}}
.card{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #eef2f7}}
th{{color:#6b7280;font-weight:600}}</style></head><body><div class="wrap">
<h1>Partner Performance Report</h1>
<div class="sub">{labels[0]} &ndash; {labels[-1]} &middot; {N_PARTNERS} partners &middot; synthetic demo data</div>
<div class="kpis">
<div class="kpi"><div class="v">&pound;{recent:,.0f}</div><div class="l">Latest monthly residual</div></div>
<div class="kpi"><div class="v" style="color:{'#16a34a' if pct>=0 else '#dc2626'}">{pct:+.1f}%</div><div class="l">vs first month</div></div>
<div class="kpi"><div class="v" style="color:#16a34a">{n_up}</div><div class="l">Partners rising</div></div>
<div class="kpi"><div class="v" style="color:#dc2626">{n_down}</div><div class="l">Partners falling</div></div>
</div>
<div class="card">{trend_svg}</div>
<div class="card">{movers_svg}</div>
<div class="card"><h3 style="margin-top:0">Biggest movers (baseline vs recent)</h3>
<table><tr><th>Partner</th><th>Baseline</th><th>Recent</th><th>Change</th></tr>{rows}</table></div>
<p style="color:#9ca3af;font-size:12px">Generated by build_partner_report.py &middot; synthetic data &middot; no confidential information.</p>
</div></body></html>"""


def main():
    print("-> generating synthetic monthly datagrids ...")
    labels = generate_datagrids()
    print(f"   wrote {len(labels)} files to data/")

    print("-> compiling time-series ...")
    tidy = compile_datagrids(labels)
    print(f"   {len(tidy):,} partner-month rows compiled")

    totals = (tidy.groupby("MonthOrder").Residual.sum()
              .reindex(range(len(labels))).tolist())
    mv = movers(tidy, labels)

    ASSETS.mkdir(exist_ok=True)
    trend_svg = line_chart_svg(labels, totals, "Total monthly residual (GBP)")
    movers_svg = movers_chart_svg(mv.head(5), mv.tail(5).iloc[::-1],
                                  "Biggest risers and fallers (monthly change)")
    (ASSETS / "residual_trend.svg").write_text(trend_svg, encoding="utf-8")
    (ASSETS / "top_movers.svg").write_text(movers_svg, encoding="utf-8")
    (ROOT / "Partner_Report.html").write_text(
        build_html(mv, labels, totals, trend_svg, movers_svg), encoding="utf-8")

    print("\nTop 3 risers:")
    for r in mv.head(3).itertuples():
        print(f"   {r.Partner:<32} +GBP {r.delta:,.0f}/mo  ({r.pct:+.0f}%)")
    print("Top 3 fallers:")
    for r in mv.tail(3).iloc[::-1].itertuples():
        print(f"   {r.Partner:<32} -GBP {abs(r.delta):,.0f}/mo  ({r.pct:+.0f}%)")
    print("\nOK - wrote assets/*.svg and Partner_Report.html")


if __name__ == "__main__":
    main()
