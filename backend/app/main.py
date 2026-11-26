"""Gym Pay: backend API, SQLite persistence, real payOS webhook and demo simulation."""
import io
import html
import json
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import parse_qs
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import qrcode
from . import config, payos
if config.DATABASE_URL:
    from . import store_postgres as store
else:
    from . import store

FRONTEND = config.ROOT / 'frontend'

@asynccontextmanager
async def lifespan(app):
    store.init_db()
    yield

app = FastAPI(title='Gym Membership Payment API', version='1.0', lifespan=lifespan)

class NewOrder(BaseModel):
    member_name: str = Field(min_length=2, max_length=60)
    months: Literal[1, 3, 6] = 1

class DemoOutcome(BaseModel):
    outcome: Literal['PAID', 'FAILED', 'PENDING', 'CANCELLED']


def order_or_404(token):
    item = store.present_order(token)
    if item is None:
        raise HTTPException(404, 'Invoice not found')
    return item

@app.get('/api/health')
def health():
    return {'ok': True, 'mode': config.MODE, 'database': 'postgresql' if config.DATABASE_URL else 'sqlite'}

@app.get('/api/config')
def runtime_config():
    return {'mode': config.MODE, 'prices': config.PRICE_MAP,
            'supports_real_vietqr': config.MODE == 'live',
            'momo_status': 'Prototype only – MoMo Subscription API is not connected'}

@app.post('/api/orders', status_code=201)
def create_order(request: NewOrder):
    member = ' '.join(request.member_name.split()).strip()
    if len(member) < 2:
        raise HTTPException(422, 'Please enter the member name')
    token = store.create_order(member, request.months, config.PRICE_MAP[request.months])
    return store.present_order(token)

@app.get('/api/orders/{token}')
def get_order(token: str):
    return order_or_404(token)

@app.post('/api/orders/{token}/payment-link')
def create_payment(token: str):
    order = order_or_404(token)
    if order['status'] == 'PAID':
        raise HTTPException(409, 'This invoice has already been paid')
    attempt, is_new = store.new_attempt(token, 'PAYOS' if config.MODE == 'live' else 'DEMO')
    if not is_new:
        return order_or_404(token)
    if config.MODE == 'demo':
        # Classroom-only reference QR, not an EMV/VietQR bank instruction.
        # Scanning it reveals invoice text; it must NOT impersonate a live bank transfer.
        demo_reference = f'FF{order["id"]:05d}'
        qr_text = (f'FITFLOW CLASSROOM DEMO - NOT A BANK TRANSFER\n'
                   f'Invoice: FF-{order["id"]:05d}\n'
                   f'Membership: {order["months"]} month(s)\n'
                   f'Amount: {order["amount"]} VND\n'
                   f'Reference: {demo_reference}')
        store.update_attempt(attempt['id'], status='PENDING', qr_payload=qr_text,
                             checkout_url=None, description=demo_reference)
        return order_or_404(token)
    try:
        link = payos.create_payment_link(order, attempt)
    except payos.PayOSError as exc:
        # PSP may have created the payment link even if the HTTP response was lost.
        # Never mark this FAILED and generate a different new request automatically.
        store.update_attempt(attempt['id'], status='UNKNOWN')
        raise HTTPException(502, f'{exc}. Status is unknown; check the original payOS request before creating another one.') from exc
    if int(link.get('orderCode', -1)) != attempt['order_code'] or int(link.get('amount', -1)) != order['amount']:
        store.update_attempt(attempt['id'], status='UNKNOWN')
        raise HTTPException(502, 'The payOS response does not match the invoice; manual review is required')
    store.update_attempt(attempt['id'], status='PENDING',
        qr_payload=link['qrCode'], checkout_url=link['checkoutUrl'],
        payment_link_id=link.get('paymentLinkId'), bank_bin=link.get('bin'),
        account_number=link.get('accountNumber'), account_name=link.get('accountName'),
        description=link.get('description'))
    return order_or_404(token)

@app.get('/api/orders/{token}/qr.png')
def qr_code(token: str, attempt: int | None = None):
    order = order_or_404(token)
    # Only current, active QR is rendered. Old attempt links cannot display a replaced QR.
    item = store.recent_attempt_for_order(token)
    if not item or not item['qr_payload']:
        raise HTTPException(404, 'No QR payment request exists for this invoice')
    if attempt is not None and int(item['id']) != attempt:
        raise HTTPException(410, 'This QR payment request has been replaced')
    qr = qrcode.QRCode(version=None, box_size=8, border=3, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(item['qr_payload']); qr.make(fit=True)
    buf = io.BytesIO(); qr.make_image(fill_color='#16202c', back_color='white').save(buf, format='PNG')
    return Response(buf.getvalue(), media_type='image/png', headers={'Cache-Control':'no-store'})

@app.post('/api/demo/orders/{token}/outcome')
def demo_outcome(token: str, change: DemoOutcome):
    if config.MODE != 'demo':
        raise HTTPException(404, 'Demo controls disabled in LIVE')
    order = order_or_404(token)
    attempt = store.recent_attempt_for_order(token)
    if not attempt:
        raise HTTPException(409, 'Create a payment request before simulating the outcome')
    if attempt['provider'] != 'DEMO':
        raise HTTPException(409, 'This classroom VietQR simulator only accepts DEMO VietQR attempts')
    if change.outcome == 'PENDING':
        return {'result':'PENDING', 'order': order}
    # Simulates a trusted backend event after the bank/PSP side has confirmed.
    fake_reference = f'DEMO_{attempt["order_code"]}_{change.outcome}'
    result = store.apply_event(attempt['order_code'], outcome=change.outcome,
        amount=order['amount'], source='DEMO', reference=fake_reference)
    return {'result': result, 'order': order_or_404(token)}

@app.post('/api/demo/orders/{token}/momo/start')
def demo_momo_start(token: str):
    """Create a pending, expiring authorization; never claim a real MoMo link."""
    if config.MODE != 'demo':
        raise HTTPException(404, 'MoMo simulator disabled in LIVE')
    try:
        nonce = store.demo_momo_start(token)
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    return {'authorization_url': f'/demo/momo/{token}?auth={nonce}',
            'order': order_or_404(token), 'simulated': True}


@app.post('/api/demo/orders/{token}/momo/next-cycle')
def demo_momo_next_billing_cycle(token: str):
    """Presenter-only: simulate due date, make new invoice, request recurring charge.

    The next payment is merchant-initiated, so there is no second wallet approval.
    This is NOT a real scheduler or MoMo Subscription API integration.
    """
    if config.MODE != 'demo':
        raise HTTPException(404,'Next-cycle simulator disabled in LIVE')
    try:
        next_token=store.demo_momo_next_cycle(token)
        attempt, new=store.new_attempt(next_token,'MOMO_DEMO')
        if new or attempt['status']=='CREATING':
            store.update_attempt(attempt['id'],status='PENDING')
        return {'order':order_or_404(next_token),'simulated':True,
                'message':'Simulated monthly due date and merchant-initiated collection. Awaiting provider result.'}
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@app.post('/api/demo/orders/{token}/momo/charge')
def demo_momo_charge(token: str):
    """Open a separate first-payment simulator using a pre-linked demo MoMo wallet."""
    if config.MODE != 'demo':
        raise HTTPException(404, 'MoMo simulator disabled in LIVE')
    order = order_or_404(token)
    if order['months'] != 1:
        raise HTTPException(409,'Demo MoMo is available only for monthly memberships')
    if order['status'] == 'PAID':
        raise HTTPException(409,'Invoice already paid')
    try:
        store.ensure_demo_momo_subscription(token)
        attempt, new = store.new_attempt(token,'MOMO_DEMO')
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    if not new and attempt['provider'] != 'MOMO_DEMO':
        raise HTTPException(409,'Resolve the current non-MoMo payment attempt first')
    link = f'/demo/momo/{token}/payment?attempt={attempt["id"]}'
    if new or attempt['status'] == 'CREATING':
        store.update_attempt(attempt['id'],status='PENDING',checkout_url=link)
    return {'checkout_url':link,'order':order_or_404(token),'simulated':True}


def _momo_sim_page(payload: dict) -> str:
    """Serve one shared, explicitly labelled MoMo-style simulator UI for consent and payment.

    Form actions remain on the server, and all personally supplied values are JSON-encoded
    with HTML script-escape protection. No real provider login or money movement occurs.
    """
    template = (FRONTEND / 'momo_simulator.html').read_text(encoding='utf-8')
    safe_json = (json.dumps(payload, ensure_ascii=False).replace('<', chr(92) + 'u003c')
                 .replace('>', chr(92) + 'u003e').replace('&', chr(92) + 'u0026'))
    return template.replace('<!-- MOMO_BOOTSTRAP -->',
        f'<script type="application/json" id="momo-data">{safe_json}</script>')


def _momo_auth_html(order, status, nonce):
    token=order['token']
    return _momo_sim_page({
        'kind':'authorization',
        'status':status,
        'invoice':f'FF-{order["id"]:05d}',
        'amount':order['amount'],
        'member_name':order['member_name'],
        'primary_action':f'/demo/momo/{token}/decision?auth={nonce}&decision=approve',
        'decline_action':f'/demo/momo/{token}/decision?auth={nonce}&decision=decline',
        'return_url':f'/?receipt={token}',
    })


@app.get('/demo/momo/{token}',response_class=HTMLResponse)
def momo_wallet_simulator(token: str, auth: str):
    if config.MODE != 'demo': raise HTTPException(404,'MoMo simulator disabled in LIVE')
    try:
        session = store.demo_momo_session(token,auth)
    except ValueError as exc:
        raise HTTPException(410,str(exc)) from exc
    return HTMLResponse(_momo_auth_html(order_or_404(token),session['status'],auth),headers={'Cache-Control':'no-store'})


@app.post('/demo/momo/{token}/decision',response_class=HTMLResponse)
async def momo_wallet_decision(token: str, auth: str, decision: Literal['approve','decline'], request: Request):
    if config.MODE != 'demo': raise HTTPException(404,'MoMo simulator disabled in LIVE')
    # Browser simulator only: confirm a published sample wallet alias, never a real wallet secret.
    # Older automated clients may post without a body; preserve that test-only interface.
    if decision == 'approve':
        payload=parse_qs((await request.body()).decode('utf-8'))
        if payload and payload.get('wallet_suffix', [''])[0] != '8842':
            raise HTTPException(422, 'Demo wallet reference must match the displayed sample (8842)')
    try:
        status=store.demo_momo_decide(token,auth,decision=='approve')
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc
    return HTMLResponse(_momo_auth_html(order_or_404(token),status,auth),headers={'Cache-Control':'no-store'})


def _momo_charge_context(token: str, attempt_id: int):
    if config.MODE != 'demo':raise HTTPException(404,'MoMo payment simulator disabled in LIVE')
    order=order_or_404(token)
    item=store.recent_attempt_for_order(token)
    if not item or item['id']!=attempt_id or item['provider']!='MOMO_DEMO' or item['status'] not in ('PENDING','PAID','FAILED'):
        raise HTTPException(409,'Invalid or superseded simulated MoMo payment')
    if not order['subscription'] or order['subscription']['status'] not in ('ACTIVE_DEMO','CANCELLED_DEMO'):
        raise HTTPException(409,'No MoMo authorization associated with invoice')
    return order,item


def _momo_charge_html(order, item):
    token=order['token']
    return _momo_sim_page({
        'kind':'payment',
        'status':item['status'],
        'invoice':f'FF-{order["id"]:05d}',
        'amount':order['amount'],
        'member_name':order['member_name'],
        'primary_action':f'/demo/momo/{token}/payment/decision?attempt={item["id"]}&outcome=PAID',
        'decline_action':f'/demo/momo/{token}/payment/decision?attempt={item["id"]}&outcome=FAILED',
        'return_url':f'/?receipt={token}',
        'transaction_reference':item.get('reference') or '',
        'paid_at':order.get('paid_at') or '',
        'membership_until':order.get('membership_until') or '',
        'plan_name':'Monthly Pass' if order.get('months') == 1 else f"{order['months']}-Month Pass",
    })


@app.get('/demo/momo/{token}/payment',response_class=HTMLResponse)
def momo_first_payment_simulator(token: str,attempt: int):
    order,item=_momo_charge_context(token,attempt)
    return HTMLResponse(_momo_charge_html(order,item),headers={'Cache-Control':'no-store'})


@app.post('/demo/momo/{token}/payment/decision',response_class=HTMLResponse)
async def momo_first_payment_decision(token: str,attempt: int,outcome:Literal['PAID','FAILED'],request:Request):
    order,item=_momo_charge_context(token,attempt)
    posted=parse_qs((await request.body()).decode('utf-8'))
    payment_source=posted.get('payment_source', ['momo_wallet'])[0]
    if payment_source not in {'momo_wallet','vcb_demo','tcb_demo','bidv_demo'}:
        raise HTTPException(422, 'Unknown sample payment source')
    if item['status']=='PENDING':
        result=store.apply_event(item['order_code'],outcome=outcome,amount=order['amount'],
                source='MOMO_SIMULATOR',reference=f'MOMO_SIM_{item["order_code"]}_{outcome}')
        if result not in ('PAID','FAILED','DUPLICATE','DUPLICATE_VERIFIED_PAYMENT'):
            raise HTTPException(409,f'Could not apply payment outcome: {result}')
    # POST/Redirect/GET: refreshing the success screen must never repost the payment form.
    return RedirectResponse(
        url=f'/demo/momo/{token}/payment?attempt={attempt}',
        status_code=303,
        headers={'Cache-Control':'no-store'},
    )


@app.post('/api/demo/orders/{token}/momo/collect')
def demo_momo_collect(token: str, outcome: DemoOutcome):
    if config.MODE != 'demo':
        raise HTTPException(404, 'MoMo demo disabled in LIVE')
    order = order_or_404(token)
    if not order['subscription'] or order['subscription']['status'] != 'ACTIVE_DEMO':
        raise HTTPException(409, 'Subscription consent not active')
    if order['status'] == 'PAID':
        raise HTTPException(409, 'Invoice is already PAID')
    attempt, new = store.new_attempt(token, 'MOMO_DEMO')
    if not new and attempt['provider'] != 'MOMO_DEMO':
        raise HTTPException(409, 'Existing payment attempt must be resolved first')
    if outcome.outcome == 'PENDING':
        store.update_attempt(attempt['id'], status='PENDING')
        return {'result':'PENDING','order':order_or_404(token)}
    result = store.apply_event(attempt['order_code'], outcome=outcome.outcome, amount=order['amount'],
        source='MOMO_DEMO', reference=f'MOMO_{attempt["order_code"]}_{outcome.outcome}')
    return {'result':result,'order':order_or_404(token)}

@app.post('/api/demo/orders/{token}/momo/cancel')
def demo_momo_cancel(token: str):
    if config.MODE != 'demo':
        raise HTTPException(404, 'MoMo demo disabled in LIVE')
    try:
        return store.demo_momo_cancel(token)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

@app.post('/api/orders/{token}/sync')
def synchronize_status(token: str):
    order = order_or_404(token)
    if config.MODE == 'demo':
        return {'result':'DEMO_NO_REMOTE_PROVIDER', 'order': order}
    attempt = store.recent_attempt_for_order(token)
    if not attempt or attempt['status'] in ('FAILED', 'CANCELLED', 'PAID'):
        return {'result':'NO_ACTIVE_PAYMENT', 'order': order}
    # 12-second throttle protects PSP from browser polling.
    if attempt['last_checked_at']:
        from datetime import datetime, timezone
        check = datetime.fromisoformat(attempt['last_checked_at'])
        if (datetime.now(timezone.utc) - check).total_seconds() < 12:
            return {'result':'THROTTLED', 'order': order}
    store.mark_checked(attempt['id'])
    try:
        remote = payos.get_payment_link(attempt['order_code'])
    except payos.PayOSError as exc:
        raise HTTPException(502, f'Unable to verify payOS status: {exc}') from exc
    if int(remote.get('orderCode', -1)) != attempt['order_code'] or int(remote.get('amount', -1)) != order['amount']:
        raise HTTPException(502, 'The payOS response does not match the invoice')
    status = str(remote.get('status', '')).upper()
    if status == 'PAID' and int(remote.get('amountPaid', 0)) >= order['amount']:
        # Reconcile by provider API; signed callback remains primary.
        result = store.apply_event(attempt['order_code'], outcome='PAID', amount=order['amount'],
            source='PAYOS', reference=f'LINK_{attempt["order_code"]}', payment_link_id=attempt['payment_link_id'])
    elif status in ('CANCELLED', 'EXPIRED'):
        result = store.apply_event(attempt['order_code'], outcome='CANCELLED', amount=order['amount'],
            source='PAYOS', reference=f'CANCEL_{attempt["order_code"]}')
    elif status == 'PENDING':
        # Recover orphaned CREATING/UNKNOWN attempt when payOS confirms creation.
        if attempt['status'] == 'UNKNOWN':
            link_id = remote.get('id')
            store.revive_pending_attempt(attempt['id'], str(link_id) if link_id else None,
                f'https://pay.payos.vn/web/{link_id}' if link_id else None)
        result = 'PENDING'
    else:
        result = 'REMOTE_STATUS_'+status[:20]
    return {'result':result, 'order':order_or_404(token)}

@app.post('/api/webhooks/payos')
async def payos_webhook(request: Request):
    if config.MODE != 'live':
        raise HTTPException(404, 'PayOS webhook inactive in DEMO')
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, 'Invalid JSON')
    if not payos.verify_webhook(body):
        raise HTTPException(400, 'Invalid payOS signature')
    data = body['data']
    # Signed *data* is authoritative; do not trust unsigned envelope alone.
    if str(data.get('code')) != '00' or str(data.get('currency')) != 'VND':
        return {'ok': True, 'result': 'NON_PAYMENT_EVENT'}
    try:
        code = int(data['orderCode'])
        amount = int(data['amount'])
    except (TypeError, ValueError, KeyError):
        raise HTTPException(400, 'Invalid transaction fields')
    reference = str(data.get('reference', '')).strip()
    if not reference:
        raise HTTPException(400, 'Missing bank reference')
    result = store.apply_event(code, outcome='PAID', amount=amount,
        source='PAYOS', reference=reference, payment_link_id=data.get('paymentLinkId'))
    # Signed amount/link mismatches have been stored as anomalies without granting access.
    # Acknowledge to avoid endless automatic webhook redelivery; finance must reconcile.
    # Signed provider test events might use codes absent from local DB; acknowledge safely.
    return {'ok': True, 'result': result}

def demo_bank_context(token: str, attempt_id: int):
    # Mock-bank flow exists in demo mode only.
    if config.MODE != 'demo':
        raise HTTPException(404, 'Demo bank is disabled in LIVE')
    order = order_or_404(token)
    attempt = store.recent_attempt_for_order(token)
    if not attempt or attempt['provider'] != 'DEMO' or attempt['id'] != attempt_id:
        raise HTTPException(409, 'This demo payment link is no longer active')
    if attempt['status'] not in ('PENDING', 'PAID'):
        raise HTTPException(409, 'This payment attempt cannot be confirmed')
    return order, attempt


def demo_bank_html(order: dict, attempt: dict, *, completed: bool = False) -> str:
    # Separate mock bank UI with explicit approval.
    member = html.escape(order['member_name'], quote=True)
    invoice = f'FF-{order["id"]:05d}'
    money = f'{order["amount"]:,}'
    token = html.escape(order['token'], quote=True)
    action = f'/demo/bank/{token}/confirm?attempt={attempt["id"]}'
    paid = completed or order['status'] == 'PAID'
    status_text = 'Demo transfer confirmed' if paid else 'Review transfer details'
    button = (f'<a href="/?receipt={token}" class="button">View FitFlow receipt</a>' if paid else
              f'<form method="post" action="{action}"><button class="button" type="submit">Confirm demo transfer →</button></form>'
              f'<a href="/?receipt={token}" class="back-to-fitflow">← Back to FitFlow</a>')
    label = ('This is a simulation. No bank account is debited and no money is transferred. '
             'The merchant backend receives a demo event only after you confirm.')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"/>
    <title>Demo Bank · FitFlow Payment</title><style>
    :root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,Arial;color:#111827;background:#edf0f5}}
    *{{box-sizing:border-box}}body{{margin:0}}.phone{{max-width:430px;min-height:100dvh;margin:auto;background:#fafbff;display:flex;flex-direction:column}}
    header{{background:#071832;color:#fff;padding:32px 24px 42px;border-radius:0 0 30px 30px}}
    .tag{{display:inline-block;border:1px solid #86a3c4;color:#dcecff;padding:6px 10px;border-radius:99px;font-size:11px;font-weight:800;letter-spacing:1.5px}}
    .brand{{font-weight:850;letter-spacing:-.6px;font-size:21px;margin:28px 0 24px}}.brand span{{color:#79baf9}}h1{{font-size:28px;letter-spacing:-.8px;line-height:1.1;margin:0 0 10px}}header p{{color:#c0d2e8;margin:0;font-size:13px;line-height:1.6}}
    main{{padding:24px;flex:1}}.card{{background:#fff;border-radius:20px;padding:24px;box-shadow:0 9px 28px #23345d12;border:1px solid #e7eaf2}}
    .recipient{{color:#5d6575;font-size:12px;letter-spacing:.8px;font-weight:750;text-transform:uppercase}}.to{{font-size:21px;font-weight:800;margin:7px 0 22px}}.amount{{font-size:36px;font-weight:850;letter-spacing:-1px}}.currency{{font-size:14px;font-weight:800;color:#6d7480;margin-left:6px}}.row{{display:flex;justify-content:space-between;align-items:start;gap:16px;padding:16px 0;border-bottom:1px solid #eef0f4;font-size:14px}}.row:last-child{{border:0;padding-bottom:0}}.row span{{color:#647084}}.row b{{text-align:right;max-width:64%;overflow-wrap:anywhere}}.explain{{background:#fff4e5;border:1px solid #ffdfad;color:#7c4b08;border-radius:14px;padding:14px 15px;margin:19px 0;font-size:12px;line-height:1.55}}.button{{display:block;width:100%;border:0;border-radius:15px;background:#1662df;padding:18px 12px;text-align:center;font-size:15px;font-weight:800;color:white;text-decoration:none;cursor:pointer}}.sub{{font-size:12px;line-height:1.5;text-align:center;color:#7c8696;padding:18px 6px}}.status{{color:#137b43;font-weight:800;margin:0 0 8px}}.small{{font-size:12px;color:#647084}}.back-to-fitflow{{display:block;text-align:center;color:#53657f;text-decoration:none;font-size:13px;font-weight:700;margin:17px 0 0}}
    @media(min-width:500px){{.phone{{margin:24px auto;min-height:820px;border:7px solid #111722;border-radius:38px;overflow:hidden;box-shadow:0 16px 70px #13203f30}}}}
    </style></head><body><div class="phone"><header><span class="tag">DEMO BANK · NOT A REAL BANK</span><div class="brand">◈ &nbsp; Northstar<span>Bank</span> <small style="font-size:10px;font-weight:500">SIMULATOR</small></div><h1>{status_text}</h1><p>{'The simulated bank event was sent to FitFlow.' if paid else 'Check the recipient, amount and invoice reference before confirming.'}</p></header><main>
    <div class="card">{('<p class="status">✓ Demo payment approved</p>' if paid else '')}<div class="recipient">Paying to</div><div class="to">FitFlow Club · Demo Merchant</div><div class="amount">{money}<span class="currency">VND</span></div>
    <div class="row"><span>Membership holder</span><b>{member}</b></div><div class="row"><span>Invoice</span><b>{invoice}</b></div><div class="row"><span>Transfer reference</span><b>GYM{attempt['order_code']}</b></div><div class="row"><span>Processing</span><b>{'Confirmed in demo ledger' if paid else 'Awaiting your confirmation'}</b></div></div>
    <div class="explain">{label}</div>{button}<div class="sub">FitFlow classroom payment simulation · Test data only</div></main></div></body></html>'''


@app.get('/demo/bank/{token}', response_class=__import__('fastapi.responses', fromlist=['HTMLResponse']).HTMLResponse)
def demo_bank_checkout(token: str, attempt: int):
    from fastapi.responses import HTMLResponse
    order, item = demo_bank_context(token, attempt)
    return HTMLResponse(demo_bank_html(order, item))


@app.post('/demo/bank/{token}/confirm', response_class=__import__('fastapi.responses', fromlist=['HTMLResponse']).HTMLResponse)
def demo_bank_confirm(token: str, attempt: int):
    from fastapi.responses import HTMLResponse
    order, item = demo_bank_context(token, attempt)
    if order['status'] != 'PAID':
        result = store.apply_event(item['order_code'], outcome='PAID', amount=order['amount'],
            source='DEMO_BANK', reference=f'DEMO_BANK_{item["order_code"]}')
        if result not in ('PAID', 'DUPLICATE', 'DUPLICATE_VERIFIED_PAYMENT'):
            raise HTTPException(409, f'Could not confirm demo transfer: {result}')
    return HTMLResponse(demo_bank_html(order_or_404(token), item, completed=True))


@app.get('/demo/receipt/{token}')
def scan_demo_receipt(token: str):
    order = order_or_404(token)
    from fastapi.responses import HTMLResponse
    name = order['member_name'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    return HTMLResponse(f'''<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>Demo QR</title>
    <body style="font:16px system-ui;max-width:540px;margin:60px auto;padding:20px">
    <h1>Demo QR scanned</h1><p>Member: <b>{name}</b></p>
    <p>This scannable QR opens a classroom demo page. <b>It is not a bank transfer request.</b></p>
    <p>Return to the FitFlow demo and open <b>Presenter controls → Simulate paid</b> to trigger a test event on the backend.</p>
    </body></html>''')

@app.get('/')
def index():
    return FileResponse(FRONTEND / 'index.html')

# Same-origin static frontend. No CORS wildcard.
app.mount('/assets', StaticFiles(directory=FRONTEND), name='assets')
