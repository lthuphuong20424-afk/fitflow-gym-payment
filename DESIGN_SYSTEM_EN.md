# FitFlow Club — STRIDE UI Design System

Design language: premium athletic/editorial, strong condensed italic headings, coral-red accents, charcoal and warm-cream contrast. Avoid generic dashboard icon badges or decorative gradient cards.

## Color tokens

- Coral: `#F24E43`
- Warm cream: `#F7F0E8`
- Charcoal: `#181716`
- Dark raised surface: `#242322`
- Secondary text: `#AAA39E`

## Visual assets

- `media/vietqr.png` and `media/momo.png`: user-supplied brand logo images, used without recoloring.
- `media/athlete.jpg`, `media/weights.jpg`, `media/towel.jpg`: crops of the approved AI concept board, used as decorative photography only.
- `media/appmark.svg`: FitFlow's demo-only F/ app icon.
- Icons: purpose-drawn inline vector glyphs in `js/app.js`, controlled by `SVG`.

## Implementation map

- `frontend/index.html`: realistic device bezel, stage and scrollable app viewport.
- `frontend/css/styles.css`: phone design and responsive layout.
- `frontend/js/app.js`: state-based views for plans, checkout, QR, MoMo consent, receipt and history.
- `backend/`: the original FastAPI business/payment logic, retained except customer-facing error strings and the scanned demo receipt text translated to English.

## Safety boundaries

The DEMO QR is deliberately **not** a bank-transfer QR. It may be scanned only to display a confirmation page explaining that it is a classroom simulation. Presenter controls simulate server-side payment notifications. In LIVE, the app needs configured payOS credentials and verified bank transfer callbacks. MoMo remains demo-only.
