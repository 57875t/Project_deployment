---
name: qrdesk-cloud-market-data
description: Build, audit, and validate the QR Desk read-only cloud market-data gateway and its HTML integration without fabricating live data.
---

# QR Desk Cloud Market Data Skill

## Use this skill when

- adding or changing a market-data provider;
- modifying `/v1/market/health` or `/v1/market/bundle`;
- changing K-line ranges, intervals, timestamps, sessions, or provenance;
- preparing Railway deployment;
- connecting the QR Desk HTML to a cloud gateway;
- reviewing whether data labeled real is actually supported by a provider response.

## Hard constraints

1. Real fields may contain only provider-returned data that passed validation.
2. Provider failure must fail closed. Never backfill a real response with generated candles.
3. Simulation must remain a separate, visibly labeled mode.
4. Weekends, exchange holidays, and closed sessions must not create a fake current-day candle.
5. Provider recency must be labeled honestly: real-time, delayed, end-of-day, or historical.
6. API keys belong only in server-side secrets.
7. The gateway is read-only: no balances, positions, trading passwords, or order endpoints.

## Workflow

1. Preview the provider contract and entitlement assumptions.
2. Implement in an isolated branch.
3. Run the project Nitpick checklist.
4. Review all error paths and provenance fields.
5. Test US/HK/CN examples and closed-market behavior.
6. Record PASS/OPEN/NEEDS FIX in the audit document.
7. Keep the pull request in Draft until live acceptance is complete.

## Required output fields

A successful bundle must include:

- instrument metadata;
- quote values;
- normalized OHLCV bars;
- provider name;
- entitlement/recency label;
- provider timestamp and fetch timestamp;
- delay in seconds when measurable;
- request ID;
- warnings and provider attempts.

## Audit questions

- Did the provider actually support the requested symbol and exchange?
- Is the interval native or aggregated?
- Are daily and intraday endpoints correctly separated?
- Is the timestamp bar-start or bar-end?
- Is the bar complete or still forming?
- Are time zones and daylight-saving transitions correct?
- Are adjusted/unadjusted prices labeled?
- Is the last bar from a valid trading session?
- Can a quota, entitlement, or authentication failure be mistaken for an empty market?
