# Paddleboard Conditions Dashboard

## Purpose
A self-contained HTML dashboard showing current paddleboarding conditions at four DFW-area
USGS river/lake gauges (Greenbelt below Ray Roberts, Elm Fork at Lewisville, White Rock Creek,
Lake Ray Hubbard), with a map of suggested launch/exit routes, 13-week flow history, and
year-over-year comparison charts. Exists so Marco can check at a glance whether any nearby
spot is paddleable without manually checking USGS gauges.

## Architecture
- **`fetch_river_data.py`** — the only real logic in this repo. On each run it:
  1. Fetches instantaneous + daily USGS water data (flow CFS + gage height) for each gauge in
     `GAUGES` via `waterservices.usgs.gov` (no API key required).
  2. Classifies conditions (`classify_condition`) — river gauges use CFS thresholds (Too Low /
     Marginal / Good / Ideal / Fast-Caution / Dangerous); the lake gauge (Ray Hubbard) uses a
     simpler flat-water/high-water check since wind, not flow, is the real risk there.
  3. Computes suggested paddle routes (`ROUTES`) with haversine straight-line distance × a
     1.45 sinuosity factor to estimate actual river miles.
  4. Writes two output files: **`river_data.json`** (raw data snapshot) and
     **`dashboard.html`** (a fully self-contained HTML page — data is inlined as a JSON blob
     in a `<script>` tag, styled inline, using Leaflet for the map and Chart.js for the
     history/YoY charts, both loaded from CDN).
- **`dashboard.html`** is generated output, not hand-edited. Regenerating requires re-running
  the Python script — the page does not fetch live data itself.
- **`open_widget.bat`** — double-click convenience: runs the fetch script, then opens
  `dashboard.html` in the default browser.
- **`setup_daily_task.bat`** — one-time setup script (run as Administrator) that registers a
  Windows Task Scheduler job (`PaddleboardRiverConditions`) to run `fetch_river_data.py` daily
  at 7:00 AM.
- **`.github/workflows/refresh-river-data.yml`** — a GitHub Actions workflow that independently
  runs the same script every 6 hours in the cloud and commits+pushes `river_data.json` and
  `dashboard.html` back to `main` if they changed.

## Conventions
- Run manually: `python fetch_river_data.py` from the repo root (writes both output files in
  place). Or double-click `open_widget.bat` to fetch and view in one step.
- No secrets/config: USGS water services API is public, unauthenticated. GitHub Actions
  workflow only needs the default `GITHUB_TOKEN` (already scoped via `permissions: contents: write`).
- Two independent refresh mechanisms exist — see STATE.md for which one is actually active.

## Key facts
- External API: USGS NWIS water services (`waterservices.usgs.gov`), parameters `00060` (flow,
  CFS) and `00065` (gage height, ft). No key needed; failures are caught and logged as warnings
  per-gauge rather than crashing the whole run.
- `dashboard.html` embeds a full JSON snapshot at generation time — opening the file directly
  shows whatever data was current at the last `fetch_river_data.py` run, not live data.
- The GitHub Actions workflow commits directly to `main` on its own schedule. A local clone can
  drift far behind `origin/main` (auto-commits named "Refresh river conditions") without any
  local change — always `git pull` before assuming `river_data.json`/`dashboard.html` here are current.
