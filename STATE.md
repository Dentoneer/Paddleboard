_Last updated: 2026-08-10_

## Status
- **GitHub Actions refresh: working and active.** Runs every 6 hours (cron `0 */6 * * *`),
  last 5 runs all succeeded (most recent 2026-08-10T19:01Z). It commits fresh
  `river_data.json` + `dashboard.html` straight to `main`.
- **Local Windows Task Scheduler job: not set up.** `setup_daily_task.bat` exists but the
  `PaddleboardRiverConditions` task is not currently registered on this machine (`schtasks
  /query` finds nothing) — it was never run, or was removed. The only thing keeping data fresh
  right now is the GitHub Action.
- **This local clone is stale/behind.** At last check, local `main` was 33 commits behind
  `origin/main` (all auto "Refresh river conditions" commits). The `river_data.json` /
  `dashboard.html` files on disk here reflect a 2026-05-17 fetch, not current conditions.
  Run `git pull` before trusting the local dashboard file, or just re-run the script.
- Core fetch/classify/render logic in `fetch_river_data.py` appears complete and working (no
  stubs found; USGS calls have per-gauge error handling).

## Recent decisions
- Lake Ray Hubbard was given its own simpler condition model (`paddle_type: "lake"`) instead of
  the river CFS thresholds, since outflow doesn't map to paddleability on flat water the way
  river CFS does — worth knowing if adding more lake gauges later.

## Open threads / next steps
- Decide whether the local Task Scheduler job is still wanted given the GitHub Action already
  covers refresh — running both could cause redundant/conflicting local commits if ever git-tracked
  together carelessly. Marco generally pushes to eliminate redundant manual/local steps once an
  automated path already covers the same job (see memory: automation-first preference) — leaning
  toward retiring `setup_daily_task.bat` rather than actually registering it, but confirm with him
  before deleting it.
- Consider pulling latest `main` locally (or just treating GitHub as source of truth) so the
  local dashboard.html isn't misleadingly stale if opened directly from this clone.
