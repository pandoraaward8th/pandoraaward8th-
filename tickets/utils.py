"""
Pandora E-Ticket System — Utility functions
QR code generation, PDF ticket generation, IP helper
"""

import io
import os
import urllib.request
import qrcode
from django.conf import settings

SITE_URL = 'https://pandoraaward8th.onrender.com'

# ── Ticket physical dimensions ───────────────────────────────────────────────
# Full ticket : 8.0 × 3.0 inches at ~209 DPI  (new poster images are 1670×941 px)
# Stub        : rightmost ~25% of width (separator dashes ~x=1115 on 1670px)
# QR code     : overlaid on 'QR CODE WILL BE GENERATED IN THE APP' area in stub
#
# ReportLab works in points (1 pt = 1/72 inch)
PT  = 1.0            # 1 point
IN  = 72.0           # points per inch

TICKET_W = 8.0 * IN   # 576 pt
TICKET_H = 3.0 * IN   # 216 pt

# Pixel-to-percent conversion for 1670×941 images:
#   x_pct = px / 1670    y_pct_from_bottom = (941 - y_from_top) / 941

# Stub occupies the right 25 % (~2 in) of the ticket
STUB_X_PCT  = 0.755    # stub left edge
STUB_W_PCT  = 0.245    # stub width

# Global QR / name defaults (used only when a config entry omits these keys)
QR_CX_PCT   = 0.858
QR_CY_PCT   = 0.393
QR_W_IN     = 1.177
QR_H_IN     = 0.642
QR_W_PT     = QR_W_IN * IN
QR_H_PT     = QR_H_IN * IN
QR_SIZE_PT  = QR_W_PT  # backward compat

# Global name-strip defaults
NAME_X_PCT  = 0.14
NAME_Y_PCT  = 0.14    # % from BOTTOM


# ---------------------------------------------------------------------------
# IP Address helper
# ---------------------------------------------------------------------------

def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR')


# ---------------------------------------------------------------------------
# QR Code generation
# ---------------------------------------------------------------------------

def generate_qr_image(qr_token: str, size: int = 10) -> bytes:
    """Generate QR PNG encoding the full live verify URL."""
    verify_url = f"{SITE_URL}/verify/qr/{qr_token}/"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=size,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def save_qr_to_file(ticket) -> str:
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    png = generate_qr_image(ticket.qr_token)
    path = f"qrcodes/{ticket.ticket_number}.png"
    try:
        if default_storage.exists(path):
            default_storage.delete(path)
    except Exception:
        pass
    default_storage.save(path, ContentFile(png))
    return path


# ---------------------------------------------------------------------------
# Ticket type → background PNG + name text colour
# ---------------------------------------------------------------------------

TICKET_CONFIG = {
    # ── REGULAR ──────────────────────────────────────────────────────────────
    # Background unchanged (no live_test version produced for this tier)
    'REGULAR': {
        'bg':            'REGULAR (1).PNG',
        'name_color':    '#1a0e00',
        # QR box: 226×185px on 1536×864. Top-left:(1205,432). Centre:(1318,524.5)
        # DPI: 192h × 288v
        'qr_cx_pct':     0.858,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.14,
        'name_y_pct':    0.14,
    },

    # ── VIP ───────────────────────────────────────────────────────────────────
    # VIP.jpeg — 1280×720 px (black/gold)
    # Gold TICKET HOLDER bar - use dark brown text for contrast
    'VIP': {
        'bg':            'VIP.jpeg',
        'name_color':    '#2a1500',
        'qr_cx_pct':     0.870,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.1641,
        'name_y_pct':    0.1528,
    },

    # ── SPECIAL GUEST ────────────────────────────────────────────────────────
    # Dark green/gold ticket, black TICKET HOLDER bar - use gold text
    'SPECIAL GUEST': {
        'bg':            'Pandora Awards SPecial guestTicket Poster.png',
        'name_color':    '#d4a825',
        'qr_cx_pct':     0.870,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.1377,
        'name_y_pct':    0.1286,
    },
    'SPECIAL GUEST SEAT': {
        'bg':            'Pandora Awards SPecial guestTicket Poster.png',
        'name_color':    '#d4a825',
        'qr_cx_pct':     0.870,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.1377,
        'name_y_pct':    0.1286,
    },

    # ── TABLE OF TEN ─────────────────────────────────────────────────────────
    # Maroon/gold ticket, black TICKET HOLDER bar - use gold text
    'TABLE OF TEN': {
        'bg':            'Pandora Awards Table for Ten Ticket.png',
        'name_color':    '#d4a825',
        'qr_cx_pct':     0.870,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.1376,
        'name_y_pct':    0.1286,
    },
    'GOLD TABLE': {
        'bg':            'Pandora Awards Table for Ten Ticket.png',
        'name_color':    '#d4a825',
        'qr_cx_pct':     0.870,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.1376,
        'name_y_pct':    0.1286,
    },

    # ── MEDIA / STAFF (fall back to REGULAR background) ──────────────────────
    'MEDIA': {
        'bg':            'REGULAR (1).PNG',
        'name_color':    '#1a0e00',
        'qr_cx_pct':     0.858,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.14,
        'name_y_pct':    0.14,
    },
    'STAFF': {
        'bg':            'REGULAR (1).PNG',
        'name_color':    '#1a0e00',
        'qr_cx_pct':     0.858,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.14,
        'name_y_pct':    0.14,
    },
}

DEFAULT_CONFIG = TICKET_CONFIG['REGULAR']


# ---------------------------------------------------------------------------
# Photo loader helper
# ---------------------------------------------------------------------------

def _get_photo_reader(photo_field):
    from reportlab.lib.utils import ImageReader
    if not photo_field:
        return None
    try:
        url = photo_field.url
        if url.startswith('http'):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                return ImageReader(io.BytesIO(r.read()))
        else:
            return ImageReader(photo_field.path)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# PDF Ticket generator
#
# Layout (all measurements in ReportLab points, y=0 at bottom-left):
#
#   ┌─────────────────────────────────┬──────────┐
#   │  MAIN PANEL  (75 %)             │  STUB    │
#   │                                 │ (25 %)   │
#   │  [logo] PANDORA AWARDS title    │ [logo]   │
#   │  ticket-type box | price box    │ category │
#   │  date / time / venue row        │          │
#   │  ──────────────────────────     │ [QR BOX] │
#   │  TICKET HOLDER | _blank_        │          │
#   │                                 │ ADMIT    │
#   │  [GUEST NAME overlaid here]     │ 8TH ED.  │
#   └─────────────────────────────────┴──────────┘
# ---------------------------------------------------------------------------

def generate_ticket_pdf(ticket) -> bytes:
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    ttype = ticket.ticket_type.name.upper()
    cfg   = TICKET_CONFIG.get(ttype, DEFAULT_CONFIG)

    bg_path    = os.path.join(settings.BASE_DIR, 'static', 'img', cfg['bg'])
    name_color = colors.HexColor(cfg['name_color'])

    # Per-ticket QR box settings
    qr_cx_pct = cfg.get('qr_cx_pct', QR_CX_PCT)
    qr_cy_pct = cfg.get('qr_cy_pct', QR_CY_PCT)
    qr_w_pt   = cfg.get('qr_w_in', 1.177) * IN
    qr_h_pt   = cfg.get('qr_h_in', 0.642) * IN

    # Per-ticket name strip position (falls back to global defaults)
    name_x_pct = cfg.get('name_x_pct', NAME_X_PCT)
    name_y_pct = cfg.get('name_y_pct', NAME_Y_PCT)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(TICKET_W, TICKET_H))

    # ── 1. Full-page background image ────────────────────────────────────
    # Use mask='auto' only for PNG (supports alpha); JPEGs have no alpha channel
    # and mask='auto' causes ReportLab to render them blank.
    if os.path.exists(bg_path):
        is_png = bg_path.lower().endswith('.png')
        c.drawImage(
            ImageReader(bg_path),
            0, 0, TICKET_W, TICKET_H,
            preserveAspectRatio=False,
            mask='auto' if is_png else None,
        )
    else:
        # Fallback plain bg
        c.setFillColor(colors.HexColor('#f5f0e8'))
        c.rect(0, 0, TICKET_W, TICKET_H, fill=1, stroke=0)

    # ── 2. Guest name overlay — intentionally blank (plain ticket mode)
    # Name is not printed on the ticket. The TICKET HOLDER strip on the
    # background image is left empty. Personal info is stored in the system
    # and verified via QR code at the gate.

    # ── 3. QR code overlay (stub QR placeholder box) ────────────────────
    # The gold-bordered empty box on the stub.
    # Centre: x ≈ 87.5 % of ticket width, y ≈ 50 % of ticket height.
    qr_cx = TICKET_W * qr_cx_pct
    qr_cy = TICKET_H * qr_cy_pct
    qr_x  = qr_cx - qr_w_pt / 2
    qr_y  = qr_cy - qr_h_pt / 2

    qr_bytes = generate_qr_image(ticket.qr_token, size=10)
    c.drawImage(
        ImageReader(io.BytesIO(qr_bytes)),
        qr_x, qr_y,
        qr_w_pt, qr_h_pt,
    )

    c.save()
    return buf.getvalue()


def _draw_photo_placeholder(c, x, y, w, h):
    from reportlab.lib import colors as _c
    c.setFillColor(_c.HexColor('#eeeeee'))
    c.rect(x, y, w, h, fill=1, stroke=0)
