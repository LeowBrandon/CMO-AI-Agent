# MVP implementation notes

## What changed from the prototype

The original HTML/ZIP had in-memory arrays, simulated save/export toasts, fixed metrics, and scripted chat answers. The MVP keeps its seven workflows while adding persisted business records, actual CSV downloads/imports, rule-based review and analytics, and a server-side DeepSeek adapter.

A live AI key is optional, so small teams can validate the workflow without paying for calls. Local outputs are explicitly marked as templates/rules; they must not be presented as live AI. Free-text brand voice and detailed rewrite instructions are prompt inputs for the live model; local mode offers basic brand-informed layouts.

## Architecture

```text
Browser: index.html + web/app.js + web/style.css
    │ same-origin JSON / downloads
Python ThreadingHTTPServer (server.py)
    ├── Service: validation, approval, review, metrics, exports
    ├── Agent: context + daily attempt cap + JSON schema validation
    │       ├── Local templates/rules
    │       └── DeepSeek HTTPS API (or optional OpenAI)
    └── SQLite Store: brand, plans, assets, campaigns, metric rows, messages, usage
```

No frontend key storage. No external assets/CDN/fonts at runtime. Standard library only for application deployment. SQLite uses WAL and short transactions; asset writes use revision comparison. Unique indexes prevent duplicate metric identity and multiple assets per saved plan item. The app is for a single local operator, not a concurrent team service.

## Main API routes

| Route                            | Behavior                                                             |
| -------------------------------- | -------------------------------------------------------------------- |
| GET `/api/health`                | Liveness and configured generation mode; no provider call            |
| GET `/api/state`                 | Saved workspace and computed analytics                               |
| POST `/api/brand`                | Validate and persist brand context                                   |
| POST `/api/plans`                | Generate and persist a seven-item plan                               |
| POST `/api/assets`               | Generate an independent or plan-linked draft                         |
| POST `/api/assets/:id/save`      | Edit with expected revision, reset approval if changed               |
| POST `/api/assets/:id/approve`   | Check rules and current revision, bind approval to brand fingerprint |
| POST `/api/assets/:id/variation` | Rewrite using instructions/live AI or alternate local layout         |
| POST `/api/campaigns`            | Save campaign brief and budget                                       |
| POST `/api/campaigns/:id/review` | Persist recommendations and transparent readiness checks             |
| POST `/api/metrics/import`       | Validate full CSV then transactionally upsert metrics                |
| POST `/api/insights`             | Analyze aggregate performance; response is not a saved report        |
| POST `/api/chat`                 | Generate and persist question/answer                                 |
| GET `/api/export/assets`         | Download currently approved assets only                              |
| GET `/api/export/metrics`        | Download all imported metric rows                                    |
| GET `/api/export/workspace`      | Download JSON for inspection (no restore endpoint)                   |

## Budget choices

- One SQLite database and Python process; no hosted vector store, queue, or orchestration subscription.
- One provider request per generation/review/chat; bounded output, no autonomous retry loops.
- Context limited to saved brand, two latest plans, five campaigns, aggregate metrics, and eight recent conversation turns.
- Daily global attempt cap, including failures; server date resets the counter.
- Token totals are provider-reported usage, not a billing estimate. Malformed/network-failed responses may still incur charges not represented by successful token totals. Use provider billing limits.
- Export/manual publishing and CSV imports avoid paid third-party automation dependencies in the MVP.

## Boundaries

- Single workspace; no login, multi-user roles, approval identity, audit trail, or public deployment.
- Approval is a workflow state, not legal/compliance certification. Basic rules cannot prove voice match or factual accuracy.
- A brand update invalidates content approvals, but campaign reviews are stored snapshots and need rerunning.
- A variation replaces the current draft; no version history/undo yet. Export important drafts before rewriting.
- Campaigns and plans can be created and reviewed, but there is no campaign editing/deletion UI, bulk asset deletion, scheduling, or provider integrations.
- CSV imports upsert aggregate records; use a stopped SQLite backup to recover from an unwanted import. No deletion/JSON restore UI.
- A database path selects a workspace; there is no UI for switching clients/brands.
- Charts/rates reflect supplied data and simple observations, not attribution or predictive models.
- Provider availability, key authorization, output quality, production hosting, and real-world business impact require live validation.

## Suggested next 30 days

| When       | Owner              | Action                                                               | Success measure                                             |
| ---------- | ------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------- |
| Days 1–3   | Founder            | Configure brand and DeepSeek, test 10 representative prompts         | Brand context used, no unsupported claims accepted          |
| Days 4–10  | Marketing owner    | Run one full weekly planning and approval cycle                      | Seven dated ideas, at least three reviewed assets exported  |
| Days 11–17 | Marketing owner    | Import actual daily channel results                                  | Reconciled spend/leads, correct CTR/CPL, no double counting |
| Days 18–24 | Founder + marketer | Compare time spent vs prior manual workflow; interview 3–5 users     | Measured drafting time, edit effort, usefulness feedback    |
| Days 25–30 | Developer          | Choose fixes from evidence; scope team authentication and deployment | Prioritized backlog and a reviewed private deployment plan  |

Expected impact is a hypothesis to test: less coordination and drafting effort, consistent context, and clearer decisions. Do not claim specific ROI/time savings until measured with real teams.
