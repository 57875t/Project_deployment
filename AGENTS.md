# QR Desk v1.0 — Codex Execution Guardrails

## Mission

Upgrade QR Desk from v0.8 to a release-candidate v1.0 that can be handed to quantitative-data and frontend testers as a complete, reproducible, truth-first system.

The product is a read-only market-data workstation. It is not an order-routing or brokerage system.

## Mandatory workflow

Every implementation batch must follow:

1. Preview — scope, inputs, outputs, assumptions, and blocked dependencies.
2. Execute — isolated implementation with narrowly scoped commits.
3. Nitpick — actively search for correctness, security, race, time-zone, stale-data, and provenance failures.
4. Review — inspect code paths, contracts, tests, logs, and error handling.
5. Acceptance — run deterministic, contract, browser, and provider-backed tests.
6. Closure — update audit, changelog, release status, and remaining blockers.

Do not skip a stage and do not mark a stage PASS based only on the page looking correct.

## Hard truth boundaries

- Real fields may contain only licensed-provider observations that passed validation.
- A real response MUST explicitly contain `provenance.syntheticBars === 0`; missing is a hard failure.
- A real response MUST contain a recognized `quality.verdict`; missing or unknown is a hard failure.
- Provider failure must fail closed. Never replace real bars with generated bars.
- Simulated/calibrated data must remain physically and semantically isolated and visibly labeled.
- Last-completed-bar close must never be presented as an independent live quote.
- Delayed, EOD, historical, snapshot, and real-time data must be labeled separately.
- API keys must never be returned to the browser, included in exception text, logs, URLs shown to users, repository files, or frontend storage.
- No trading, account, balance, position, or order endpoints.

## Release-blocking P0 items

Before any public or staff-facing deployment:

1. Sanitize provider failures. Current raw `httpx` exception strings can include request URLs containing `apiKey` or `api_token`; never return or log these strings.
2. Add stable internal error codes and redacted provider-attempt records.
3. Require explicit `syntheticBars: 0` and valid `quality.verdict` in frontend and backend contracts.
4. Add authentication or signed access plus rate limiting, request coalescing, quotas, and abuse protection to the gateway.
5. Replace production CORS `*` with an explicit origin allowlist.
6. Remove browser-direct model API keys from the production build; route model requests through a server-side proxy.
7. Put the complete frontend source in the repository and run browser/contract tests in CI.

## Engineering requirements

- Split the monolithic HTML into maintainable modules while preserving a standalone release artifact as a build output.
- Define typed request/response schemas and publish `schemaVersion` and `buildVersion`.
- Pin dependencies with a lockfile or hashes; do not rely on floating ranges for release builds.
- Use provider adapters with normalized error types, response validation, retries with bounded backoff, circuit breakers, caching, and concurrency limits.
- Treat provider entitlement and recency as verified metadata, not environment-label assertions.
- Add a canonical instrument master for market, exchange, asset type, currency, timezone, tick size, lot size, provider symbols, and calendar.
- Keep quote semantics separate from K-line semantics.
- Calculate session open/high/low/volume from the whole session or an independent quote snapshot; never use the last candle's OHLCV as day metrics.
- Verify bar-start/bar-end conventions per provider, market, and interval using captured fixtures.
- Reject or explicitly classify bars crossing exchange breaks. Do not accept truncated bars as complete.
- Count missing intraday slots across trading sessions, not only within the same date.
- Add corporate-action, suspension, halt, zero-volume, early-close, DST, lunch-break, auction, and holiday handling.
- Bind WebSocket streams to the configured gateway origin or an explicit allowlist; validate every message against a strict schema and session rules before mutating state.
- Add exponential reconnect backoff, heartbeat timeout, message-rate limits, and stale-stream downgrade.
- Local snapshots are untrusted caches, not proof of authenticity. Add schema versioning, expiration, integrity metadata, and clear stale labeling.

## Required test gates

- Unit tests for normalization, sessions, aggregation, quote semantics, errors, and redaction.
- Property/fuzz tests for malformed OHLCV, timestamps, duplicates, ordering, and extreme values.
- Provider fixture tests for US/HK/SH/SZ and each supported interval.
- Contract tests between backend schemas and frontend consumers.
- Browser tests covering race cancellation, offline mode, corrupted storage, missing fields, stream reconnect, mobile layout, keyboard navigation, and accessibility.
- Security tests proving provider keys and model keys never appear in API responses, logs, HTML, browser storage, or test artifacts.
- Performance budgets for initial load, chart rendering, large datasets, and memory growth.
- CI must run lint, formatting, typing, unit, contract, browser, security, and build-artifact checks.

## Definition of done

v1.0 can be marked RELEASE CANDIDATE only when:

- all P0/P1 defects are closed;
- CI is green from a clean checkout;
- the release artifact is reproducible and checksummed;
- US, HK, SH, and SZ reference fixtures pass;
- a provider-backed acceptance report records entitlement, latency, timestamp convention, adjustment mode, and reference-terminal tolerance;
- failure tests prove there is no synthetic substitution or secret leakage;
- rollback instructions and known limitations are documented.

LIVE PASS remains blocked until licensed credentials and reference-terminal comparisons are completed.