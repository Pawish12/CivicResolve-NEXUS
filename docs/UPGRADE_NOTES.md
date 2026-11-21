# CivicResolve NEXUS Upgrade — Evidence for Review

## Changed while preserving the initial attempt

- Civic Memory Intelligence: links new cases to recent citizen-verified issues in the same ward, service category, and landmark after conservative description matching, without merging into closed cases.
- Explainable recurrence boost: up to +10 additional review points (capped at 100), with reason displayed for case officers.
- A separate Civic Memory panel in Signal Radar, audit events, API `/api/memory`, and CivicGuide contextual replies.
- Accessibility: skip-to-content, keyboard Tab focus trapping for active dialog and restoring focus on close.
- Testing: regression assertions covering recurrence and different-ward/location non-matches, CSRF controls, and public APIs.
- Dependencies: explicitly declares `itsdangerous` for Starlette sessions on Render.

## Limitations and honesty

These are prototype heuristics; similarity can make incorrect links. `Civic Memory` is not a causal diagnostic or predictive model. All case data is synthetic/demo. Citizen alias verification is **not authenticated identity** and demo staff accounts are not production-ready.

## Safe second-attempt strategy

Do not submit another scored attempt just to trigger a reevaluation. First inspect `git diff`, run `python -m pytest -q`, test browser workflows locally, then deploy and verify the live site. The event only accepts two attempts and evaluates the most recent submitted attempt.
