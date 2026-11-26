"""SQLite storage and idempotent payment state transitions."""
import sqlite3
import secrets
from datetime import datetime, timezone
from calendar import monthrange
from pathlib import Path
from .config import DB_PATH


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def add_months(iso_date: str, months: int) -> str:
    """Clamp 29/30/31 rather than rolling to next month."""
    d = datetime.fromisoformat(iso_date)
    target_month = (d.month - 1 + months) % 12 + 1
    target_year = d.year + (d.month - 1 + months) // 12
    return d.replace(year=target_year, month=target_month, day=min(d.day, monthrange(target_year, target_month)[1])).isoformat(timespec='seconds')


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def init_db():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS orders (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          token TEXT NOT NULL UNIQUE,
          member_name TEXT NOT NULL,
          months INTEGER NOT NULL,
          amount INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'UNPAID',
          has_exception INTEGER NOT NULL DEFAULT 0,
          paid_at TEXT,
          membership_start TEXT,
          membership_until TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attempts (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_id INTEGER NOT NULL REFERENCES orders(id),
          provider TEXT NOT NULL,
          order_code INTEGER NOT NULL UNIQUE,
          status TEXT NOT NULL DEFAULT 'CREATING',
          payment_link_id TEXT,
          qr_payload TEXT,
          checkout_url TEXT,
          bank_bin TEXT,
          account_number TEXT,
          account_name TEXT,
          description TEXT,
          reference TEXT,
          created_at TEXT NOT NULL,
          last_checked_at TEXT,
          confirmed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          attempt_id INTEGER NOT NULL REFERENCES attempts(id),
          source TEXT NOT NULL,
          event_key TEXT NOT NULL UNIQUE,
          outcome TEXT NOT NULL,
          amount INTEGER,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          order_id INTEGER NOT NULL UNIQUE REFERENCES orders(id),
          status TEXT NOT NULL,
          consent_at TEXT NOT NULL,
          cancelled_at TEXT
        );
        CREATE TABLE IF NOT EXISTS payment_anomalies (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          attempt_id INTEGER NOT NULL REFERENCES attempts(id),
          event_key TEXT NOT NULL UNIQUE,
          reason TEXT NOT NULL,
          amount INTEGER,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_attempts_order ON attempts(order_id);
        ''')
        # Backward-compatible upgrade for an existing SQLite demo database.
        columns={r['name'] for r in db.execute('PRAGMA table_info(subscriptions)')}
        for name, kind in {
            'auth_digest':'TEXT', 'auth_expires_at':'TEXT', 'auth_requested_at':'TEXT',
            'auth_reference':'TEXT', 'declined_at':'TEXT', 'terms_amount':'INTEGER',
            'terms_frequency':'TEXT'
        }.items():
            if name not in columns:
                db.execute(f'ALTER TABLE subscriptions ADD COLUMN {name} {kind}')
        order_columns={r['name'] for r in db.execute('PRAGMA table_info(orders)')}
        for name,kind in {'subscription_id':'INTEGER','renewal_of_id':'INTEGER','billing_due_at':'TEXT'}.items():
            if name not in order_columns:db.execute(f'ALTER TABLE orders ADD COLUMN {name} {kind}')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_renewal_parent ON orders(renewal_of_id)')


def rowdict(row):
    return dict(row) if row is not None else None


def find_order(db, token):
    return db.execute('SELECT * FROM orders WHERE token=?', (token,)).fetchone()


def create_order(member_name, months, amount):
    token = secrets.token_urlsafe(24)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO orders (token, member_name, months, amount, created_at) VALUES (?,?,?,?,?)',
                   (token, member_name, months, amount, utcnow()))
        db.commit()
    return token


def present_order(token):
    with connect() as db:
        order = find_order(db, token)
        if not order:
            return None
        attempts = db.execute('SELECT * FROM attempts WHERE order_id=? ORDER BY id DESC', (order['id'],)).fetchall()
        safe_attempts = [{key: a[key] for key in (
            'id', 'provider', 'order_code', 'status', 'checkout_url', 'bank_bin',
            'account_number', 'account_name', 'description', 'reference',
            'created_at', 'confirmed_at') } | {'has_qr':bool(a['qr_payload'])} for a in attempts]
        subscription_filter = 'id=?' if order['subscription_id'] else 'order_id=?'
        subscription_key = order['subscription_id'] or order['id']
        subscription = db.execute(f'''SELECT status,consent_at,cancelled_at,auth_requested_at,auth_expires_at,
                  auth_reference,declined_at,terms_amount,terms_frequency FROM subscriptions WHERE {subscription_filter}''',
                  (subscription_key,)).fetchone()
        return {**dict(order), 'attempts': safe_attempts, 'subscription': rowdict(subscription)}


def new_attempt(token, provider):
    """Only one nonterminal attempt per invoice. Do not retry UNKNOWN payments."""
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        order = find_order(db, token)
        if not order:
            db.rollback(); raise ValueError('NOT_FOUND')
        if order['status'] == 'PAID':
            db.rollback(); raise ValueError('ALREADY_PAID')
        old = db.execute('SELECT * FROM attempts WHERE order_id=? ORDER BY id DESC LIMIT 1', (order['id'],)).fetchone()
        if old and old['status'] in ('CREATING', 'PENDING', 'UNKNOWN', 'PAID'):
            db.commit()
            return rowdict(old), False
        # PayOS orderCode is unique integer; suitable for JS safe integer.
        import time
        for _ in range(5):
            code = int(time.time() * 1000) * 100 + secrets.randbelow(100)
            try:
                cur = db.execute('INSERT INTO attempts (order_id, provider, order_code, created_at) VALUES (?,?,?,?)',
                                 (order['id'], provider, code, utcnow()))
                db.execute("UPDATE orders SET status='PENDING' WHERE id=?", (order['id'],))
                db.commit()
                return rowdict(db.execute('SELECT * FROM attempts WHERE id=?', (cur.lastrowid,)).fetchone()), True
            except sqlite3.IntegrityError:
                continue
        db.rollback(); raise RuntimeError('Cannot allocate unique payment identifier')


def update_attempt(attempt_id, *, status, qr_payload=None, checkout_url=None, payment_link_id=None,
                   bank_bin=None, account_number=None, account_name=None, description=None):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT status FROM attempts WHERE id=?', (attempt_id,)).fetchone()
        if not existing or existing['status'] in ('PAID', 'FAILED', 'CANCELLED'):
            db.rollback(); return False
        db.execute('''UPDATE attempts SET status=?, qr_payload=?, checkout_url=?, payment_link_id=?,
                   bank_bin=?, account_number=?, account_name=?, description=? WHERE id=?''',
                   (status, qr_payload, checkout_url, payment_link_id, bank_bin, account_number,
                    account_name, description, attempt_id))
        db.commit()
        return True


def mark_checked(attempt_id):
    with connect() as db:
        db.execute('UPDATE attempts SET last_checked_at=? WHERE id=?', (utcnow(), attempt_id))


def find_attempt_by_code(code):
    with connect() as db:
        return rowdict(db.execute('SELECT * FROM attempts WHERE order_code=?', (code,)).fetchone())


def recent_attempt_for_order(token):
    with connect() as db:
        order = find_order(db, token)
        if not order: return None
        return rowdict(db.execute('SELECT * FROM attempts WHERE order_id=? ORDER BY id DESC LIMIT 1', (order['id'],)).fetchone())


def apply_event(order_code, *, outcome, amount, source, reference, payment_link_id=None):
    """Exactly once: unique provider event key; paid order renewed only once.

    A second *real* money receipt is preserved as an exception; never erase it.
    """
    if outcome not in ('PAID', 'FAILED', 'CANCELLED', 'PENDING'):
        raise ValueError('INVALID_OUTCOME')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        attempt = db.execute('SELECT * FROM attempts WHERE order_code=?', (order_code,)).fetchone()
        if not attempt:
            db.rollback(); return 'UNKNOWN_ORDER'
        order = db.execute('SELECT * FROM orders WHERE id=?', (attempt['order_id'],)).fetchone()
        anomaly = None
        if attempt['payment_link_id'] and payment_link_id != attempt['payment_link_id']:
            anomaly = 'LINK_MISMATCH'
        if amount != order['amount'] and outcome == 'PAID':
            anomaly = 'AMOUNT_MISMATCH'
        if anomaly:
            # Signed money movements with mismatches must NOT activate a membership,
            # but must remain visible for finance/reconciliation.
            event_key = f'{source}:{reference}' if reference else f'{source}:{order_code}:{outcome}'
            if db.execute('SELECT 1 FROM payment_anomalies WHERE event_key=?',(event_key,)).fetchone():
                db.rollback();return 'DUPLICATE_ANOMALY'
            db.execute('INSERT INTO payment_anomalies(attempt_id,event_key,reason,amount,created_at) VALUES(?,?,?,?,?)',
                       (attempt['id'],event_key,anomaly,amount,utcnow()))
            db.execute('UPDATE orders SET has_exception=1 WHERE id=?',(order['id'],))
            db.commit();return anomaly
        event_key = f'{source}:{reference}' if reference else f'{source}:{order_code}:{outcome}'
        # A provider's transaction reference must be globally unique across invoices.
        existing_event = db.execute('SELECT * FROM events WHERE event_key=?', (event_key,)).fetchone()
        if existing_event:
            db.rollback(); return 'DUPLICATE'
        db.execute('INSERT INTO events (attempt_id, source, event_key, outcome, amount, created_at) VALUES (?,?,?,?,?,?)',
                   (attempt['id'], source, event_key, outcome, amount, utcnow()))
        if outcome == 'PAID':
            if attempt['status'] == 'PAID':
                db.commit(); return 'DUPLICATE_VERIFIED_PAYMENT'
            db.execute('UPDATE attempts SET status=?, reference=?, confirmed_at=? WHERE id=?',
                       ('PAID', reference, utcnow(), attempt['id']))
            if order['status'] == 'PAID':
                db.execute('UPDATE orders SET has_exception=1 WHERE id=?', (order['id'],))
                db.commit(); return 'EXTRA_PAYMENT'
            moment = utcnow()
            period_start = order['billing_due_at'] or moment
            db.execute('''UPDATE orders SET status='PAID', paid_at=?, membership_start=?,
                        membership_until=? WHERE id=?''', (moment, period_start, add_months(period_start, order['months']), order['id']))
            db.commit(); return 'PAID'
        if attempt['status'] == 'PAID':
            db.commit(); return 'IGNORED_AFTER_PAID'
        # Don't demote paid invoice; preserve attempt failures.
        db.execute('UPDATE attempts SET status=? WHERE id=?', (outcome, attempt['id']))
        if outcome in ('FAILED', 'CANCELLED') and order['status'] != 'PAID':
            db.execute("UPDATE orders SET status='UNPAID' WHERE id=?", (order['id'],))
        db.commit(); return outcome


def _demo_momo_digest(code: str) -> str:
    import hashlib
    return hashlib.sha256(code.encode('utf-8')).hexdigest()




def ensure_demo_momo_subscription(token):
    """Provision a classroom-only linked MoMo wallet for monthly demo flows.

    This bypasses the separate wallet-link step so presenters can demonstrate a
    cleaner payment journey using a pre-linked sample MoMo account. No real
    wallet credentials, PIN, OTP, or account linking is performed.
    """
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        order = find_order(db, token)
        if not order or order['months'] != 1 or order['status'] == 'PAID':
            db.rollback(); raise ValueError('Only an unpaid monthly invoice can use the demo MoMo wallet')
        sub = db.execute('SELECT * FROM subscriptions WHERE order_id=?', (order['id'],)).fetchone()
        now = utcnow()
        if sub and sub['status'] in ('CANCELLED_DEMO','DECLINED_DEMO','PENDING_DEMO'):
            db.rollback(); raise ValueError('An existing wallet authorization was cancelled, declined or remains pending')
        ref = 'MOMO-LINKED-DEMO'
        args = ('ACTIVE_DEMO', now, now, order['amount'], 'MONTHLY', ref)
        if sub:
            db.execute("""UPDATE subscriptions SET status=?, consent_at=?, auth_requested_at=?,
                         terms_amount=?, terms_frequency=?, auth_reference=?,
                         auth_expires_at=NULL, auth_digest=NULL, declined_at=NULL
                         WHERE id=?""", (*args, sub['id']))
        else:
            db.execute("""INSERT INTO subscriptions(order_id,status,consent_at,auth_requested_at,
                         terms_amount,terms_frequency,auth_reference) VALUES (?,?,?,?,?,?,?)""",
                       (order['id'], *args))
        db.commit()
    return present_order(token)

def demo_momo_start(token):
    """Create a consent session for the separate, labelled demo wallet page."""
    from datetime import timedelta
    nonce = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(minutes=10)).isoformat(timespec='seconds')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        order = find_order(db, token)
        if not order or order['months'] != 1 or order['status'] == 'PAID':
            db.rollback(); raise ValueError('Only an unpaid monthly invoice can start MoMo authorization')
        latest = db.execute('SELECT status FROM attempts WHERE order_id=? ORDER BY id DESC LIMIT 1', (order['id'],)).fetchone()
        if latest and latest['status'] in ('CREATING', 'PENDING', 'UNKNOWN', 'PAID'):
            db.rollback(); raise ValueError('Resolve the existing payment attempt before linking MoMo')
        existing = db.execute('SELECT * FROM subscriptions WHERE order_id=?', (order['id'],)).fetchone()
        if existing and existing['status'] == 'ACTIVE_DEMO':
            db.rollback(); raise ValueError('MoMo authorization is already active')
        if existing and existing['status'] == 'CANCELLED_DEMO':
            db.rollback(); raise ValueError('This authorization was cancelled; create a new membership enrollment')
        args = ('PENDING_DEMO','',now.isoformat(timespec='seconds'),expires,_demo_momo_digest(nonce),order['amount'],'MONTHLY')
        if existing:
            db.execute('''UPDATE subscriptions SET status=?,consent_at=?,auth_requested_at=?,auth_expires_at=?,
                 auth_digest=?,terms_amount=?,terms_frequency=?,cancelled_at=NULL,declined_at=NULL,
                 auth_reference=NULL WHERE id=?''',(*args,existing['id']))
        else:
            db.execute('''INSERT INTO subscriptions(order_id,status,consent_at,auth_requested_at,
                 auth_expires_at,auth_digest,terms_amount,terms_frequency)
                 VALUES (?,?,?,?,?,?,?,?)''',(order['id'],*args))
        db.commit()
    return nonce


def demo_momo_session(token, nonce):
    with connect() as db:
        order = find_order(db, token)
        if not order: raise ValueError('Invoice not found')
        sub = db.execute('SELECT * FROM subscriptions WHERE order_id=?',(order['id'],)).fetchone()
        if not sub or not sub['auth_digest'] or not secrets.compare_digest(_demo_momo_digest(nonce),sub['auth_digest']):
            raise ValueError('Invalid demo authorization link')
        if sub['status'] == 'PENDING_DEMO' and datetime.fromisoformat(sub['auth_expires_at']) <= datetime.now(timezone.utc):
            raise ValueError('This demo authorization link expired; restart from FitFlow')
        return {'status':sub['status'],'amount':order['amount'],'member_name':order['member_name'],
                'expires_at':sub['auth_expires_at'],'reference':sub['auth_reference']}


def demo_momo_decide(token, nonce, approved):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        order = find_order(db, token)
        if not order: db.rollback(); raise ValueError('Invoice not found')
        sub = db.execute('SELECT * FROM subscriptions WHERE order_id=?',(order['id'],)).fetchone()
        if not sub or not sub['auth_digest'] or not secrets.compare_digest(_demo_momo_digest(nonce),sub['auth_digest']):
            db.rollback(); raise ValueError('Invalid demo authorization link')
        if sub['status'] != 'PENDING_DEMO':
            db.commit(); return sub['status']
        if datetime.fromisoformat(sub['auth_expires_at']) <= datetime.now(timezone.utc):
            db.rollback(); raise ValueError('Demo authorization link expired')
        now = utcnow()
        if approved:
            ref = 'MOMO-SIM-' + secrets.token_hex(5).upper()
            db.execute('''UPDATE subscriptions SET status='ACTIVE_DEMO',consent_at=?,
                       auth_reference=? WHERE id=?''',(now,ref,sub['id']))
            result = 'ACTIVE_DEMO'
        else:
            db.execute("UPDATE subscriptions SET status='DECLINED_DEMO',declined_at=? WHERE id=?",(now,sub['id']))
            result = 'DECLINED_DEMO'
        db.commit(); return result


def demo_momo_cancel(token):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        order = find_order(db, token)
        if not order:
            db.rollback(); raise ValueError('NOT_FOUND')
        sub = db.execute('SELECT * FROM subscriptions WHERE order_id=? OR id=?',
                         (order['id'], order['subscription_id'] or -1)).fetchone()
        if not sub:
            db.rollback(); raise ValueError('NO_SUBSCRIPTION')
        if sub['status'] == 'CANCELLED_DEMO':
            db.commit(); return present_order(token)
        db.execute('UPDATE subscriptions SET status=?, cancelled_at=? WHERE id=?',
                   ('CANCELLED_DEMO',utcnow(),sub['id']))
        db.commit()
    return present_order(token)


def revive_pending_attempt(attempt_id, payment_link_id, checkout_url):
    with connect() as db:
        db.execute('''UPDATE attempts SET status='PENDING',
          payment_link_id=COALESCE(payment_link_id,?), checkout_url=COALESCE(checkout_url,?)
          WHERE id=? AND status='UNKNOWN' ''', (payment_link_id, checkout_url, attempt_id))

def demo_momo_next_cycle(token):
    """Presenter-only: pretend next bill is due; generate one invoice per previous paid period.

    No actual scheduler, MoMo API, real authorization token or money movement exists.
    """
    new_token = secrets.token_urlsafe(24)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        origin = find_order(db, token)
        if not origin or origin['status'] != 'PAID' or origin['months'] != 1 or not origin['membership_until']:
            db.rollback(); raise ValueError('Pay the current monthly invoice before simulating renewal')
        if origin['subscription_id']:
            sub=db.execute('SELECT * FROM subscriptions WHERE id=?',(origin['subscription_id'],)).fetchone()
        else:
            sub=db.execute('SELECT * FROM subscriptions WHERE order_id=?',(origin['id'],)).fetchone()
        if not sub or sub['status']!='ACTIVE_DEMO':
            db.rollback(); raise ValueError('No active demo authorization for the next billing cycle')
        existing=db.execute('SELECT token FROM orders WHERE renewal_of_id=?',(origin['id'],)).fetchone()
        if existing:
            db.commit();return existing['token']
        db.execute('''INSERT INTO orders(token,member_name,months,amount,created_at,
                     subscription_id,renewal_of_id,billing_due_at) VALUES(?,?,?,?,?,?,?,?)''',
                   (new_token,origin['member_name'],1,sub['terms_amount'] or origin['amount'],utcnow(),
                    sub['id'],origin['id'],origin['membership_until']))
        db.commit()
    return new_token


