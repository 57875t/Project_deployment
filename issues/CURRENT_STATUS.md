# QR Desk Current Status

## Version

`v0.8 K-line Core — Phase 2`

## Current verdict

**PARTIAL PASS / Draft**

## Completed

- [x] Unified QR Desk repository structure
- [x] Read-only cloud market-data gateway
- [x] Provider fail-closed behavior
- [x] OHLCV invariant validation
- [x] Duplicate and future timestamp handling
- [x] Exchange-local timestamp parsing
- [x] XNYS, XHKG and XSHG calendar mapping
- [x] Weekend, holiday, lunch-break and session-state logic
- [x] Off-session bar removal
- [x] Incomplete intraday and daily bar removal
- [x] Strict 5m → 15m aggregation
- [x] Session-aware gap counting
- [x] Previous-session change separated from last-bar change
- [x] Deterministic test suite: 9 passed
- [x] GitHub Actions K-line CI workflow added

## Open

- [ ] Verify Massive timestamp convention with licensed responses
- [ ] Verify EODHD timestamp convention for US/HK/CN
- [ ] Validate early-close and special-session samples
- [ ] Validate Shenzhen schedule equivalence against exchange reference
- [ ] Reconcile adjusted prices and corporate actions
- [ ] Add dual-provider cross-check and tolerance report
- [ ] Wire `marketSession`, `quality`, `change` and `barChange` into HTML
- [ ] Compare last completed candle and percentage change against a reference UI
- [ ] Complete live entitlement and latency acceptance

## Truth boundary

- No API credentials in the browser or repository.
- No simulated candles in real-data responses.
- No interpolation or synthetic gap filling.
- No LIVE PASS until licensed provider output is compared against a reference feed.
