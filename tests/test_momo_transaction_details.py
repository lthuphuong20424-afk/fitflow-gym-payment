"""MoMo transaction-details screen regression checks (classroom simulator)."""
import sys,os
from pathlib import Path
from fastapi.testclient import TestClient
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ['PAYMENT_MODE']='demo'
from app import main,store,config

@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DB_PATH',tmp_path/'test-v9.sqlite3')
    monkeypatch.setattr(store,'DB_PATH',tmp_path/'test-v9.sqlite3')
    monkeypatch.setattr(config,'MODE','demo')
    with TestClient(main.app) as c: yield c

def test_momo_transaction_details_support_and_receipt_flow(client):
    order=client.post('/api/orders',json={'member_name':'Pham Ha','months':1}).json()
    token=order['token']
    pending=client.post(f'/api/demo/orders/{token}/momo/charge')
    assert pending.status_code==200
    page=pending.json()['checkout_url']
    initial=client.get(page)
    assert initial.status_code==200
    assert 'Thanh toán an toàn' in initial.text
    assert 'id="success-screen"' in initial.text
    assert 'id="contact-support-button"' in initial.text
    assert 'Liên hệ CSKH' in initial.text
    attempt=order_id=int(page.split('attempt=')[-1])
    clicked=client.post(f'/demo/momo/{token}/payment/decision?attempt={attempt}&outcome=PAID',data={'payment_source':'momo_wallet'},follow_redirects=False)
    assert clicked.status_code==303
    done=client.get(clicked.headers['location'])
    assert done.status_code==200
    assert '"status": "PAID"' in done.text
    assert '"transaction_reference": "MOMO_SIM_' in done.text
    assert f'"return_url": "/?receipt={token}"' in done.text
    persisted=client.get(f'/api/orders/{token}').json()
    assert persisted['status']=='PAID'
    assert persisted['membership_until']
    assert client.get(clicked.headers['location']).status_code==200
    assert client.get(f'/api/orders/{token}').json()['membership_until']==persisted['membership_until']

def test_momo_transaction_details_customer_support_does_not_pretend_real_service():
    html=(ROOT/'frontend/momo_simulator.html').read_text(encoding='utf-8')
    js=(ROOT/'frontend/js/momo_simulator.js').read_text(encoding='utf-8')
    assert 'Chi Tiết Giao Dịch' in js
    assert 'Liên hệ CSKH' in html
    assert 'Yêu cầu hoàn/hủy' not in html
    assert 'id="support-copy"' in html
    assert "el('contact-support-button')" in js
    assert 'chưa có tổng đài' in html.lower()
    assert 'window.open(' not in js
    assert 'target="_blank"' not in html
