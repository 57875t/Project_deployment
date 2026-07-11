#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
exec python -m uvicorn qrdesk_gateway.app:app --host "${QRDESK_GATEWAY_HOST:-127.0.0.1}" --port "${QRDESK_GATEWAY_PORT:-8787}"
