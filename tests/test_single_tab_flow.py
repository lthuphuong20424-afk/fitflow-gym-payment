"""Guard against browser-tab regressions in the classroom payment journey.

These are static front-end navigation assertions plus API endpoint checks;
not a browser E2E test.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / 'frontend/js/app.js').read_text(encoding='utf-8')
INDEX = (ROOT / 'frontend/index.html').read_text(encoding='utf-8')
MOMO_HTML = (ROOT / 'frontend/momo_simulator.html').read_text(encoding='utf-8')


def test_no_new_tab_window_open_or_blank_targets():
    assert 'window.open(' not in APP_JS
    assert 'target="_blank"' not in APP_JS
    assert 'target="_blank"' not in MOMO_HTML


def test_momo_checkout_replaces_current_tab_with_provider_screen():
    assert 'window.location.assign(r.checkout_url)' in APP_JS
    assert 'await momoCharge()' in APP_JS
    assert '/momo/charge' in APP_JS
    assert 'Open MoMo payment' in APP_JS


def test_vietqr_checkout_remains_in_fitflow_and_uses_verified_backend_state():
    assert 'Continue to Demo Bank' not in APP_JS
    assert 'Awaiting payment confirmation' in APP_JS
    assert 'Simulate bank / payOS callback' in APP_JS
    assert 'window.location.assign(r.checkout_url)' in APP_JS  # MoMo only
    assert '/api/orders/${encodeURIComponent(state.token)}' in APP_JS
    assert 'target="_blank"' not in APP_JS


def test_busted_js_cache_for_new_frontend():
    assert '/assets/js/app.js?v=10' in INDEX


def test_option_a_provider_success_only_after_verified_status_and_same_tab_return():
    main=(ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
    simulator_js=(ROOT / 'frontend/js/momo_simulator.js').read_text(encoding='utf-8')
    assert "if(success && !isAuth)" in simulator_js
    assert "el('success-screen').hidden=false" in simulator_js
    assert "el('return-button').href=returnUrl" in simulator_js
    assert "RedirectResponse(" in main
    assert "status_code=303" in main
    assert 'target="_blank"' not in MOMO_HTML
    assert 'window.open(' not in APP_JS
