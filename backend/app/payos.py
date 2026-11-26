"""payOS v2 payment link + signed webhook integration (no credentials in frontend)."""
import hashlib
import hmac
import json
import requests
from .config import CLIENT_ID, API_KEY, CHECKSUM_KEY, BASE_URL

API = 'https://api-merchant.payos.vn'

class PayOSError(RuntimeError):
    pass


def hmac_sha256(message):
    return hmac.new(CHECKSUM_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()


def create_signature(*, amount, cancel_url, description, order_code, return_url):
    message = (f'amount={amount}&cancelUrl={cancel_url}&description={description}'
               f'&orderCode={order_code}&returnUrl={return_url}')
    return hmac_sha256(message)


def _to_signed_value(value):
    if value is None or value in ('undefined', 'null'):
        return ''
    if isinstance(value, list):
        return json.dumps([dict(sorted(x.items())) if isinstance(x, dict) else x for x in value],
                          ensure_ascii=False, separators=(',', ':'))
    if isinstance(value, bool):
        return 'true' if value else 'false'
    return str(value)


def verify_webhook(body):
    if not isinstance(body, dict) or not isinstance(body.get('data'), dict):
        return False
    signature = body.get('signature')
    if not isinstance(signature, str) or len(signature) != 64:
        return False
    fields = body['data']
    message = '&'.join(f'{key}={_to_signed_value(fields[key])}' for key in sorted(fields))
    return hmac.compare_digest(hmac_sha256(message), signature.lower())


def headers():
    return {'x-client-id': CLIENT_ID, 'x-api-key': API_KEY, 'content-type': 'application/json'}


def payos_request(method, path, payload=None):
    try:
        r = requests.request(method, f'{API}{path}', headers=headers(), json=payload, timeout=12)
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        raise PayOSError(f'payOS unavailable: {type(exc).__name__}') from exc
    if r.status_code != 200 or data.get('code') != '00' or not data.get('data'):
        raise PayOSError(f'payOS request rejected (HTTP {r.status_code}, code={data.get("code", "unknown")})')
    return data['data']


def create_payment_link(order, attempt):
    token = order['token']
    # URL redirect is only for navigation. NEVER mark an invoice PAID from query parameters.
    success_url = f'{BASE_URL}/?receipt={token}&provider_return=1'
    cancel_url = f'{BASE_URL}/?receipt={token}&provider_cancel=1'
    # Conservative short ASCII description fits restrictions on unlinked bank accounts.
    description = f'GYM{attempt["id"]}'[:9]
    payload = {
        'orderCode': int(attempt['order_code']),
        'amount': int(order['amount']),
        'description': description,
        'cancelUrl': cancel_url,
        'returnUrl': success_url,
    }
    payload['signature'] = create_signature(amount=payload['amount'], cancel_url=cancel_url,
        description=description, order_code=payload['orderCode'], return_url=success_url)
    return payos_request('POST', '/v2/payment-requests', payload)


def get_payment_link(order_code):
    return payos_request('GET', f'/v2/payment-requests/{int(order_code)}')


def confirm_webhook():
    return payos_request('POST', '/confirm-webhook', {'webhookUrl': f'{BASE_URL}/api/webhooks/payos'})
