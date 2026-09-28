# Approved AI risk dashboard — UI 2.0.0

The 2026-09-27 approved mobile shell is fixed in `templates/`. CSS SHA-256 is pinned. The model produces only structured evidence; Python renders the page. Headline/reason/axis text has validated length limits. The display has Today / Trend / Evidence, five clickable axis rows, and a centered marker in one of four stages. No decimal risk score is displayed.

## Operation
- Existing schedule stays `10 23 * * *` UTC (08:10 KST). Queue delays are possible.
- Code pushes run tests and re-render existing data without API costs. Only `main` deploys.
- Scheduled runs and manual `refresh_data=true` research current sources using the existing API secret. The repository variable `OPENAI_MODEL` can override the pre-existing `gpt-5.6` default; no API key appears in source or browser output.
- Manual `refresh_data=false` is a layout-only redeploy.
- Initial deployment keeps the original report date and labels its grade as `원본 판정 참고`. A template update is not a new market assessment.
- A research/validation failure publishes a clearly labeled `UNKNOWN` report with no current marker. It is a data failure, not GREEN. Raw API errors and keys are not logged.
- `status.json` exposes data freshness and assessment state. A successful deployment does not imply successful market research; check `assessment_state`.

## Contract
`latest.json` keeps `date`, `risk_level`, `headline`, `summary`, `html_url`, `trend`, `monthly_summary`. `schema_version=2`, `ui_version=2.0.0`, `rules_version`, `assessment_state`, `change`, `axes`, sources, timestamps and build SHA are added. **`risk_score` is null and `watch` is empty.** Consumers must use the categorical level, treat UNKNOWN/data limitations separately, and not call numeric formatting on the removed score.

## History
All archived JSON stays. Layout-only redeploys leave dated archive bytes unchanged. Daily HTML older than 365 calendar days is removed on daily runs; this is public-tree retention, not a Git history purge. Same-day regeneration retains the old bytes in `revisions/`. Monthly summaries separate legacy and v1.0 classifications and do not average old scores. Missing days break streaks. Counts represent reports, not independent market observations.

## Verification
`python -m unittest discover -s tests -v` checks classification gates, source/date validation, escaping, failed-data handling, history separation, retention and layout-only archive preservation.
`python tests/check_browser.py` checks 320/360/390/768px, tabs, dialogs, keyboard navigation, source links, and 200% text sizing. Screenshots are Actions artifacts.
After Pages deployment, `tests/verify_pages.py` verifies public HTML **and** JSON UI/build versions. Never treat an old cached HTTP 200 response as success.

## Limits
v1.0 is a qualitative operating classification, not a calibrated default/return model. Observing a URL in search output does not by itself prove every claim in a source; interpretation and coverage still require review. No new market claims are asserted by the initial layout-only deployment. Historical archives are not retrospectively re-certified.
