# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the agent

```bash
python3 main.py
```

The process is long-running — it executes one poll cycle immediately on startup, then repeats on the interval set by `POLL_INTERVAL_SECONDS` (default 300s). Stop it with `Ctrl+C`.

## Dependencies

```bash
pip3 install -r requirements.txt
```

## Configuration

All configuration lives in `.env`. Copy `.env.example` to get started. The five required vars are `SF_USERNAME`, `SF_PASSWORD`, `SF_SECURITY_TOKEN`, `SF_ALERT_OWNER_ID`, and `ANTHROPIC_API_KEY`. Everything else has a default.

## Architecture

```
main.py → agent.py → salesforce_client.py
                   → enrichment_client.py  (FEC, SEC EDGAR, ProPublica)
                   → claude_client.py      (receives contact + enrichment signals)
```

- **`config.py`** — loaded once at startup; the `Config` dataclass is passed into every class constructor, so all field names and thresholds are resolved from `.env` in one place.
- **`agent.py` (`WealthScoringAgent.run_cycle`)** — the only place that orchestrates the full flow. Per-contact errors are caught and logged so one failure never aborts the cycle.
- **`salesforce_client.py` (`SalesforceClient`)** — all SOQL and DML. Uses `query_all` (not `query`) to auto-paginate, but the SOQL itself applies `LIMIT 200` so each cycle is bounded. `update_contact_score` writes both the score field and the processed flag in a single API call.
- **`enrichment_client.py` (`EnrichmentClient`)** — thin facade over three enrichment modules; calls each, passes `MailingState` through for FEC/ProPublica. All lookups are best-effort — failures are warned and never block scoring. Results are returned as `{"fec": {...}, "sec_edgar": {...}, "propublica": {...}}`.
  - **`enrichment/fec.py`** — Schedule A individual campaign contributions (≥$200). Keyset pagination, 30-day diskcache, tenacity retries, fuzzy name match at 85% + state check. Uses the API key from `config.fec_api_key` or the bundled default.
  - **`enrichment/sec_edgar.py`** — Quoted full-name search in Form 4 (insider transactions) and DEF 14A (proxy/exec compensation), with last-name-only fallback. Snippet verification via `is_match`. 7-day diskcache.
  - **`enrichment/propublica.py`** — Searches IRS 990 data for foundations/charities named after the contact (`{Last} Foundation`, `{Last} Family Foundation`, `{Last} Charitable`). Fetches org assets via a second API call per match. 30-day diskcache.
  - **`matching/fuzzy.py`** — `normalize_name` (handles FEC "LAST, FIRST" format, strips honorifics), `build_name_variants`, `fuzzy_match`/`is_match` via `rapidfuzz.token_sort_ratio`, `names_share_state`.
- **`claude_client.py` (`ClaudeClient`)** — builds a prompt from contact fields + formatted enrichment signals, calls `claude-sonnet-4-6`, and parses a strict JSON response `{"score": int, "reasoning": str}`. The prompt instructs Claude to treat name-based public records as supporting evidence (not proof) due to name collision risk.

## Idempotency

Two guards prevent double-processing:

1. `Wealth_Scan_Processed__c = true` is set atomically with the score write, so the SOQL query won't return the contact again.
2. Before creating an alert Task, `task_exists_for_contact` queries for an existing `Task` with `Subject = 'High-Value Donor Alert'` on the same `WhoId` — this handles the edge case where the agent crashed after writing the score but before creating the Task.

To re-score a contact, set `Wealth_Scan_Processed__c` back to `false` in Salesforce.

## Salesforce custom fields required

Both fields must exist on the Contact object before running:

| Field label | API name | Type |
|---|---|---|
| Wealth Score | `Wealth_Score__c` | Number (3, 0 decimals) |
| Wealth Scan Processed | `Wealth_Scan_Processed__c` | Checkbox (default unchecked) |
