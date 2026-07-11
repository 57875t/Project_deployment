---
name: qrdesk-cloud-market-data
description: Build, audit, and validate the QR Desk read-only cloud market-data gateway and its HTML integration without fabricating live data.
---

# QR Desk Cloud Market Data Skill

## Use this skill when

- adding or changing a market-data provider;
- modifying `/v1/market/health` or `/v1/market/bundle`;
- changing K-line ranges, intervals, timestamps, sessions, or provenance;
- preparing cloud deployment;
- connecting the QR Desk HTML to a cloud gateway;
- reviewing whether data labeled real is actually supported by a provider response.

## Hard constraints

1. Real fields may contain only provider-returned data that passed validation.
2. Provider failure must fail closed. Never backfill a real response with generated candles.
3. Simulation must remain a separate, visibly labeled mode.
4. Weekends, exchange holidays, breaks and closed sessions must not create a fake current-day candle.
5. A still-forming bar must not be presented as a completed bar.
6. Provider recency must be labeled honestly: real-time, delayed, end-of-day, or historical.
7. API keys belong only in server-side secrets.
8. The gateway is read-only: no balances, positions, trading passwords, or order endpoints.
9. Aggregation may combine real source bars deterministically, but incomplete buckets must be dropped.
10. Gap detection must ignore legitimate overnight closures, holidays and lunch breaks.

## Workflow

1. Preview the provider contract, interval, timestamp convention and entitlement assumptions.
2. Implement in an isolated branch.
3. Normalize numbers and exchange-local timestamps.
4. Apply the correct exchange calendar before aggregation or quality scoring.
5. Remove off-session and still-forming bars.
6. Aggregate only contiguous complete source buckets.
7. Run the project Nitpick checklist and deterministic tests.
8. Review all error paths, session fields and provenance fields.
9. Test US/HK/CN examples, lunch breaks, weekends and current-session behavior.
10. Record PASS/OPEN/NEEDS FIX in the audit document.
11. Keep the pull request in Draft until live acceptance is complete.

## Required output fields

A successful bundle must include:

- instrument metadata;
- quote values;
- previous-session change and last-bar change as separate fields;
- normalized OHLCV bars;
- market session state and exchange calendar;
- provider name;
- entitlement/recency label;
- provider timestamp and fetch timestamp;
- delay in seconds when measurable;
- quality counters for duplicates, invalid bars, gaps, off-session bars and incomplete bars;
- request ID;
- warnings and provider attempts;
- `syntheticBars: 0` for the real-data path.

## Audit questions

- Did the provider actually support the requested symbol and exchange?
- Is the interval native or aggregated?
- If aggregated, were all source bars complete and contiguous?
- Are daily and intraday endpoints correctly separated?
- Is the timestamp bar-start or bar-end, and was that verified rather than assumed?
- Is the last bar complete or still forming?
- Are time zones and daylight-saving transitions correct?
- Are exchange holidays, early closes and lunch breaks applied?
- Are adjusted/unadjusted prices labeled?
- Is the last bar from a valid trading session?
- Does `previousClose` refer to the prior session rather than the prior intraday candle?
- Can a quota, entitlement, or authentication failure be mistaken for an empty market?
