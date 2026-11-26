"""Configuration. Never send payOS keys to the browser."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')

MODE = os.getenv('PAYMENT_MODE', 'demo').strip().lower()
if MODE not in {'demo', 'live'}:
    raise RuntimeError('PAYMENT_MODE must be demo or live')
DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
# Vercel Functions do not have persistent writable local files.
# Require PostgreSQL for every Vercel deployment, including demo mode.
if os.getenv('VERCEL') and not DATABASE_URL:
    raise RuntimeError('Set DATABASE_URL to a persistent PostgreSQL connection URL in Vercel environment variables')
if DATABASE_URL and not DATABASE_URL.startswith(('postgresql://', 'postgres://')):
    raise RuntimeError('DATABASE_URL must be a PostgreSQL connection string')
DB_PATH = Path(os.getenv('DATABASE_PATH', str(ROOT / 'data' / 'payments.sqlite3')))
# Public demo QR destinations should resolve from a Vercel deployment URL.
# For real payOS webhooks, set PUBLIC_BASE_URL explicitly to a stable production URL.
_vercel_host = os.getenv('VERCEL_URL', '').strip()
BASE_URL = os.getenv('PUBLIC_BASE_URL', '').strip() or (f'https://{_vercel_host}' if _vercel_host else 'http://localhost:8000')
BASE_URL = BASE_URL.rstrip('/')
CLIENT_ID = os.getenv('PAYOS_CLIENT_ID', '').strip()
API_KEY = os.getenv('PAYOS_API_KEY', '').strip()
CHECKSUM_KEY = os.getenv('PAYOS_CHECKSUM_KEY', '').strip()
PRICE_MONTHLY = int(os.getenv('PRICE_MONTHLY_VND', '600000'))
PRICE_3MONTH = int(os.getenv('PRICE_3MONTH_VND', '1650000'))
PRICE_6MONTH = int(os.getenv('PRICE_6MONTH_VND', '3000000'))
PRICE_MAP = {1: PRICE_MONTHLY, 3: PRICE_3MONTH, 6: PRICE_6MONTH}

if any(x <= 0 for x in PRICE_MAP.values()):
    raise RuntimeError('Prices must be positive amounts of VND')
if MODE == 'live':
    if not all([CLIENT_ID, API_KEY, CHECKSUM_KEY]):
        raise RuntimeError('LIVE requires PAYOS_CLIENT_ID, PAYOS_API_KEY, PAYOS_CHECKSUM_KEY')
    if not BASE_URL.startswith('https://'):
        raise RuntimeError('LIVE requires PUBLIC_BASE_URL with a public HTTPS address for webhook/return URLs')
