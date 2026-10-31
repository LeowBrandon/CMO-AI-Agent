# CMO AI — a marketing workspace for small teams

A working, low-cost MVP built from the original CMO AI prototype. Keep brand context, plan a week, draft and approve content, review campaigns, and turn imported marketing results into next steps.

**Stack:** Python 3.10+ standard library, SQLite, HTML/CSS/JavaScript. No npm dependencies, database service, build, or paid software is needed to run locally. DeepSeek is the default optional live AI provider. With no key, clearly labelled local templates and rules make the workflow usable without API costs.

## Run

```bash
python3 server.py
```

Open `http://127.0.0.1:8000` in a browser on the same machine. Use `--port 8001` if needed. This is a backend application: opening `index.html` directly or running `python -m http.server` will not work.

Data is created automatically in `.data/cmo.sqlite3` (ignored by Git). Restarting the server or browser preserves saved records. Start a separate workspace with `python3 server.py --db /path/to/workspace.sqlite3`. There is no automatic fake performance data or seeded campaign history. The initial Brand Brain uses the editable NovaFlow example from the prototype.

The original ZIP is unchanged; its standalone HTML is also preserved at `docs/original-prototype.html`.

## Connect your DeepSeek key

Configure these variables through your hosting environment's **secure environment/secret settings**, then restart the server:

| Variable                     | Default / purpose                                        |
| ---------------------------- | -------------------------------------------------------- |
| `DEEPSEEK_API_KEY`           | Your existing DeepSeek API key; recognized automatically |
| `CMO_LLM_API_KEY`            | Optional generic API key override; takes precedence      |
| `CMO_LLM_PROVIDER`           | `deepseek` (`openai` also supported)                     |
| `CMO_LLM_MODEL`              | `deepseek-chat` for DeepSeek; `gpt-4.1-mini` for OpenAI  |
| `CMO_DAILY_GENERATION_LIMIT` | `30` generation attempts per server calendar day         |
| `CMO_DB_PATH`                | Optional SQLite path override                            |

The server reads environment variables; it **does not load `.env` files automatically**. Never paste a real key into frontend code, Git, chat, or screenshots. The key is not exposed to the browser. DeepSeek requests go to `https://api.deepseek.com/chat/completions`. Allow HTTPS access to `api.deepseek.com`. For OpenAI, use a matching key, provider/model settings, and allow `api.openai.com`.

If `DEEPSEEK_API_KEY` is already exported in your system environment, start the app from that environment; no renaming is required. `CMO_LLM_API_KEY` remains an optional override. A new terminal/process may be needed after changing system variables. A variable on your personal computer is not automatically inherited by this cloud workspace. In the managed cloud environment, bind your existing secret securely to `DEEPSEEK_API_KEY` (or the previously declared `CMO_LLM_API_KEY` override) in environment settings. The DeepSeek domain is already in the draft. Saving a draft does not inject a key into an already running process; apply configuration and restart the app.

Live generation sends saved brand context, the two latest plans, up to five campaigns, eight recent chat turns, and aggregate performance to the selected provider. Do not add sensitive customer information without permission. Requests have a 45-second timeout, a 2,200-output-token limit, and validated JSON responses. Failures are surfaced without saving fabricated results or silently falling back to templates. Daily attempts include failed requests to prevent uncontrolled retries. The cap is **not a currency budget**; configure provider billing limits separately.

The workspace settings panel shows the current mode and token counts. A configured key is not proof of provider access: confirm it with a successful generation. Local mode is deterministic templating, not a language model. It uses saved brand facts but does not understand arbitrary rewrite instructions or fully enforce a free-text voice description.

## Project progress

See [the progress report](docs/PROGRESS.md) for delivered features, verification, and the remaining pilot/deployment work. The GitHub Actions workflow runs service tests on Python 3.10 and 3.12 and packages a source-only ZIP.

## The MVP workflow

1. **Brand Brain:** save product, audience, positioning, voice, CTA, restricted phrases, and monthly budget. All generation uses this context.
2. **Content Planner:** generate a dated seven-day plan for a business goal. Keep multiple plans and draft any idea into an asset; drafting the same plan item reopens its existing asset.
3. **Content Studio:** generate social posts, emails, blog drafts, and landing-page copy. Edit and save content, request a variation, and review basic brand checks. Approve only after the saved content includes the brand and CTA, avoids restricted phrases, and has enough context. These are simple rules, not a guarantee of marketing or legal quality.
4. **Campaigns:** save audience, offer, goal, channel, budget and deadline; run a review for recommendations. Readiness is five disclosed rules worth 20 points each, not an AI confidence score or predicted ROI. Reviews are snapshots; run them again after changing brand context.
5. **Analytics:** import your metrics CSV and get actual totals, channel CTR/CPL/ROAS, period comparisons, and grounded observations. Empty/zero denominators show “—”, not invented ratios. “Analyze” adds local rules or live AI recommendations.
6. **Ask your CMO:** saved contextual conversations use the Brand Brain, plans, campaigns, aggregate metrics, and recent conversation history. Chat recommends actions; it does not independently change records or publish content.
7. **Export:** download approved assets as CSV for manual publishing, all metric records as CSV, or a workspace JSON for inspection.

**Human approval:** saving changed asset content or title resets its approval to Draft. A Brand Brain change invalidates earlier approvals. CSV asset exports include only currently approved assets matching the current brand. Stale revisions cannot overwrite or approve a newer asset. Nothing is auto-posted, emailed, or scheduled to external services.

## Import performance

Download an example from Analytics → Import metrics. Required headers, in this order:

```csv
date,channel,campaign,spend,impressions,clicks,leads,revenue
2026-10-01,LinkedIn,Product launch,50,2000,100,10,250
```

Use your own actual dates and results. Dates must not be in the future; supported channels are `LinkedIn`, `Email`, `Instagram`, `Blog`, `Landing page`. Monetary amounts are USD. Counts are nonnegative integers with leads ≤ clicks ≤ impressions. Up to 1,000 rows / 200 KB per import; the complete file is validated before saving. Duplicate keys within a file are rejected. Re-importing a matching **date + channel + campaign** updates that row, making repeated imports safe.

Analytics uses the server's current date: the last 30 calendar days inclusive, compared with the preceding 30 days. The chart groups those dates into six five-day buckets. Imported older data stays saved but is excluded from current totals. Ingest daily increments, not overlapping cumulative totals. Email impressions should represent delivered emails; provide click-attributed leads for this simplified funnel. Duplicate/overlapping aggregate sources can overcount; clean data before importing. Observed channel efficiency does not establish causation or customer quality.

## Validation

Service tests need only Python:

```bash
python3 -m unittest discover -s tests -v
```

The optional browser regression uses development-only tools (preinstalled in this cloud environment): Python Playwright and Chromium.

```bash
# On another development machine, if these tools are absent:
python3 -m pip install -r requirements-dev.txt
# Install Chromium through your OS package manager, or set CHROMIUM_PATH.
python3 tests/browser_smoke.py
```

The browser test starts an isolated temporary server/database and verifies the full brand → plan → draft → approval → export workflow, invalidation after brand changes, campaign reviews, CSV analytics, persisted chat, cross-site request guards, safe rendering, and all seven mobile pages. It writes screenshots to ignored `artifacts/`. It makes no real provider requests. DeepSeek adapter tests use mocked responses; they verify wiring, not live API access.

## Scope and deployment

This MVP is a **single trusted local workspace**, bound to `127.0.0.1`. It has no user accounts, tenant isolation, public hosting configuration, or autonomous publishing integrations. Do not expose it as a public multi-user service. Host/Origin guards, JSON-only mutations, fixed static routes, CSP, parameterized SQL, CSV formula escaping and revision checks reduce common local risks; they do not replace authentication or an independent security review.

For a private single-operator installation, run Python on a small persistent machine and use a trusted private access mechanism. Public/team deployment requires authentication, authorization, HTTPS, protected database storage/backups, retention policies, production process supervision, rate limits per user, and a suitable deployment review. See [MVP notes](docs/MVP.md) for the architecture and next steps.

Back up the workspace by stopping the server and copying the SQLite database. To restore, start the server with `--db` pointing to that copy. Do not copy only the main database while a live WAL writer is running. JSON exports are for inspection/portability; this version has no JSON restore endpoint. `.data/`, `.env`, generated screenshots, and API secrets must not be committed.
