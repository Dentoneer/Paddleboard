"""
Paddleboard Conditions Fetcher — DFW Area
Four locations tracked:
  1. Greenbelt / Pilot Point  (USGS 08051135) — Elm Fork below Lake Ray Roberts
  2. Elm Fork at Lewisville   (USGS 08053000) — Elm Fork tailwater
  3. White Rock Creek         (USGS 08057200) — Richardson/Dallas (~15 min from Richardson)
  4. Lake Ray Hubbard         (USGS 08061551) — E Fork Trinity below dam (lake outflow proxy)
"""

import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timezone

# ── Gauge definitions ─────────────────────────────────────────────────────────
# paddle_type: "river" uses CFS flow thresholds
#              "lake"  uses gentler thresholds (flat water — wind is the main concern)
GAUGES = [
    {
        "site_id":     "08051135",
        "label":       "Greenbelt (below Ray Roberts)",
        "short":       "Greenbelt",
        "color":       "#38bdf8",
        "lat":         33.3497222,
        "lon":         -97.0355556,
        "paddle_type": "river",
    },
    {
        "site_id":     "08053000",
        "label":       "Elm Fork at Lewisville",
        "short":       "Lewisville",
        "color":       "#a78bfa",
        "lat":         33.0456773,
        "lon":         -96.9611173,
        "paddle_type": "river",
    },
    {
        "site_id":     "08057200",
        "label":       "White Rock Creek (Richardson/Dallas)",
        "short":       "White Rock Creek",
        "color":       "#fb923c",
        "lat":         32.8893,
        "lon":         -96.7567,
        "paddle_type": "river",
    },
    {
        "site_id":     "08061551",
        "label":       "Lake Ray Hubbard (Garland/Rowlett)",
        "short":       "Ray Hubbard",
        "color":       "#f472b6",
        "lat":         32.8780,
        "lon":         -96.5450,
        "paddle_type": "lake",
    },
]

# ── Suggested launch / exit points ────────────────────────────────────────────
ROUTES = [
    {
        "gauge_site_id": "08051135",
        "name":   "Elm Fork Greenbelt Paddle",
        "color":  "#38bdf8",
        "launch": {
            "name": "FM 455 Greenbelt Trailhead (Ray Roberts Greenbelt)",
            "lat":   33.3806,
            "lon":  -97.0220,
        },
        "exit": {
            "name": "FM 428 Greenbelt Park",
            "lat":   33.3082,
            "lon":  -97.0406,
        },
        "notes": "River paddle through the Elm Fork Greenbelt corridor. Float with current; state park pass or $7 fee required.",
    },
    {
        "gauge_site_id": "08053000",
        "name":   "Elm Fork Below Lewisville Dam",
        "color":  "#a78bfa",
        "launch": {
            "name": "LLELA Kayak Launch (201 E. Jones St., Lewisville)",
            "lat":   33.0520,
            "lon":  -96.9720,
        },
        "exit": {
            "name": "Hebron Pkwy Kayak Launch (1105 Hebron Pkwy)",
            "lat":   33.0126,
            "lon":  -96.9507,
        },
        "notes": "Tailwater below Lewisville Dam. One-way downstream — arrange a shuttle at Hebron Pkwy. Check llela.org for current launch conditions.",
    },
    {
        "gauge_site_id": "08057200",
        "name":   "White Rock Creek Greenbelt",
        "color":  "#fb923c",
        "launch": {
            # Arapaho Rd crossing — public creek access in Richardson, ~15 min from Richardson center
            "name": "Arapaho Rd Creek Access (Richardson)",
            "lat":   32.9600,
            "lon":  -96.7495,
        },
        "exit": {
            # Greenville Ave bridge — USGS gauge location, good take-out point
            "name": "Greenville Ave Bridge (Dallas)",
            "lat":   32.8893,
            "lon":  -96.7567,
        },
        "notes": "Creek paddle through White Rock Creek Greenbelt. Beautiful wooded corridor through Richardson and Dallas. Flows into White Rock Lake. Best at 50+ CFS.",
    },
    {
        "gauge_site_id": "08061551",
        "name":   "Lake Ray Hubbard Open Water",
        "color":  "#f472b6",
        "launch": {
            # Winters Park Boat Ramp — free public launch, west shore, Garland
            "name": "Winters Park Boat Ramp (Garland)",
            "lat":   32.8662,
            "lon":  -96.5660,
        },
        "exit": {
            # Harbor Point Park — north shore, Rowlett, ~5.5 mi paddle across open water
            "name": "Harbor Point Park (Rowlett)",
            "lat":   32.9170,
            "lon":  -96.5390,
        },
        "notes": "Flat-water lake paddle on Lake Ray Hubbard. Open water — wind is the main concern. Many coves to explore along the shoreline. Return trip or arrange shuttle.",
    },
]

# ── Paddleboarding condition thresholds ───────────────────────────────────────
IDEAL_MIN_CFS = 100
IDEAL_MAX_CFS = 600
IDEAL_LABEL   = "100-600 CFS"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Helpers ───────────────────────────────────────────────────────────────────

def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)


def usgs_fetch(site, period, service="iv"):
    url = (
        f"https://waterservices.usgs.gov/nwis/{service}/"
        f"?sites={site}&parameterCd=00060,00065&period={period}&format=json"
    )
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return json.loads(r.read())
    except Exception as exc:
        print(f"  Warning: fetch failed for {site} ({service} {period}): {exc}", file=sys.stderr)
        return None


def extract_series(data, param_code):
    if not data:
        return []
    result = []
    for ts in data.get("value", {}).get("timeSeries", []):
        if ts["variable"]["variableCode"][0]["value"] == param_code:
            for v in ts["values"][0]["value"]:
                try:
                    result.append({"dt": v["dateTime"], "value": float(v["value"])})
                except (KeyError, ValueError):
                    pass
    return result


def daily_average(series):
    buckets = {}
    for pt in series:
        day = pt["dt"][:10]
        buckets.setdefault(day, []).append(pt["value"])
    return [{"dt": d, "value": round(sum(v) / len(v), 2)} for d, v in sorted(buckets.items())]


def classify_condition(cfs, paddle_type="river"):
    if cfs is None:
        return {"label": "Unknown",          "color": "#6b7280"}
    # Lake paddles: flat water — main risk is wind/flooding, not CFS
    if paddle_type == "lake":
        if cfs > 800:
            return {"label": "High Water - Caution", "color": "#eab308"}
        return {"label": "Good - Flat Water",        "color": "#22c55e"}
    # River paddles: CFS thresholds
    if cfs < 50:
        return {"label": "Too Low",          "color": "#ef4444"}
    if cfs < 100:
        return {"label": "Marginal",         "color": "#f97316"}
    if cfs < 300:
        return {"label": "Good",             "color": "#22c55e"}
    if cfs < 600:
        return {"label": "Ideal",            "color": "#3b82f6"}
    if cfs < 1000:
        return {"label": "Fast / Caution",   "color": "#eab308"}
    return     {"label": "Dangerous",        "color": "#dc2626"}


def group_by_doy(series, year):
    out = {}
    for pt in series:
        if pt["dt"][:4] == str(year):
            out[pt["dt"][5:10]] = pt["value"]
    return out


# ── Per-gauge fetch ───────────────────────────────────────────────────────────

def fetch_gauge(g):
    site = g["site_id"]
    print(f"  [{g['short']}] current conditions...")
    iv_raw  = usgs_fetch(site, "P2D", "iv")
    flow_iv = extract_series(iv_raw, "00060")
    gage_iv = extract_series(iv_raw, "00065")

    latest_flow = flow_iv[-1]["value"] if flow_iv else None
    latest_gage = gage_iv[-1]["value"] if gage_iv else None
    latest_dt   = flow_iv[-1]["dt"]    if flow_iv else datetime.now(timezone.utc).isoformat()
    condition   = classify_condition(latest_flow, g.get("paddle_type", "river"))
    print(f"         Flow: {latest_flow} CFS  |  Gage: {latest_gage} ft  |  {condition['label']}")

    print(f"  [{g['short']}] 13-week history...")
    hist_raw  = usgs_fetch(site, "P91D", "iv")
    hist_flow = daily_average(extract_series(hist_raw, "00060"))
    hist_gage = daily_average(extract_series(hist_raw, "00065"))

    print(f"  [{g['short']}] year-over-year...")
    yoy_raw   = usgs_fetch(site, "P730D", "dv")
    yoy_flow  = extract_series(yoy_raw, "00060")
    this_year  = datetime.now().year
    prior_year = this_year - 1
    yoy_this   = group_by_doy(yoy_flow, this_year)
    yoy_prior  = group_by_doy(yoy_flow, prior_year)
    all_mds    = sorted(set(yoy_this) | set(yoy_prior))

    return {
        "site_id":        site,
        "label":          g["label"],
        "short":          g["short"],
        "color":          g["color"],
        "lat":            g["lat"],
        "lon":            g["lon"],
        "paddle_type":    g.get("paddle_type", "river"),
        "latest_flow":    latest_flow,
        "latest_gage":    latest_gage,
        "latest_dt":      latest_dt,
        "condition":      condition,
        "hist_flow":      hist_flow,
        "hist_gage":      hist_gage,
        "yoy_labels":     all_mds,
        "yoy_this":       [yoy_this.get(md)  for md in all_mds],
        "yoy_prior":      [yoy_prior.get(md) for md in all_mds],
        "yoy_this_year":  this_year,
        "yoy_prior_year": prior_year,
    }


def fetch_all():
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    gauges = [fetch_gauge(g) for g in GAUGES]

    routes = []
    for r in ROUTES:
        d = haversine_miles(r["launch"]["lat"], r["launch"]["lon"],
                            r["exit"]["lat"],   r["exit"]["lon"])
        river_est = round(d * 1.45, 1)  # ~1.45x sinuosity for Elm Fork/creek
        routes.append({**r, "straight_miles": d, "river_est_miles": river_est})

    return {
        "fetched_at":  fetched_at,
        "ideal_min":   IDEAL_MIN_CFS,
        "ideal_max":   IDEAL_MAX_CFS,
        "ideal_label": IDEAL_LABEL,
        "gauges":      gauges,
        "routes":      routes,
    }


# ── HTML helpers ──────────────────────────────────────────────────────────────

def condition_card_html(g, ideal_label):
    cond       = g["condition"]
    flow       = g["latest_flow"]
    gage       = g["latest_gage"]
    is_lake    = g.get("paddle_type") == "lake"
    fs         = f"{flow:.1f} CFS" if flow is not None else "N/A"
    gs         = f"{gage:.2f} ft"  if gage is not None else "N/A"
    pct        = min(100, (flow or 0) / 10)
    type_badge = (
        '<span style="font-size:0.65rem;background:#0ea5e9;color:#0f172a;'
        'font-weight:700;padding:2px 8px;border-radius:999px;margin-left:8px;'
        'vertical-align:middle;">LAKE</span>'
        if is_lake else
        '<span style="font-size:0.65rem;background:#6366f1;color:#fff;'
        'font-weight:700;padding:2px 8px;border-radius:999px;margin-left:8px;'
        'vertical-align:middle;">RIVER</span>'
    )
    flow_label  = "Outflow (CFS)" if is_lake else "Flow Rate (CFS)"
    third_label = "Check Wind Forecast" if is_lake else ideal_label
    third_val   = "wind.com" if is_lake else ideal_label
    bar_html    = "" if is_lake else f"""
    <div class="range-bar-wrap">
      <div class="row">
        <span>0 CFS</span><span>Ideal: {ideal_label}</span><span>1000+ CFS</span>
      </div>
      <div class="range-bar">
        <div class="ideal-zone"></div>
        <div class="fill" style="width:{pct:.1f}%; background:{cond['color']};"></div>
      </div>
      <div class="range-legend">
        <span>Too Low</span><span>Marginal</span><span>Good</span><span>Ideal</span><span>Fast</span><span>Danger</span>
      </div>
    </div>"""
    wind_note   = (
        '<div style="margin-top:12px;font-size:0.73rem;color:var(--muted);'
        'background:var(--surface2);border-radius:8px;padding:8px 12px;">'
        '&#127788; Flat water — conditions are almost always paddleable. '
        'Main risk is wind. Check forecast before heading out.</div>'
        if is_lake else ""
    )
    return f"""
    <h2>Current Conditions &mdash; {g["short"]} {type_badge}</h2>
    <div style="font-size:0.68rem;color:var(--muted);margin-bottom:10px;">USGS {g["site_id"]}</div>
    <div class="status-pill" style="background:{cond['color']}22; color:{cond['color']}; border:1px solid {cond['color']}44;">
      {cond['label']}
    </div>
    <div class="metrics">
      <div class="metric">
        <div class="val" style="color:{cond['color']}">{fs}</div>
        <div class="lbl">{flow_label}</div>
      </div>
      <div class="metric">
        <div class="val" style="color:var(--accent)">{gs}</div>
        <div class="lbl">Gauge Height</div>
      </div>
      <div class="metric">
        <div class="val" style="color:var(--muted);font-size:{'0.8rem' if is_lake else '1rem'};">{third_val}</div>
        <div class="lbl">{third_label}</div>
      </div>
    </div>
    {bar_html}
    {wind_note}
    <p class="ts">Reading as of {g["latest_dt"][:16].replace("T", " ")} UTC</p>"""


# ── HTML builder ──────────────────────────────────────────────────────────────

def build_html(data):
    j      = json.dumps(data, indent=2)
    gauges = data["gauges"]
    this_y  = gauges[0]["yoy_this_year"]
    prior_y = gauges[0]["yoy_prior_year"]

    cards = "".join(
        f'<div class="card">{condition_card_html(g, data["ideal_label"])}</div>'
        for g in gauges
    )

    hist_canvases = "".join(
        f'<div class="card"><h2>{g["short"]}</h2>'
        f'<div class="chart-wrap"><canvas id="hist{i}"></canvas></div></div>'
        for i, g in enumerate(gauges)
    )
    yoy_canvases = "".join(
        f'<div class="card"><h2>{g["short"]} &mdash; {prior_y} vs {this_y}</h2>'
        f'<div class="chart-wrap"><canvas id="yoy{i}"></canvas></div></div>'
        for i, g in enumerate(gauges)
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Paddleboard Conditions - Elm Fork &amp; Hickory Creek</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg:       #0f172a;
    --surface:  #1e293b;
    --surface2: #273549;
    --border:   #334155;
    --text:     #e2e8f0;
    --muted:    #94a3b8;
    --accent:   #38bdf8;
    --radius:   12px;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 20px;
  }}
  header {{ text-align: center; margin-bottom: 24px; }}
  header h1 {{
    font-size: 1.6rem; font-weight: 700;
    background: linear-gradient(135deg, #38bdf8, #818cf8);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
  }}
  header p {{ color: var(--muted); font-size: 0.85rem; margin-top: 4px; }}

  .outer {{ display: grid; gap: 16px; max-width: 1400px; margin: 0 auto; }}

  /* Three equal columns for gauge rows */
  .trio {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
  }}
  .card h2 {{
    font-size: 0.72rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: .08em; color: var(--muted); margin-bottom: 14px;
  }}

  .status-pill {{
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 16px; border-radius: 999px;
    font-size: 1.05rem; font-weight: 700; margin-bottom: 16px;
  }}

  .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; }}
  .metric {{ flex: 1; min-width: 80px; }}
  .metric .val {{ font-size: 1.8rem; font-weight: 800; line-height: 1; }}
  .metric .lbl {{ font-size: 0.72rem; color: var(--muted); margin-top: 4px; }}

  .range-bar-wrap {{ margin-top: 16px; }}
  .range-bar-wrap .row {{
    display: flex; justify-content: space-between;
    font-size: 0.7rem; color: var(--muted); margin-bottom: 6px;
  }}
  .range-bar {{
    height: 10px; background: var(--surface2);
    border-radius: 999px; overflow: hidden; position: relative;
  }}
  .range-bar .ideal-zone {{
    position: absolute; left: 10%; width: 50%;
    height: 100%; background: rgba(59,130,246,.25); border-radius: 999px;
  }}
  .range-bar .fill {{ height: 100%; border-radius: 999px; transition: width .6s ease; }}
  .range-legend {{
    display: flex; justify-content: space-between;
    font-size: 0.66rem; color: var(--muted); margin-top: 5px;
  }}

  .ts {{ font-size: 0.7rem; color: var(--muted); margin-top: 10px; }}

  #map {{ height: 380px; border-radius: 8px; overflow: hidden; }}

  /* Route legend below map */
  .route-legend {{
    display: flex; flex-wrap: wrap; gap: 12px; margin-top: 14px;
  }}
  .route-badge {{
    display: flex; align-items: flex-start; gap: 10px;
    background: var(--surface2); border-radius: 8px; padding: 10px 14px;
    flex: 1; min-width: 240px;
  }}
  .route-badge .rb-dot {{
    width: 12px; height: 12px; border-radius: 50%;
    margin-top: 3px; flex-shrink: 0;
  }}
  .route-badge .rb-name {{ font-size: 0.8rem; font-weight: 700; }}
  .route-badge .rb-detail {{ font-size: 0.72rem; color: var(--muted); margin-top: 3px; line-height: 1.5; }}
  .route-badge .rb-dist {{ font-size: 0.78rem; font-weight: 700; color: var(--accent); margin-top: 4px; }}

  .chart-wrap {{ position: relative; height: 210px; }}

  .section-label {{
    font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .1em; color: var(--muted); padding: 4px 0 2px;
  }}

  .guide-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 8px; margin-top: 4px;
  }}
  .guide-item {{
    background: var(--surface2); border-radius: 8px;
    padding: 10px 12px; font-size: 0.78rem;
  }}
  .guide-item .g-label {{ font-weight: 600; margin-bottom: 2px; }}
  .guide-item .g-range {{ color: var(--muted); font-size: 0.72rem; }}

  @media (max-width: 900px) {{
    .trio {{ grid-template-columns: 1fr; }}
    .metric .val {{ font-size: 1.5rem; }}
  }}
</style>
</head>
<body>

<header>
  <h1>&#127940; Paddleboard Conditions</h1>
  <p>Elm Fork Trinity River &amp; Hickory Creek &middot; Updated {data["fetched_at"]}</p>
</header>

<div class="outer">

  <!-- ── Current conditions: 3 columns ── -->
  <div class="trio">{cards}</div>

  <!-- ── Map with gauges + launch/exit points ── -->
  <div class="card">
    <h2>Gauge Locations &amp; Suggested Paddling Routes</h2>
    <div id="map"></div>
    <div class="route-legend" id="routeLegend"></div>
  </div>

  <!-- ── 13-week history: 3 columns ── -->
  <div class="section-label">13-Week Flow History (Daily Average CFS)</div>
  <div class="trio">{hist_canvases}</div>

  <!-- ── Year-over-year: 3 columns ── -->
  <div class="section-label">Year-over-Year Comparison &mdash; {prior_y} vs {this_y}</div>
  <div class="trio">{yoy_canvases}</div>

  <!-- ── Condition guide ── -->
  <div class="card">
    <h2>Paddleboarding Condition Guide &mdash; River Gauges &nbsp;
      <span style="font-size:0.65rem;background:#6366f1;color:#fff;font-weight:700;padding:2px 8px;border-radius:999px;">RIVER</span>
      &nbsp;&nbsp;Lake paddles
      <span style="font-size:0.65rem;background:#0ea5e9;color:#0f172a;font-weight:700;padding:2px 8px;border-radius:999px;">LAKE</span>
      are always paddleable — check wind only
    </h2>
    <div class="guide-grid">
      <div class="guide-item" style="border-left:3px solid #ef4444;">
        <div class="g-label" style="color:#ef4444;">Too Low</div>
        <div class="g-range">&lt; 50 CFS</div>
        <div style="margin-top:4px;font-size:0.73rem;">Shallow, rocky, dragging boards</div>
      </div>
      <div class="guide-item" style="border-left:3px solid #f97316;">
        <div class="g-label" style="color:#f97316;">Marginal</div>
        <div class="g-range">50-100 CFS</div>
        <div style="margin-top:4px;font-size:0.73rem;">Some sections passable</div>
      </div>
      <div class="guide-item" style="border-left:3px solid #22c55e;">
        <div class="g-label" style="color:#22c55e;">Good</div>
        <div class="g-range">100-300 CFS</div>
        <div style="margin-top:4px;font-size:0.73rem;">Good depth, easy paddling</div>
      </div>
      <div class="guide-item" style="border-left:3px solid #3b82f6;">
        <div class="g-label" style="color:#3b82f6;">Ideal</div>
        <div class="g-range">300-600 CFS</div>
        <div style="margin-top:4px;font-size:0.73rem;">Best conditions &mdash; fun flow</div>
      </div>
      <div class="guide-item" style="border-left:3px solid #eab308;">
        <div class="g-label" style="color:#eab308;">Fast / Caution</div>
        <div class="g-range">600-1000 CFS</div>
        <div style="margin-top:4px;font-size:0.73rem;">Strong current, experienced only</div>
      </div>
      <div class="guide-item" style="border-left:3px solid #dc2626;">
        <div class="g-label" style="color:#dc2626;">Dangerous</div>
        <div class="g-range">&gt; 1000 CFS</div>
        <div style="margin-top:4px;font-size:0.73rem;">Stay off the water</div>
      </div>
    </div>
  </div>

</div>

<script>
const DATA = {j};
const G    = DATA.gauges;
const IDEAL_MIN = DATA.ideal_min;
const IDEAL_MAX = DATA.ideal_max;

// ── Map ───────────────────────────────────────────────────────────────────────
const allLats = G.map(g => g.lat).concat(DATA.routes.flatMap(r => [r.launch.lat, r.exit.lat]));
const allLons = G.map(g => g.lon).concat(DATA.routes.flatMap(r => [r.launch.lon, r.exit.lon]));
const bounds  = [[Math.min(...allLats) - 0.02, Math.min(...allLons) - 0.02],
                 [Math.max(...allLats) + 0.02, Math.max(...allLons) + 0.02]];

const map = L.map('map').fitBounds(bounds);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap contributors', maxZoom: 18
}}).addTo(map);

// Gauge marker (teardrop, colored by condition)
function gaugeIcon(color) {{
  return L.divIcon({{
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
      <path d="M14 0 C6 0 1 6 1 13 C1 22 14 34 14 34 C14 34 27 22 27 13 C27 6 22 0 14 0Z"
            fill="${{color}}" stroke="white" stroke-width="2"/>
      <circle cx="14" cy="13" r="5" fill="white" opacity="0.9"/>
    </svg>`,
    className: '', iconSize: [28, 36], iconAnchor: [14, 36], popupAnchor: [0, -38],
  }});
}}

// Launch marker (green flag)
function launchIcon(color) {{
  return L.divIcon({{
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
      <circle cx="14" cy="14" r="13" fill="#22c55e" stroke="white" stroke-width="2"/>
      <text x="14" y="19" text-anchor="middle" font-size="14" fill="white" font-family="sans-serif" font-weight="bold">P</text>
    </svg>`,
    className: '', iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -16],
  }});
}}

// Exit marker (red flag)
function exitIcon(color) {{
  return L.divIcon({{
    html: `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">
      <circle cx="14" cy="14" r="13" fill="#ef4444" stroke="white" stroke-width="2"/>
      <text x="14" y="19" text-anchor="middle" font-size="14" fill="white" font-family="sans-serif" font-weight="bold">X</text>
    </svg>`,
    className: '', iconSize: [28, 28], iconAnchor: [14, 14], popupAnchor: [0, -16],
  }});
}}

// Add gauge markers
G.forEach(g => {{
  const flow = g.latest_flow !== null ? g.latest_flow.toFixed(1) + ' CFS' : 'N/A';
  const gage = g.latest_gage !== null ? g.latest_gage.toFixed(2) + ' ft' : 'N/A';
  L.marker([g.lat, g.lon], {{ icon: gaugeIcon(g.condition.color) }})
    .addTo(map)
    .bindPopup(`<b>USGS ${{g.site_id}}</b><br><b>${{g.label}}</b><br>
      Flow: <b>${{flow}}</b> &nbsp; Gage: <b>${{gage}}</b><br>
      Status: <b style="color:${{g.condition.color}}">${{g.condition.label}}</b>`);
}});

// Add routes (launch, exit, route line, distance label)
const legendEl = document.getElementById('routeLegend');

// Derive a traffic-light color from a gauge condition label
function conditionTrafficColor(label) {{
  if (!label) return '#6b7280';
  if (label === 'Good' || label === 'Ideal') return '#22c55e';      // green
  if (label === 'Marginal' || label === 'Fast / Caution') return '#eab308'; // yellow
  return '#ef4444';  // red — Too Low or Dangerous
}}

// Build a lookup of site_id → gauge data
const gaugeBySite = {{}};
G.forEach(g => {{ gaugeBySite[g.site_id] = g; }});

DATA.routes.forEach(r => {{
  const gauge     = gaugeBySite[r.gauge_site_id] || {{}};
  const condLabel = gauge.condition ? gauge.condition.label : null;
  const lineColor = conditionTrafficColor(condLabel);
  const latlngs   = [[r.launch.lat, r.launch.lon], [r.exit.lat, r.exit.lon]];

  // Route line — colored red/yellow/green by paddleboard condition
  L.polyline(latlngs, {{ color: lineColor, weight: 5, opacity: 0.85, dashArray: '10 6' }}).addTo(map);

  // Distance label at midpoint
  const midLat = (r.launch.lat + r.exit.lat) / 2;
  const midLon = (r.launch.lon + r.exit.lon) / 2;
  L.marker([midLat, midLon], {{
    icon: L.divIcon({{
      html: `<div style="background:${{lineColor}};color:#0f172a;font-weight:800;font-size:11px;
                         padding:3px 8px;border-radius:999px;white-space:nowrap;
                         border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,.4);">
               ~${{r.river_est_miles}} mi &bull; ${{condLabel || '?'}}
             </div>`,
      className: '', iconAnchor: [40, 10],
    }})
  }}).addTo(map);

  // Launch marker
  L.marker([r.launch.lat, r.launch.lon], {{ icon: launchIcon(r.color) }})
    .addTo(map)
    .bindPopup(`<b style="color:#22c55e">&#9654; Launch</b><br>${{r.launch.name}}<br>
      <i style="color:#94a3b8">${{r.name}}</i>`);

  // Exit marker
  L.marker([r.exit.lat, r.exit.lon], {{ icon: exitIcon(r.color) }})
    .addTo(map)
    .bindPopup(`<b style="color:#ef4444">&#9632; Exit / Take-out</b><br>${{r.exit.name}}<br>
      <i style="color:#94a3b8">${{r.name}}</i>`);

  // Legend badge — dot color matches route line (traffic-light)
  legendEl.innerHTML += `
    <div class="route-badge" style="border-left:4px solid ${{lineColor}}">
      <div class="rb-dot" style="background:${{lineColor}}"></div>
      <div>
        <div class="rb-name">${{r.name}}
          <span style="background:${{lineColor}};color:#0f172a;font-size:0.68rem;font-weight:700;
                       padding:2px 8px;border-radius:999px;margin-left:6px;">${{condLabel || 'Unknown'}}</span>
        </div>
        <div class="rb-detail">
          <b style="color:#22c55e">P</b> ${{r.launch.name}}<br>
          <b style="color:#ef4444">X</b> ${{r.exit.name}}
        </div>
        <div class="rb-dist">~${{r.river_est_miles}} mi estimated river distance
          <span style="color:#94a3b8;font-weight:400"> (${{r.straight_miles}} mi straight-line &times; 1.45 sinuosity)</span>
        </div>
        <div class="rb-detail" style="margin-top:4px;">${{r.notes}}</div>
      </div>
    </div>`;
}});

// ── Chart defaults ────────────────────────────────────────────────────────────
Chart.defaults.color       = '#94a3b8';
Chart.defaults.borderColor = '#334155';
Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
Chart.defaults.font.size   = 11;

function condLabel(v) {{
  if (v < 50)   return 'Too Low';
  if (v < 100)  return 'Marginal';
  if (v < 300)  return 'Good';
  if (v < 600)  return 'Ideal';
  if (v < 1000) return 'Fast';
  return 'Dangerous';
}}

function makeHistChart(id, gauge) {{
  const labels = gauge.hist_flow.map(d => d.dt.slice(5));
  const vals   = gauge.hist_flow.map(d => d.value);
  new Chart(document.getElementById(id), {{
    type: 'line',
    data: {{
      labels,
      datasets: [
        {{ label: 'Daily Flow (CFS)', data: vals,
           borderColor: gauge.color, backgroundColor: gauge.color + '1a',
           borderWidth: 2, pointRadius: 2, fill: true, tension: 0.3 }},
        {{ label: `Ideal Min (${{IDEAL_MIN}} CFS)`,
           data: labels.map(() => IDEAL_MIN),
           borderColor: '#22c55e', borderWidth: 1.5, borderDash: [6,4], pointRadius: 0, fill: false }},
        {{ label: `Ideal Max (${{IDEAL_MAX}} CFS)`,
           data: labels.map(() => IDEAL_MAX),
           borderColor: '#3b82f6', borderWidth: 1.5, borderDash: [6,4], pointRadius: 0, fill: false }},
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ position: 'top' }},
        tooltip: {{ callbacks: {{ afterLabel(ctx) {{
          return ctx.datasetIndex === 0 ? 'Status: ' + condLabel(ctx.parsed.y) : '';
        }}}}}}
      }},
      scales: {{
        x: {{ ticks: {{ maxTicksLimit: 14 }} }},
        y: {{ title: {{ display: true, text: 'Flow (CFS)' }}, min: 0 }}
      }}
    }}
  }});
}}

function makeYoyChart(id, gauge) {{
  new Chart(document.getElementById(id), {{
    type: 'line',
    data: {{
      labels: gauge.yoy_labels,
      datasets: [
        {{ label: String(gauge.yoy_this_year), data: gauge.yoy_this,
           borderColor: gauge.color, backgroundColor: gauge.color + '14',
           borderWidth: 2.5, pointRadius: 1, fill: true, tension: 0.3, spanGaps: true }},
        {{ label: String(gauge.yoy_prior_year), data: gauge.yoy_prior,
           borderColor: '#818cf8', borderWidth: 2, borderDash: [5,3],
           pointRadius: 1, fill: false, tension: 0.3, spanGaps: true }},
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{ legend: {{ position: 'top' }} }},
      scales: {{
        x: {{ ticks: {{ maxTicksLimit: 24 }} }},
        y: {{ title: {{ display: true, text: 'Flow (CFS)' }}, min: 0 }}
      }}
    }}
  }});
}}

G.forEach((g, i) => {{
  makeHistChart('hist' + i, g);
  makeYoyChart('yoy' + i, g);
}});
</script>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Paddleboard River Conditions - Elm Fork & Hickory Creek")
    print("=" * 60)

    data = fetch_all()

    json_path = os.path.join(SCRIPT_DIR, "river_data.json")
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nData saved -> {json_path}")

    html_path = os.path.join(SCRIPT_DIR, "dashboard.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(build_html(data))
    print(f"Dashboard saved -> {html_path}")

    print("\nCondition summary:")
    for g in data["gauges"]:
        flow = f"{g['latest_flow']} CFS" if g["latest_flow"] is not None else "N/A"
        gage = f"{g['latest_gage']} ft"  if g["latest_gage"] is not None else "N/A"
        print(f"  {g['short']:20s}  Flow: {flow:12s}  Gage: {gage:10s}  Status: {g['condition']['label']}")

    print("\nRoute distances:")
    for r in data["routes"]:
        print(f"  {r['name']:40s}  ~{r['river_est_miles']} mi river ({r['straight_miles']} mi straight)")

    print("\nDone.")
