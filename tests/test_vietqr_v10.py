"""VietQR v10: classroom QR is not a bank instruction, live payOS remains available."""
from pathlib import Path
import pytest
from test_payments import new_order,client,store,config,main

ROOT=Path(__file__).resolve().parents[1]

def test_demo_cannot_verify_unknown_or_uncreated_qr(client):
    order=new_order(client)
    token=order['token']
    r=client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PAID'})
    assert r.status_code==409
    assert client.get(f'/api/orders/{token}').json()['status']=='UNPAID'


def test_pending_is_not_success_and_retry_requires_failed_status(client):
    order=new_order(client)
    token=order['token']
    attempt=client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    pending=client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PENDING'})
    assert pending.json()['order']['status']=='PENDING'
    repeated=client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    assert repeated['id']==attempt['id']
    failed=client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'FAILED'})
    assert failed.json()['order']['status']=='UNPAID'
    renewed=client.post(f'/api/orders/{token}/payment-link').json()['attempts'][0]
    assert renewed['id']!=attempt['id']
    assert len(client.get(f'/api/orders/{token}').json()['attempts'])==2


def test_frontend_has_no_qr_bank_transition_or_ive_paid_button():
    script=(ROOT/'frontend/js/app.js').read_text(encoding='utf-8')
    assert 'Continue to Demo Bank' not in script
    assert 'data-action="iPaid"' not in script
    assert 'data-copy' in script
    assert 'qr.png?attempt=' in script
    assert 'Send success event' in script
    assert 'status===\'PAID\'' in script


def test_demo_provider_event_is_disabled_in_live_mode(client,monkeypatch):
    order=new_order(client)
    token=order['token']
    client.post(f'/api/orders/{token}/payment-link')
    monkeypatch.setattr(config,'MODE','live')
    result=client.post(f'/api/demo/orders/{token}/outcome',json={'outcome':'PAID'})
    assert result.status_code==404
    assert client.get(f'/api/orders/{token}').json()['status']=='PENDING'
