# QR Desk v1.0 — Master Bug Audit

Status: **RELEASE BLOCKED**

Baseline reviewed:

- `agent/qrdesk-v0.8-kline-core`
- `qrdesk_gateway/app.py`
- `qrdesk_gateway/config.py`
- `qrdesk_gateway/provider.py`
- `qrdesk_gateway/kline_engine.py`
- `qrdesk_gateway/session_engine.py`
- local v0.8 Phase 3 standalone HTML artifact

This document is intentionally adversarial. It is the Nitpick input for the v1.0 Codex upgrade.

## P0 — must close before any staff-facing or public deployment

### P0-01 Provider secrets can leak through raw exception text

The gateway calls providers with `apiKey` / `api_token` in query parameters. `response.raise_for_status()` can produce an exception containing the full request URL. Provider failures are appended with `str(exc)` and the FastAPI endpoint returns `str(exc)` to the browser.

Required fix:

- introduce typed provider errors with stable internal codes;
- redact URLs, query strings, headers, tokens, and response bodies;
- never serialize raw exception text to clients;
- add automated tests using sentinel secrets and assert they never occur in responses, logs, attempts, tracebacks, or artifacts.

### P0-02 Real-data gate does not require explicit `syntheticBars: 0`

The frontend rejects non-zero finite values, but a missing/invalid value becomes a warning. This violates the truth contract.

Required fix: missing, null, NaN, string, negative, or non-zero `syntheticBars` must hard-fail every real REST and stream path.

### P0-03 Missing `quality.verdict` is only a warning

A gateway payload can omit the quality verdict and still reach display logic.

Required fix: real data requires an explicit enum such as `PASS | WARN | FAIL`; missing or unknown is blocking. Define which WARN codes are displayable and which are not.

### P0-04 Gateway is public and quota-abusable

No authentication, signed session, effective rate limiting, request coalescing, provider quota budget, or abuse protection is active. The settings fields for cache TTL and requests per minute are not enforced.

Required fix: add access control, per-client and global limits, caching, coalescing, concurrency bounds, quota telemetry, and provider circuit breakers.

### P0-05 Production CORS defaults to wildcard

`QRDESK_ALLOWED_ORIGINS` defaults to `*`.

Required fix: refuse production startup with wildcard or empty origins. Keep a separate explicit development mode.

### P0-06 Browser-direct model API key is a production blocker

The standalone frontend stores the GLM key in page memory/sessionStorage and calls the model provider directly. Any XSS, extension, compromised dependency, copied page, or debugging session can expose it.

Required fix: production model calls must use a server-side proxy with scoped credentials, request limits, redaction, audit IDs, and prompt-size limits. Browser-direct mode may exist only in an explicitly marked local developer build.

### P0-07 Complete frontend source is not reproducibly versioned in the repository

The tested v0.8 HTML artifact is local while the branch contains only the contract/audit. Codex, CI, and testers cannot reproduce the exact tested frontend from a clean checkout.

Required fix: commit source modules, build configuration, tests, and a deterministic standalone artifact build. Store artifact SHA-256 in the release manifest.

### P0-08 Stream data can mutate trusted state without a complete truth envelope

WebSocket quote/bar messages do not require schema version, provider, entitlement, request correlation, explicit `syntheticBars: 0`, quality verdict, sequence number, or signed stream identity. Quote price accepts any finite value, including negative values. Closed bars are inserted before full acceptance is established.

Required fix:

- strict stream envelope schema;
- positive/tick-size/market/session validation;
- sequence and replay protection;
- origin binding or explicit allowlist;
- validate before state mutation;
- quarantine invalid messages;
- stale heartbeat downgrade and bounded reconnect.

## P1 — correctness and architecture defects

### P1-01 Day open/high/low/volume are actually the last candle metrics

The backend currently maps `quote.open/high/low/volume` from the last completed bar. The frontend labels these fields like session/day metrics.

Required fix: derive session metrics from all current-session bars or use an independent quote snapshot. Rename candle fields if session data is unavailable.

### P1-02 Health checks key presence, not provider health

A configured but invalid/expired key returns health `ok`.

Required fix: distinguish process health, configuration health, provider authentication health, entitlement health, and data freshness. Do not spend provider quota on every liveness check.

### P1-03 Entitlement and recency are environment assertions

`configured`, `plan-dependent`, and delayed labels are not proof of actual entitlement.

Required fix: adapter-specific entitlement verification where available; otherwise mark `unverified` and block LIVE PASS.

### P1-04 Raw provider attempts expose internals and are unstable

Attempts contain raw strings and provider implementation details.

Required fix: stable public attempt schema with redacted code, retryability, provider alias, status class, and correlation ID. Detailed traces stay server-side.

### P1-05 Configuration is partially ignored

Configured provider base URLs, cache TTL, and request limits are not consistently used by provider/application code.

Required fix: inject one validated settings object into adapters and fail startup for invalid production configuration.

### P1-06 Version drift

FastAPI reports `0.7.1` while the branch and frontend are v0.8 and the target is v1.0.

Required fix: one build/version source, exposed in health, response envelopes, frontend, artifacts, and CI.

### P1-07 No typed API contract

Responses are untyped dictionaries without Pydantic response models or schema versioning.

Required fix: strict request and response models, enum fields, OpenAPI examples, compatibility tests, and frontend-generated or shared types.

### P1-08 Negative volume is silently converted to zero

Normalization uses `max(0, volume)`, changing provider observations instead of rejecting them.

Required fix: reject and count invalid negative volume. Define explicit policy for missing volume and legitimate zero-volume bars.

### P1-09 Zero/negative price policy is incomplete

Only `low < 0` is rejected; zero prices can pass.

Required fix: validate positive prices, tick size, decimal precision, and instrument-specific exceptional cases.

### P1-10 Timestamp convention is assumed throughout

Freshness, incomplete-bar filtering, and session validation assume bar-start timestamps. Provider metadata is still `provider-start-assumed`.

Required fix: fixture-verified convention per provider/market/interval and transformation to one canonical convention.

### P1-11 Bars crossing exchange breaks may be accepted as complete

For intraday bars, `nominal_end > segment_end` increments a counter but may still keep the bar. A one-hour HK/CN bar crossing lunch can therefore be accepted.

Required fix: reject, classify as provider-native truncated, or rebuild only from lower-interval source bars. Never label it a full target interval without evidence.

### P1-12 Intraday gap counting ignores missing whole sessions

When consecutive bars are on different dates, gap counting skips the interval. A missing trading day can be invisible.

Required fix: generate expected slots across exchange sessions and count absent slots while excluding valid closures/breaks.

### P1-13 Previous close is derived from available bars, not the official session close

A short range may have no previous session. Corporate actions and provider adjustment choices can make this wrong.

Required fix: use an explicit official previous-close field or a verified previous session daily close with the same adjustment mode.

### P1-14 Asset type is wrong for ETFs

The backend always returns `EQUITY`, including SPY/QQQ.

Required fix: canonical instrument metadata and contract tests.

### P1-15 EODHD range parameters are not enforced

Requests do not consistently pass `from`/`to`; returned windows may not match requested range and can be oversized or undersized.

Required fix: adapter-specific range construction, pagination, result caps, and exact-window tests.

### P1-16 Provider retries/backoff/circuit breaking are absent

Transient failures immediately fall through and repeated clients can amplify provider incidents.

Required fix: bounded retry only for retryable classes, jittered backoff, circuit breaker, and Retry-After support.

### P1-17 No request cache or coalescing

Identical clients can duplicate expensive provider calls.

Required fix: canonical cache key includes provider, instrument, range, interval, adjustment, entitlement class, and completed-session boundary. Never cache auth failures as market closures.

### P1-18 Provider response validation is incomplete

No strict schema, maximum payload, content-type, symbol echo, timezone, exchange, or provider status validation before normalization.

Required fix: strict adapter models and fixture tests for malformed/partial responses.

### P1-19 Direct browser Yahoo/Eastmoney paths are unstable production dependencies

CORS, schema drift, rate limits, licensing, and availability can change independently. They can be displayed even though they do not pass the authorized-real gate.

Required fix: move reference sources behind server-side adapters or isolate them in a developer/reference build. Never mix them into the production truth path.

### P1-20 Gateway endpoint validation is too permissive

Any HTTPS URL, including credentials, query, fragment, arbitrary path, or unexpected host, can be saved. Paths are concatenated onto the raw endpoint.

Required fix: normalize to an origin plus optional approved base path; reject userinfo, query, fragment, private/local addresses in public builds, and unapproved stream origins.

### P1-21 WebSocket reconnect is unbounded fixed-delay

Five-second reconnect loops have no exponential backoff, jitter, attempt ceiling, online/offline awareness, or heartbeat timeout.

Required fix: state machine with bounded exponential backoff, jitter, stale detection, and manual recovery.

### P1-22 Stream quote validation is insufficient

Finite negative price and implausible jumps can update the quote state; timestamps and market status are not fully checked.

Required fix: positive price, tick size, timestamp window, session/extended-hours semantics, sequence, symbol, provider, and tolerance checks.

### P1-23 Local snapshots are treated as “trusted” without integrity

Browser localStorage is user/script mutable and untrusted. It has no cryptographic integrity, source signature, robust schema migration, or server attestation.

Required fix: call it a local cache, validate every load, include schema/build/provider/request IDs and expiry, and never use it as proof of authenticity.

### P1-24 Monolithic standalone HTML is not maintainable

The artifact is roughly 500 KB with thousands of lines of inline CSS/JS and many responsibilities: workflow engine, storage, AI connector, market adapters, chart, stream, tests, and UI.

Required fix: modular source tree with build output; isolate domain, transport, state, rendering, workflow, model connector, and tests.

### P1-25 Inline script prevents a strong CSP

There is no enforceable production Content Security Policy compatible with the current monolith.

Required fix: external hashed assets, CSP, `connect-src` allowlist, frame restrictions, no unsafe eval, and security headers.

### P1-26 Tests contain implementation-string assertions

Some browser tests check that function source text contains strings rather than testing behavior.

Required fix: fixture-driven black-box contract tests and mutation-resistant assertions.

### P1-27 Frontend browser checks are not in CI

Backend CI passes, but the complete frontend and Playwright-style tests are not part of repository CI.

Required fix: clean-checkout browser CI on desktop/mobile viewports, offline/network-error mocks, storage corruption, API schema drift, and stream tests.

### P1-28 Floating dependencies make release builds non-reproducible

Requirements use ranges without a lockfile/hashes.

Required fix: pinned lock, dependency update process, vulnerability scan, and tz/calendar version recording.

## P2 — robustness, product, and tester-readiness gaps

- No precise accuracy/latency SLOs or reference-terminal tolerance matrix.
- No captured provider fixtures for US, HK, SH, and SZ.
- No early-close/special-session fixture suite.
- Shenzhen currently reuses Shanghai calendar without formal verification.
- No corporate-action, split, dividend, suspension, halt, auction, or delisting model.
- No instrument tick-size, lot-size, volume-unit, or price-precision metadata.
- No independent quote feed; live tick status remains unavailable.
- Exact historical-date mode is unimplemented.
- Extended-hours semantics are unimplemented.
- No clock-skew detection between browser, gateway, provider, and reference terminal.
- No monotonic latency timing or percentile telemetry.
- No accessibility gate, keyboard audit, contrast audit, or screen-reader flow.
- No mobile performance/memory budget or large-series rendering stress test.
- No structured client telemetry with privacy-safe correlation IDs.
- No feature flags, migration strategy, rollback package, or release manifest.
- No artifact checksum/signature verification in the UI.
- Duplicate/legacy gateway directories risk code drift and wrong deployment root.
- Public `/docs` and health metadata need an explicit production exposure policy.
- No deterministic handling of storage quota failure; some persistence errors are swallowed.
- No data-retention policy for task records, snapshots, or model prompts.
- No test-persona scripts for quant analyst, frontend QA, and incident operator.

## Required closure order

1. P0 security and truth-gate closure.
2. Typed contract and canonical instrument model.
3. Provider adapter hardening and session correctness.
4. Frontend modularization and strict state machine.
5. CI/browser/security/performance gates.
6. Provider fixtures and reference-terminal tolerance report.
7. Staff alpha package, rollback package, and test handbook.

No v1.0 RELEASE CANDIDATE tag until all P0 and P1 items are closed or explicitly waived with written evidence.