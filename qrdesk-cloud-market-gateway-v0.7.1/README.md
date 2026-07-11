# QR Desk v0.7.1 · Cloud Market Data Gateway

This branch replaces the local Moomoo/OpenD requirement with a read-only cloud REST gateway.

## Contract preserved

- `GET /v1/market/health`
- `GET /v1/market/bundle?instrument=US.AAPL&symbol=AAPL&range=1d&interval=5m&extended=false`

The response shape is designed for the existing QR Desk v0.6.0 Broker Market Data Gateway hook.

## Safety boundary

- No broker client is installed on the user's computer.
- No trading, account, position, balance, or order API exists.
- Provider keys are server-side environment secrets only.
- The gateway never substitutes simulated prices when a provider fails.
- Data recency is included in `provenance.recency`; delayed data is not labeled real-time.

## Providers

- **Massive:** US aggregate OHLCV. Plan recency can be end-of-day, 15-minute delayed, or real-time; set `MASSIVE_RECENCY` to the actual purchased plan.
- **EODHD:** global intraday historical data. The provider documents that intraday data is delayed and finalized after market close, so this adapter labels it delayed/historical.

## Cloud deployment

```bash
pip install -r requirements.txt
uvicorn qrdesk_gateway.app:app --host 0.0.0.0 --port 8000
```

Set at least one secret:

- `MASSIVE_API_KEY`
- `EODHD_API_TOKEN`

Set `QRDESK_ALLOWED_ORIGINS` to the deployed QR Desk origin in production.

After deployment, paste the HTTPS service root into QR Desk's “真实行情网关” field. Remote HTTP endpoints are intentionally rejected by the current HTML.

## Current audit verdict

**NEEDS FIX, not production PASS.**

Open gates are recorded in `docs/WORKFLOW_AUDIT.md`, especially HK/CN symbol verification, 6-month daily routing, historical-date mode, live credentials, and deployment acceptance.
