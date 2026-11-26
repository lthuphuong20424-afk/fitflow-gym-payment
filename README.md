# FitFlow STRIDE v10 — Gym Membership Payment Demo

Frontend (HTML/CSS/JavaScript) + FastAPI backend + SQLite locally / PostgreSQL on Vercel. **No Docker.** Customer-facing screens use English. MoMo-style provider checkout is a classroom simulator, not the official MoMo app.

## The two payment journeys

### A. Dynamic VietQR (redesigned in v10)

1. **FitFlow checkout**: select a membership plan and create an invoice.
2. **VietQR payment screen**: show amount, QR, invoice-specific reference and **Awaiting payment confirmation**. No giant arrow, forced Demo Bank transition, or customer “I've paid” button.
3. **Live via payOS**: the QR uses the actual payment payload returned by payOS; the customer scans using their banking app and authorizes a transfer. The backend verifies payOS webhook/status, matches amount and order, then changes the invoice to `PAID`. The open FitFlow screen polls the backend and displays the digital receipt.
4. **Classroom Demo**: the QR encodes **sample invoice details only**, labelled *NOT A BANK TRANSFER*. It is not payable using a real banking app. The presenter expands **Presenter / QA → Simulate bank / payOS callback → Send success event**. The backend records a simulated event; FitFlow fetches status and automatically displays the digital receipt. No separate banking tab/page is needed.

**Scanning a QR is not a proof of payment.** If no verified result arrives, the invoice stays `PENDING`. `UNKNOWN`/timeout requires checking the original request before retrying. Duplicate provider events do not activate the membership twice.

### B. MoMo demo (kept from v9)

**FitFlow Monthly Pass → Pre-linked sample MoMo wallet → MoMo-style Payment → Confirm → Transaction Details / Success → Return to FitFlow → Digital Receipt.** All in the same browser tab. Customer support is a demo sheet labelled **Liên hệ CSKH**; no live CSKH integration. The previously authorized wallet and subsequent collection are **classroom simulation only**; no actual MoMo merchant integration/token exists.

## Run locally on Windows

```powershell
py --version
.\run_windows.bat
```

Open **http://localhost:8000**. Use `Ctrl+C` in Terminal to stop the backend. No MySQL, Docker or Node server required.

- Files: `frontend/` (UI), `backend/app/main.py` (API), `backend/app/store.py` (SQLite), `backend/app/store_postgres.py` (PostgreSQL), `tests/` (QA).
- Run regression tests: `py -m pip install pytest httpx` then `py -m pytest -q tests`.
- Detailed demonstration instructions: [`docs/VIETQR_V10_PAYMENT_FLOW_VI.md`](docs/VIETQR_V10_PAYMENT_FLOW_VI.md) and [`docs/MOMO_TRANSACTION_DETAILS_VI.md`](docs/MOMO_TRANSACTION_DETAILS_VI.md).

## Vercel / payOS Live

See [`docs/DEPLOY_VERCEL_VI.md`](docs/DEPLOY_VERCEL_VI.md). Vercel requires a **persistent PostgreSQL** database (`DATABASE_URL`), even in Demo mode. SQLite in ephemeral Vercel storage is not durable. In `PAYMENT_MODE=live`, configure `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY` and public HTTPS `PUBLIC_BASE_URL`. Live mode verifies signed payment notifications; the classroom Demo event endpoint is disabled. Merchant onboarding and production security hardening are still required.

**Security scope:** Educational prototype with no proper user authentication, access controls, or full operational reconciliations. Do not deploy for actual merchant transactions without engineering and compliance review. Never commit `.env` or payment credentials.
