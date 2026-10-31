# CMO AI Agent — MVP progress

Status: functional single-workspace MVP, ready for a private pilot. Built from the original HTML prototype and ZIP; the original archive and a standalone HTML copy are preserved.

## Delivered

- Persistent SQLite records for Brand Brain, weekly plans, assets, campaigns, imported metrics, chat, and generation usage.
- Seven-day content planning linked to editable drafts across LinkedIn, email, Instagram, blog and landing-page copy.
- Rule-based brand checks, revision-aware editing, human approval, and CSV export of approved content. Changed copy or brand context requires renewed approval.
- Campaign briefs with budgets/deadlines, five transparent readiness checks and contextual recommendations.
- CSV metrics import with validation and repeatable upserts; actual CTR, CPL, ROAS, channel comparisons and period trends.
- Contextual chat and optional server-side DeepSeek generation. Existing `DEEPSEEK_API_KEY` variables are recognized automatically; `CMO_LLM_API_KEY` is an optional higher-priority override. Keys never appear in workspace API responses.
- Clearly labelled local templates/rules when no key is available. No invented marketing performance data.
- Responsive seven-page interface, setup guide, source-only packaging script and GitHub Actions service-test/package workflow.

## Verification

- **24 service tests passed locally**, covering persistence, planning, metric calculations/import validation, approvals, stale revisions, provider response validation, request limits, credential selection and key non-disclosure.
- **Browser workflow passed locally**: brand save/reload → seven-day plan → linked draft → edit/save → approval/export; invalidation after brand changes; email creation; campaign review; CSV analytics; saved chat; escaped user content; request guards; all seven mobile layouts; no console/runtime errors.
- Original MVP source archive passed clean-extraction tests; regenerated archives use the same source-only packaging script.
- Provider adapter tests use mocked responses. **Live DeepSeek calls have not been verified in the cloud workspace**: neither `DEEPSEEK_API_KEY` nor `CMO_LLM_API_KEY` was present in the running task environment during inspection. A key configured on another machine is not inherited here.
- GitHub Actions results are separate from local checks; inspect the Actions run after pushing this branch.

## Next milestones

1. Run from a system environment that exports `DEEPSEEK_API_KEY`, or bind that secret securely to the cloud runtime, then restart and verify one real generation.
2. Pilot one full week with a real brand and reviewed assets. Track time spent, edit effort and user feedback.
3. Import actual campaign results and reconcile totals with source reports before making budget decisions.
4. Add authenticated team access, approval identity/audit history, edit/undo tools and production deployment controls if the pilot supports a shared hosted product.

This is one trusted local workspace, not a public multi-user service. There is no automatic publishing, external analytics sync, or measured ROI claim. See [MVP architecture and boundaries](MVP.md).
