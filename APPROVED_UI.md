# Approved risk dashboard deployment

UI version: 2.0.0. The September 27 approved CSS, mobile shell, and accessible tab/dialog interactions are reused.

- Source of truth for UI: templates/approved-layout.*. CSS SHA-256 is checked at render time.
- Daily research: generate_report.py reads prompt-v2.txt, checks that web search completed, validates source IDs/observation dates, and applies disclosed qualitative rules v1.0.
- Code push: render-only, no OpenAI request. Saved market content is explicitly marked not revalidated. Archived source JSON/HTML bytes are not changed.
- Schedule: existing 23:10 UTC (08:10 KST) is retained. Scheduled jobs may be delayed by GitHub.
- Public contract: latest.html and latest.json URLs are unchanged. ui-version.json records deployment version/commit. risk_score remains a key but is null; numeric scores are retired. Consumers must handle null and assessment_state.
- Long-term JSON records stay in archive. Only dated HTML older than 365 days with preserved JSON is eligible for removal during new research runs. Same-day overwritten JSON is also retained in revisions.
- Monthly/trend computations separate rules versions and report counts. Legacy decimal scores are not averaged with new categories.
- A research failure publishes UNKNOWN / data limited rather than pretending that the previous grade is current. Publication success is distinct from research success.

Before production: unit tests, saved-data rendering with archive integrity check, and 360/390px browser checks. The deployment job verifies the publicly served UI version and commit after Pages completes.

This UI rollout does not validate financial figures from historical reports. Historical market assertions need their own source verification.
