"""Backend regression tests. No real bank/PSP requests are made."""
import sys, os, hashlib, hmac
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['PAYMENT_MODE'] = 'demo'
from app import store, main, config, payos

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'db.sqlite3')
    monkeypatch.setattr(store, 'DB_PATH', tmp_path / 'db.sqlite3')
    monkeypatch.setattr(config, 'MODE', 'demo')
    with TestClient(main.app) as c:
        yield c

def authorize_momo_demo(client, token):
    from urllib.parse import urlsplit,parse_qs
    response=client.post(f'/api/demo/orders/{token}/momo/start')
    assert response.status_code==200,response.text
    link=response.json()['authorization_url']
    assert '/demo/momo/' in link
    assert client.get(link).status_code==200
    query=parse_qs(urlsplit(link).query)
    auth=query['auth'][0]
    decision=client.post(f'/demo/momo/{token}/decision?auth={auth}&decision=approve')
    assert decision.status_code==200,decision.text
    return client.get(f'/api/orders/{token}').json()


def new_order(client, months=1):
    r=client.post('/api/orders',json={'member_name':'Nguyen Minh Anh','months':months})
    assert r.status_code==201,r.text
    return r.json()

def test_demo_vietqr_status_and_backend_persistence(client):
    order=new_order(client)
    token=order['token']
    receipt=client.post(f'/api/orders/{token}/payment-link').json()
    assert receipt['status']=='PENDING'
    assert len(receipt['attempts'])==1
    assert receipt['attempts'][0]['has_qr'] is True
    assert receipt['attempts'][0]['provider']=='DEMO'
    assert client.get(f'/api/orders/{token}/qr.png').content[:8]==b'\x89PNG\r\n\x1a\n'
    assert client.get(f'/api/orders/{token}').json()['status']=='PENDING'
    result=client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PAID'}).json()
    assert result['result']=='PAID'
    original_end=result['order']['membership_until']
    assert original_end
    duplicate=client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PAID'}).json()
    assert duplicate['result']=='DUPLICATE'
    assert duplicate['order']['membership_until']==original_end
    assert duplicate['order']['has_exception']==0
    assert client.post(f'/api/orders/{token}/payment-link').status_code==409


def test_momo_failed_then_vietqr_fallback(client):
    o=new_order(client);token=o['token']
    enrolled=authorize_momo_demo(client,token)
    assert enrolled['subscription']['status']=='ACTIVE_DEMO'
    fail=client.post(f'/api/demo/orders/{token}/momo/collect',json={'outcome':'FAILED'}).json()
    assert fail['order']['status']=='UNPAID'
    assert fail['order']['subscription']['status']=='ACTIVE_DEMO'
    pending=client.post(f'/api/orders/{token}/payment-link').json()
    assert len(pending['attempts'])==2
    assert pending['attempts'][0]['provider']=='DEMO'
    assert pending['attempts'][1]['provider']=='MOMO_DEMO'
    assert pending['attempts'][1]['status']=='FAILED'
    assert client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PAID'}).json()['order']['status']=='PAID'
    cancel=client.post(f'/api/demo/orders/{token}/momo/cancel').json()
    assert cancel['subscription']['status']=='CANCELLED_DEMO'
    assert cancel['status']=='PAID'
    assert cancel['has_exception']==0


def test_pending_does_not_allow_second_attempt(client):
    o=new_order(client); token=o['token']
    a=client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    b=client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    assert a['id']==b['id']
    assert len(client.get(f'/api/orders/{token}').json()['attempts'])==1


def test_unauthorized_live_demo_controls_blocked(client,monkeypatch):
    o=new_order(client)
    monkeypatch.setattr(config,'MODE','live')
    r=client.post(f'/api/demo/orders/{o["token"]}/outcome',json={'outcome':'PAID'})
    assert r.status_code==404


def test_amount_mismatch_and_duplicate_bank_events(client):
    o=new_order(client)
    a=client.post(f'/api/orders/{o["token"]}/payment-link').json()['attempts'][0]
    bad=store.apply_event(a['order_code'],outcome='PAID',amount=1,source='PAYOS',reference='BADREF')
    assert bad=='AMOUNT_MISMATCH'
    assert client.get(f'/api/orders/{o["token"]}').json()['status']=='PENDING'
    good=store.apply_event(a['order_code'],outcome='PAID',amount=o['amount'],source='PAYOS',reference='GOODREF')
    assert good=='PAID'
    assert store.apply_event(a['order_code'],outcome='PAID',amount=o['amount'],source='PAYOS',reference='GOODREF')=='DUPLICATE'
    assert store.apply_event(a['order_code'],outcome='PAID',amount=o['amount'],source='PAYOS',reference='DIFFERENT_REF')=='DUPLICATE_VERIFIED_PAYMENT'
    assert client.get(f'/api/orders/{o["token"]}').json()['has_exception']==1  # signed mismatch was retained for reconciliation


def test_live_payos_signed_webhook_path(client,monkeypatch):
    monkeypatch.setattr(config,'MODE','live')
    monkeypatch.setattr(payos,'CHECKSUM_KEY','test-checksum-value')
    monkeypatch.setattr(payos,'create_payment_link',lambda order,att: {
      'orderCode':att['order_code'],'amount':order['amount'],'status':'PENDING',
      'paymentLinkId':'link-verified','qrCode':'0002010102121234',
      'checkoutUrl':'https://pay.payos.vn/web/link-verified','accountNumber':'001122','bin':'970422',
      'accountName':'TEST GYM', 'description':'GYM1'})
    o=new_order(client);token=o['token']
    order=client.post(f'/api/orders/{token}/payment-link').json()
    attempt=order['attempts'][0]
    assert attempt['provider']=='PAYOS' and attempt['has_qr']
    data={'orderCode':attempt['order_code'],'amount':o['amount'],'description':'GYM1',
          'accountNumber':'001122','reference':'BANK-REFERENCE-123',
          'transactionDateTime':'2026-11-19 21:20:10','currency':'VND','paymentLinkId':'link-verified',
          'code':'00','desc':'Thành công'}
    signature=payos.hmac_sha256('&'.join(f'{k}={data[k]}' for k in sorted(data)))
    body={'code':'00','desc':'success','success':True,'data':data,'signature':signature}
    forged={**body,'signature':'x'*64}
    assert client.post('/api/webhooks/payos',json=forged).status_code==400
    assert client.get(f'/api/orders/{token}').json()['status']=='PENDING'
    accepted=client.post('/api/webhooks/payos',json=body)
    assert accepted.status_code==200 and accepted.json()['result']=='PAID'
    repeated=client.post('/api/webhooks/payos',json=body)
    assert repeated.status_code==200 and repeated.json()['result']=='DUPLICATE'
    check=client.get(f'/api/orders/{token}').json()
    assert check['status']=='PAID' and check['has_exception']==0


def test_month_end_clamp():
    assert store.add_months('2027-01-31T00:00:00+00:00',1).startswith('2027-02-28')
    assert store.add_months('2028-01-31T00:00:00+00:00',1).startswith('2028-02-29')


def test_demo_qr_failed_then_new_attempt_keeps_history(client):
    order=new_order(client);token=order['token']
    a=client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    failed=client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'FAILED'}).json()['order']
    assert failed['status']=='UNPAID'
    next_attempt=client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    assert next_attempt['id']!=a['id']
    all_attempts=client.get(f'/api/orders/{token}').json()['attempts']
    assert len(all_attempts)==2 and all_attempts[1]['status']=='FAILED'
    assert client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PAID'}).json()['order']['status']=='PAID'


def test_momo_authorization_does_not_activate_membership(client):
    order=new_order(client);token=order['token']
    enrolled=authorize_momo_demo(client,token)
    assert enrolled['subscription']['status']=='ACTIVE_DEMO'
    assert enrolled['status']=='UNPAID'
    assert enrolled['membership_until'] is None
    assert enrolled['paid_at'] is None


def test_demo_vietqr_qr_is_reference_only_and_backend_event_is_idempotent(client):
    """Demo QR encodes sample invoice details, never impersonates a real bank transfer."""
    o = new_order(client)
    token = o['token']
    response = client.post(f'/api/orders/{token}/payment-link')
    assert response.status_code == 200
    attempt = response.json()['attempts'][0]
    assert attempt['checkout_url'] is None  # No mandatory Demo Bank web page
    assert attempt['provider'] == 'DEMO'
    assert attempt['description'] == f'FF{o["id"]:05d}'
    saved_attempt = store.recent_attempt_for_order(token)
    assert 'CLASSROOM DEMO - NOT A BANK TRANSFER' in saved_attempt['qr_payload']
    assert f'Invoice: FF-{o["id"]:05d}' in saved_attempt['qr_payload']
    assert f'Amount: {o["amount"]} VND' in saved_attempt['qr_payload']
    qr = client.get(f'/api/orders/{token}/qr.png?attempt={attempt["id"]}')
    assert qr.status_code == 200 and qr.headers['content-type'] == 'image/png'
    assert qr.content[:8] == b'\x89PNG\r\n\x1a\n'
    assert client.get(f'/api/orders/{token}').json()['status'] == 'PENDING'
    confirmed = client.post(f'/api/demo/orders/{token}/outcome', json={'outcome':'PAID'}).json()
    assert confirmed['result'] == 'PAID'
    paid = confirmed['order']
    assert paid['status'] == 'PAID' and paid['membership_until']
    duplicate = client.post(f'/api/demo/orders/{token}/outcome', json={'outcome':'PAID'}).json()
    assert duplicate['result'] == 'DUPLICATE'
    assert duplicate['order']['membership_until'] == paid['membership_until']


def test_replaced_demo_qr_id_returns_gone_without_affecting_new_invoice(client):
    o = new_order(client)
    token = o['token']
    first = client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'FAILED'})
    second = client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    assert first['id'] != second['id']
    assert client.get(f'/api/orders/{token}/qr.png?attempt={first["id"]}').status_code == 410
    assert client.get(f'/api/orders/{token}/qr.png?attempt={second["id"]}').status_code == 200
    assert client.get(f'/api/orders/{token}').json()['status'] == 'PENDING'

def test_demo_bank_disabled_in_live(client, monkeypatch):
    o = new_order(client); token=o['token']
    a = client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    monkeypatch.setattr(config, 'MODE', 'live')
    assert client.get(f'/demo/bank/{token}?attempt={a["id"]}').status_code == 404
    assert client.post(f'/demo/bank/{token}/confirm?attempt={a["id"]}').status_code == 404


def test_momo_wallet_connection_needs_explicit_approval_and_payment_is_separate(client):
    from urllib.parse import urlsplit,parse_qs
    order=new_order(client);token=order['token']
    first=client.post(f'/api/demo/orders/{token}/momo/start')
    assert first.status_code==200
    link=first.json()['authorization_url']
    awaiting=client.get(f'/api/orders/{token}').json()
    assert awaiting['subscription']['status']=='PENDING_DEMO'
    assert awaiting['subscription']['consent_at']==''
    assert awaiting['status']=='UNPAID' and awaiting['membership_until'] is None
    assert 'auth_digest' not in awaiting['subscription']
    page=client.get(link)
    assert page.status_code==200
    assert 'CLASSROOM SIMULATOR' in page.text and 'not operated by MoMo' in page.text
    assert 'name="wallet_suffix"' in page.text
    assert 'type="password"' not in page.text
    assert 'name="otp"' not in page.text
    assert 'name="cvv"' not in page.text
    bad=client.post(f'/demo/momo/{token}/decision?auth=invalid&decision=approve')
    assert bad.status_code==409
    assert client.get(f'/api/orders/{token}').json()['subscription']['status']=='PENDING_DEMO'
    auth=parse_qs(urlsplit(link).query)['auth'][0]
    yes=client.post(f'/demo/momo/{token}/decision?auth={auth}&decision=approve')
    assert yes.status_code==200
    approved=client.get(f'/api/orders/{token}').json()
    assert approved['subscription']['status']=='ACTIVE_DEMO'
    assert approved['subscription']['auth_reference'].startswith('MOMO-SIM-')
    assert approved['subscription']['consent_at']
    assert approved['status']=='UNPAID' and approved['membership_until'] is None
    # Duplicate approvals never create additional subscriptions.
    assert client.post(f'/demo/momo/{token}/decision?auth={auth}&decision=approve').status_code==200
    assert client.post(f'/api/demo/orders/{token}/momo/start').status_code==409
    assert client.get(f'/api/orders/{token}').json()['status']=='UNPAID'


def test_momo_decline_expired_link_restart_then_approve(client):
    from urllib.parse import urlsplit,parse_qs
    o=new_order(client);token=o['token']
    first=client.post(f'/api/demo/orders/{token}/momo/start').json()['authorization_url']
    auth1=parse_qs(urlsplit(first).query)['auth'][0]
    decline=client.post(f'/demo/momo/{token}/decision?auth={auth1}&decision=decline')
    assert decline.status_code==200
    assert client.get(f'/api/orders/{token}').json()['subscription']['status']=='DECLINED_DEMO'
    assert client.post(f'/api/demo/orders/{token}/momo/charge').status_code==409
    second=client.post(f'/api/demo/orders/{token}/momo/start').json()['authorization_url']
    auth2=parse_qs(urlsplit(second).query)['auth'][0]
    assert auth1!=auth2
    assert client.post(f'/demo/momo/{token}/decision?auth={auth1}&decision=approve').status_code==409
    assert client.post(f'/demo/momo/{token}/decision?auth={auth2}&decision=approve').status_code==200
    assert client.get(f'/api/orders/{token}').json()['subscription']['status']=='ACTIVE_DEMO'


def test_momo_first_payment_simulated_wallet_then_auto_next_cycle(client):
    from urllib.parse import urlsplit,parse_qs
    o=new_order(client);token=o['token']
    authorize_momo_demo(client,token)
    payment=client.post(f'/api/demo/orders/{token}/momo/charge')
    assert payment.status_code==200
    item=payment.json()['order']['attempts'][0]
    assert item['status']=='PENDING' and item['provider']=='MOMO_DEMO'
    assert payment.json()['order']['status']=='PENDING'
    path=urlsplit(payment.json()['checkout_url'])
    attempt=int(parse_qs(path.query)['attempt'][0])
    assert client.get(path.path+'?'+path.query).status_code==200
    assert client.get(f'/api/orders/{token}').json()['membership_until'] is None
    done=client.post(f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=PAID')
    assert done.status_code==200
    initial=client.get(f'/api/orders/{token}').json()
    assert initial['status']=='PAID' and initial['membership_until']
    until=initial['membership_until']
    assert client.post(f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=PAID').status_code==200
    assert client.get(f'/api/orders/{token}').json()['membership_until']==until
    cycle=client.post(f'/api/demo/orders/{token}/momo/next-cycle')
    assert cycle.status_code==200,cycle.text
    nxt=cycle.json()['order'];newtoken=nxt['token']
    assert nxt['renewal_of_id']==initial['id']
    assert nxt['billing_due_at']==until
    assert nxt['subscription']['status']=='ACTIVE_DEMO'
    assert nxt['attempts'][0]['provider']=='MOMO_DEMO' and nxt['attempts'][0]['status']=='PENDING'
    assert len(nxt['attempts'])==1
    # Recurring charge does not require a wallet approval page or second consent.
    assert nxt['attempts'][0]['checkout_url'] is None
    same=client.post(f'/api/demo/orders/{token}/momo/next-cycle').json()['order']
    assert same['token']==newtoken and len(same['attempts'])==1
    charge=client.post(f'/api/demo/orders/{newtoken}/momo/collect',json={'outcome':'PAID'})
    assert charge.status_code==200 and charge.json()['result']=='PAID'
    renewal=charge.json()['order']
    assert renewal['membership_start']==until
    assert renewal['membership_until']!=until
    # Repeating a provider result cannot renew twice.
    repeated=client.post(f'/api/demo/orders/{newtoken}/momo/collect',json={'outcome':'PAID'})
    assert repeated.status_code==409  # paid invoice blocks a new collection
    assert client.get(f'/api/orders/{newtoken}').json()['membership_until']==renewal['membership_until']
    cancel=client.post(f'/api/demo/orders/{newtoken}/momo/cancel')
    assert cancel.status_code==200 and cancel.json()['subscription']['status']=='CANCELLED_DEMO'
    assert client.post(f'/api/demo/orders/{newtoken}/momo/next-cycle').status_code==409
    assert client.get(f'/api/orders/{newtoken}').json()['status']=='PAID'


def test_momo_separate_initial_payment_failed_fallback_and_cancel(client):
    from urllib.parse import urlsplit,parse_qs
    o=new_order(client);token=o['token']
    authorize_momo_demo(client,token)
    pay=client.post(f'/api/demo/orders/{token}/momo/charge').json()
    attempt=int(parse_qs(urlsplit(pay['checkout_url']).query)['attempt'][0])
    failed=client.post(f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=FAILED')
    assert failed.status_code==200
    check=client.get(f'/api/orders/{token}').json()
    assert check['status']=='UNPAID' and check['subscription']['status']=='ACTIVE_DEMO'
    qr=client.post(f'/api/orders/{token}/payment-link').json()
    assert qr['attempts'][0]['provider']=='DEMO' and qr['attempts'][1]['status']=='FAILED'
    assert client.post(f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=PAID').status_code==409
    client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PAID'})
    assert client.get(f'/api/orders/{token}').json()['status']=='PAID'
    client.post(f'/api/demo/orders/{token}/momo/cancel')
    assert client.post(f'/api/demo/orders/{token}/momo/next-cycle').status_code==409


def test_momo_simulator_is_disabled_in_live_mode(client,monkeypatch):
    o=new_order(client);token=o['token']
    monkeypatch.setattr(config,'MODE','live')
    assert client.post(f'/api/demo/orders/{token}/momo/start').status_code==404
    assert client.get(f'/demo/momo/{token}?auth=foo').status_code==404
    assert client.post(f'/api/demo/orders/{token}/momo/charge').status_code==404
    assert client.post(f'/api/demo/orders/{token}/momo/next-cycle').status_code==404


def test_momo_demo_wallet_reference_entry_is_illustrative_and_must_match(client):
    order=new_order(client)
    token=order['token']
    from urllib.parse import urlsplit, parse_qs
    link=client.post(f'/api/demo/orders/{token}/momo/start').json()['authorization_url']
    auth=parse_qs(urlsplit(link).query)['auth'][0]
    path=f'/demo/momo/{token}/decision?auth={auth}&decision=approve'
    invalid=client.post(path,data={'wallet_suffix':'1234'})
    assert invalid.status_code==422
    assert client.get(f'/api/orders/{token}').json()['subscription']['status']=='PENDING_DEMO'
    valid=client.post(path,data={'wallet_suffix':'8842'})
    assert valid.status_code==200
    updated=client.get(f'/api/orders/{token}').json()
    assert updated['subscription']['status']=='ACTIVE_DEMO'
    assert updated['status']=='UNPAID'


def test_both_momo_simulator_steps_share_polished_mobile_checkout(client):
    from urllib.parse import urlsplit, parse_qs
    order = new_order(client)
    token = order['token']
    auth_link = client.post(f'/api/demo/orders/{token}/momo/start').json()['authorization_url']
    first = client.get(auth_link)
    assert first.status_code == 200
    assert 'momo_simulator.css?v=9' in first.text
    assert 'momo_simulator.js?v=9' in first.text
    assert '"kind": "authorization"' in first.text
    assert 'CLASSROOM SIMULATOR' in first.text
    assert 'not operated by MoMo' in first.text
    assert 'name="wallet_suffix"' in first.text
    assert 'type="password"' not in first.text
    auth = parse_qs(urlsplit(auth_link).query)['auth'][0]
    assert client.post(f'/demo/momo/{token}/decision?auth={auth}&decision=approve', data={'wallet_suffix':'8842'}).status_code == 200
    payment_link = client.post(f'/api/demo/orders/{token}/momo/charge').json()['checkout_url']
    second = client.get(payment_link)
    assert second.status_code == 200
    assert 'momo_simulator.css?v=9' in second.text
    assert '"kind": "payment"' in second.text
    assert 'source-description' in second.text
    assert 'Tổng tiền' in second.text
    assert 'FitFlow Club' in second.text or 'FITFLOW CLUB' in second.text


def test_demo_momo_payment_source_is_whitelisted_and_not_real_bank_debit(client):
    from urllib.parse import urlsplit, parse_qs
    o = new_order(client)
    tok = o['token']
    authorize_momo_demo(client, tok)
    link = client.post(f'/api/demo/orders/{tok}/momo/charge').json()['checkout_url']
    attempt = int(parse_qs(urlsplit(link).query)['attempt'][0])
    path = f'/demo/momo/{tok}/payment/decision?attempt={attempt}&outcome=PAID'
    invalid = client.post(path, data={'payment_source':'made_up_payment_source'})
    assert invalid.status_code == 422
    assert client.get(f'/api/orders/{tok}').json()['status'] == 'PENDING'
    valid = client.post(path, data={'payment_source':'vcb_demo'})
    assert valid.status_code == 200
    assert client.get(f'/api/orders/{tok}').json()['status'] == 'PAID'


def test_prelinked_momo_checkout_confirm_success_and_idempotency(client):
    """New v5/v6 flow: no wallet authorization step, payment then success."""
    order = new_order(client)
    token = order['token']
    assert order['subscription'] is None
    response = client.post(f'/api/demo/orders/{token}/momo/charge')
    assert response.status_code == 200, response.text
    link = response.json()['checkout_url']
    pending = client.get(f'/api/orders/{token}').json()
    assert pending['subscription']['status'] == 'ACTIVE_DEMO'
    assert pending['status'] == 'PENDING'
    page = client.get(link)
    assert page.status_code == 200 and 'name="payment_source"' in page.text
    assert 'id="success-screen"' in page.text
    from urllib.parse import urlparse, parse_qs
    attempt = int(parse_qs(urlparse(link).query)['attempt'][0])
    decision = f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=PAID'
    completed = client.post(decision, data={'payment_source':'momo_wallet'})
    assert completed.status_code == 200, completed.text
    assert '"status": "PAID"' in completed.text
    settled = client.get(f'/api/orders/{token}').json()
    assert settled['status'] == 'PAID' and settled['membership_until']
    again = client.post(decision, data={'payment_source':'momo_wallet'})
    assert again.status_code == 200
    assert client.get(f'/api/orders/{token}').json()['membership_until'] == settled['membership_until']

def test_prelinked_momo_decline_maintains_unpaid_invoice(client):
    order = new_order(client)
    token = order['token']
    payment_link = client.post(f'/api/demo/orders/{token}/momo/charge').json()['checkout_url']
    from urllib.parse import urlparse, parse_qs
    attempt = int(parse_qs(urlparse(payment_link).query)['attempt'][0])
    response = client.post(f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=FAILED',
                           data={'payment_source':'momo_wallet'})
    assert response.status_code == 200
    after = client.get(f'/api/orders/{token}').json()
    assert after['status'] != 'PAID'
    assert after['attempts'][0]['status'] == 'FAILED'
    assert after['subscription']['status'] == 'ACTIVE_DEMO'

def test_momo_checkout_template_disables_hidden_authorization_fields():
    """The original v5 Confirm button was blocked by hidden required inputs."""
    script=(ROOT / 'frontend' / 'js' / 'momo_simulator.js').read_text(encoding='utf-8')
    assert "field.disabled=!(isAuth&&pending)" in script
    assert "field.required=isAuth&&pending" in script


def test_option_a_momo_success_is_distinct_get_view_and_receipt_return(client):
    from urllib.parse import urlsplit, parse_qs
    order = new_order(client)
    token = order['token']
    link = client.post(f'/api/demo/orders/{token}/momo/charge').json()['checkout_url']
    assert client.get(link).status_code == 200
    assert client.get(f'/api/orders/{token}').json()['status'] == 'PENDING'
    attempt_id = int(parse_qs(urlsplit(link).query)['attempt'][0])
    confirm = f'/demo/momo/{token}/payment/decision?attempt={attempt_id}&outcome=PAID'

    response = client.post(confirm, data={'payment_source': 'momo_wallet'}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == link

    success = client.get(response.headers['location'])
    assert success.status_code == 200
    assert 'id="success-screen"' in success.text
    assert 'Return to FitFlow' in success.text
    assert '"status": "PAID"' in success.text
    assert '"transaction_reference": "MOMO_SIM_' in success.text
    assert f'"return_url": "/?receipt={token}"' in success.text

    paid = client.get(f'/api/orders/{token}').json()
    assert paid['status'] == 'PAID'
    assert paid['membership_until']
    assert len(paid['attempts']) == 1
    assert paid['attempts'][0]['status'] == 'PAID'
    old_expiry = paid['membership_until']

    # Refreshing the GET result must not change the payment or membership.
    assert client.get(link).status_code == 200
    repeated = client.post(confirm, data={'payment_source': 'momo_wallet'}, follow_redirects=False)
    assert repeated.status_code == 303
    assert client.get(f'/api/orders/{token}').json()['membership_until'] == old_expiry
    assert len(client.get(f'/api/orders/{token}').json()['attempts']) == 1

    merchant = client.get(f'/?receipt={token}')
    assert merchant.status_code == 200
    assert 'FitFlow' in merchant.text
    app_script = (ROOT / 'frontend/js/app.js').read_text(encoding='utf-8')
    assert 'renderReceipt()' in app_script
    assert "state.order?.status==='PAID'" in app_script


def test_option_a_momo_failed_is_not_success(client):
    from urllib.parse import urlsplit, parse_qs
    order=new_order(client)
    token=order['token']
    link=client.post(f'/api/demo/orders/{token}/momo/charge').json()['checkout_url']
    attempt=int(parse_qs(urlsplit(link).query)['attempt'][0])
    response=client.post(f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=FAILED',
                         data={'payment_source': 'momo_wallet'}, follow_redirects=False)
    assert response.status_code == 303
    after=client.get(response.headers['location'])
    assert '"status": "FAILED"' in after.text
    assert client.get(f'/api/orders/{token}').json()['status'] != 'PAID'
    assert client.get(f'/api/orders/{token}').json()['membership_until'] is None
