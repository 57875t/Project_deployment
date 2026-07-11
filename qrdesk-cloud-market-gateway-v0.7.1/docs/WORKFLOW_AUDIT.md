# QR Desk Cloud Gateway — Workflow Audit

## Preview

Goal: replace the local Moomoo/OpenD dependency with a cloud REST gateway while preserving the QR Desk front-end contract.

Non-negotiable constraints:

1. No broker client installed on the user's computer.
2. No API key in browser HTML or localStorage.
3. No simulated/calibrated value may be returned as real market data.
4. Provider recency must be disclosed; delayed data cannot be labeled real-time.
5. Provider failure must return a structured error rather than fabricated bars.
6. Read-only market data only; no account, order, balance, or position endpoints.

## Execute

- Added `/v1/market/health` and `/v1/market/bundle`.
- Added Massive adapter for US aggregate bars.
- Added EODHD adapter for authenticated global delayed/historical bars.
- Added fixed instrument allowlist matching the current QR Desk watchlist.
- Added OHLCV invariant and timestamp validation.
- Added provenance fields including provider, recency, delay, request ID, warnings, and failed attempts.

## Find faults

### Critical gates

- **PASS:** no trade context or order endpoint exists.
- **PASS:** secrets are read only from server environment variables.
- **PASS:** response construction contains no simulated-price generator.
- **PASS:** remote provider failures terminate with `PROVIDER_FAILURE`.
- **OPEN:** exact provider symbols for HK/Shanghai/Shenzhen must be verified against the subscribed EODHD exchange list before production acceptance.
- **OPEN:** `6mo / 1d` should use a dedicated EOD endpoint rather than the intraday endpoint.
- **OPEN:** exact historical-date mode is intentionally blocked with HTTP 501 until implemented and tested.

### Major gates

- **OPEN:** cloud host, encrypted secrets, production CORS allowlist, and platform-level rate limiting are not yet configured.
- **OPEN:** live acceptance cannot pass without actual provider credentials.
- **OPEN:** QR Desk HTML default endpoint still points to localhost; the deployed HTTPS endpoint must be set after deployment.

## Review

Current verdict: **NEEDS FIX — architecture accepted, live data acceptance blocked.**

The branch is safe to review because it does not claim live success. It is not ready to merge as a production-complete gateway until the open critical gates are closed.

## Acceptance

Required evidence:

- US, HK, and CN sample responses with provider request IDs.
- Timestamp monotonicity and OHLC invariants pass.
- Provider recency label matches the purchased plan.
- Invalid key test returns an error and zero bars.
- Browser network inspection confirms no provider token is exposed.
- QR Desk displays unavailable state when the gateway fails.
