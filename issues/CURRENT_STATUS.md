# Current Project Status

## PASS

- GitHub repository is connected and writable.
- Dedicated QR Desk workspace branch exists.
- Root-level Railway entrypoint and dependency file exist.
- Railway config-as-code exists.
- Read-only FastAPI gateway contract exists.
- API keys are designed to remain server-side.
- Workflow and project Skill are stored in the repository.

## NEEDS FIX

- EODHD `6mo / 1d` must use the provider's dedicated end-of-day endpoint rather than the intraday path.
- Exact historical-date mode is not implemented.
- 15-minute bars from a 5-minute source need deterministic aggregation and validation.
- Market-session and holiday logic needs a dedicated exchange-calendar layer.
- Provider errors should use stable internal error codes rather than raw exception text.
- Automated unit and contract tests need to be moved to the root workspace and run in CI.

## BLOCKED

- Live provider acceptance requires at least one valid cloud API credential.
- Railway deployment requires Railway to be linked to the GitHub account `57875t` and granted access to `Project_deployment`.
- Final HTML integration requires the generated Railway HTTPS domain.

## Next acceptance sequence

1. Deploy branch `agent/qrdesk-workspace-restructure` on Railway.
2. Generate a public Railway domain.
3. Add one provider key as a Railway Variable.
4. Verify `/v1/market/health`.
5. Run US/HK/CN test requests.
6. Insert the Railway HTTPS base URL into the QR Desk HTML.
7. Run the full Nitpick and Acceptance workflow.
