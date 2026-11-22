"""
Pandora E-Ticket System — Utility functions
QR code generation, PDF ticket generation, IP helper
"""

import io
import os
import urllib.request
import qrcode
from PIL import Image, ImageDraw, ImageFont
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
        'bg':            'Pandora Awards SPecial guestTicket Poster  .jpeg',
        'name_color':    '#d4a825',
        'qr_cx_pct':     0.870,
        'qr_cy_pct':     0.393,
        'qr_w_in':       1.177,
        'qr_h_in':       0.642,
        'name_x_pct':    0.1377,
        'name_y_pct':    0.1286,
    },
    'SPECIAL GUEST SEAT': {
        'bg':            'Pandora Awards SPecial guestTicket Poster  .jpeg',
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
    """
    Generate a ticket image using Pillow + Impact font (matches bulk PNG design).
    Returns PNG bytes wrapped in a minimal PDF so the browser can download it.
    Actually returns PNG bytes directly — views serve it as image/png.
    """
    from PIL import Image, ImageDraw, ImageFont

    ttype = ticket.ticket_type.name.upper()
    cfg   = TICKET_CONFIG.get(ttype, DEFAULT_CONFIG)

    bg_path = os.path.join(settings.BASE_DIR, 'static', 'img', cfg['bg'])

    # ── Metallic gold layers per ticket type ─────────────────────────────
    def metallic_layers(t):
        if 'SPECIAL' in t:
            return [(3,3,(20,8,0,220)),(2,2,(50,22,0,230)),(0,0,(110,60,0,255)),
                    (-1,-1,(160,95,15,255)),(-2,-2,(195,130,30,255)),(-3,-3,(220,160,55,200))]
        elif 'VIP' in t:
            return [(3,3,(20,8,0,220)),(2,2,(50,22,0,230)),(0,0,(110,65,0,255)),
                    (-1,-1,(170,100,10,255)),(-2,-2,(200,135,25,255)),(-3,-3,(225,165,50,200))]
        elif 'TABLE' in t:
            return [(3,3,(20,8,0,220)),(2,2,(50,22,0,230)),(0,0,(100,55,0,255)),
                    (-1,-1,(155,90,10,255)),(-2,-2,(190,125,25,255)),(-3,-3,(215,155,45,200))]
        else:
            return [(3,3,(20,8,0,220)),(2,2,(50,22,0,230)),(0,0,(100,55,0,255)),
                    (-1,-1,(155,90,5,255)),(-2,-2,(185,120,20,255)),(-3,-3,(210,150,40,200))]

    def draw_m(draw, text, x, y, font, t):
        for ox, oy, color in metallic_layers(t):
            draw.text((x+ox, y+oy), text, font=font, fill=color)

    def get_font(size):
        for path in ['C:/Windows/Fonts/impact.ttf',
                     '/usr/share/fonts/truetype/msttcorefonts/Impact.ttf',
                     '/usr/share/fonts/truetype/freefont/FreeSansBold.ttf']:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    if not os.path.exists(bg_path):
        # Fallback — plain white image
        bg = Image.new('RGB', (1280, 640), (245, 240, 232))
    else:
        bg = Image.open(bg_path).convert('RGBA')

    w, h = bg.size
    draw = ImageDraw.Draw(bg)

    is_plain = (
        ticket.guest.full_name in ('Pandora Guest', 'Complimentary Guest') or
        getattr(ticket, 'is_complimentary', False)
    )

    # ── QR code ──────────────────────────────────────────────────────────
    if 'SPECIAL' in ttype:
        # New Special Guest ticket — exact pixel placement
        stub_cx = (int(w*0.76)+w)//2
        qr_w_px, qr_h_px = 190, 170
        qr_x = stub_cx - qr_w_px//2 + 20
        qr_y = 280
    else:
        qr_cx_pct = cfg.get('qr_cx_pct', 0.858)
        qr_cy_pct = cfg.get('qr_cy_pct', 0.607)
        qr_w_px   = int(w * cfg.get('qr_w_pct', 0.1384)) if 'qr_w_pct' in cfg else int(w * cfg.get('qr_w_in', 1.177) / 8.0)
        qr_h_px   = int(h * cfg.get('qr_h_pct', 0.2140)) if 'qr_h_pct' in cfg else int(h * cfg.get('qr_h_in', 0.642) / 3.0)
        qr_size   = min(qr_w_px, qr_h_px)
        qr_x      = int(w * qr_cx_pct) - qr_size // 2
        qr_y      = int(h * (1 - qr_cy_pct)) - qr_size // 2
        qr_w_px = qr_h_px = qr_size

    qr_png  = generate_qr_image(ticket.qr_token, size=10)
    qr_img  = Image.open(io.BytesIO(qr_png)).convert('RGBA')
    qr_img  = qr_img.resize((qr_w_px, qr_h_px), Image.LANCZOS)
    bg.paste(qr_img, (qr_x, qr_y))

    # ── Guest name ────────────────────────────────────────────────────────
    if not is_plain:
        guest_name = ticket.guest.full_name.upper()

        if 'SPECIAL' in ttype:
            # New Special Guest ticket layout
            stub_cx = (int(w*0.76)+w)//2
            sx1,sy1 = int(w*0.08), int(h*0.790)
            sx2,sy2 = int(w*0.70), int(h*0.930)
            strip_h = sy2-sy1
            fs = int(strip_h*0.82)
            while fs > 8:
                fn = get_font(fs)
                bbox = draw.textbbox((0,0), guest_name, font=fn)
                if (bbox[2]-bbox[0]) <= (sx2-sx1-16): break
                fs -= 1
            bbox = draw.textbbox((0,0), guest_name, font=fn)
            ny = sy1 + (strip_h-(bbox[3]-bbox[1]))//2 - bbox[1]
            draw_m(draw, guest_name, sx1+10, ny, fn, ttype)
        else:
            # Other ticket types
            if 'VIP' in ttype:
                sx1,sy1 = int(w*0.07), int(h*0.818)
                sx2,sy2 = int(w*0.735), int(h*0.920)
            elif 'TABLE' in ttype:
                sx1,sy1 = int(w*0.07), int(h*0.818)
                sx2,sy2 = int(w*0.735), int(h*0.920)
            else:
                sx1,sy1 = int(w*0.07), int(h*0.818)
                sx2,sy2 = int(w*0.735), int(h*0.920)

            strip_h = sy2-sy1
            # Cover TICKET HOLDER text
            if 'VIP' in ttype:    cov=(5,3,4)
            elif 'TABLE' in ttype: cov=(8,0,3)
            else:                   cov=(250,248,239)
            draw.rectangle([sx1,sy1,sx2,sy2], fill=cov+(255,))

            fs = int(strip_h*0.82)
            while fs > 8:
                fn = get_font(fs)
                bbox = draw.textbbox((0,0), guest_name, font=fn)
                if (bbox[2]-bbox[0]) <= (sx2-sx1-16): break
                fs -= 1
            bbox = draw.textbbox((0,0), guest_name, font=fn)
            ny = sy1 + (strip_h-(bbox[3]-bbox[1]))//2 - bbox[1]
            draw_m(draw, guest_name, sx1+10, ny, fn, ttype)

    # ── Convert to PNG bytes ──────────────────────────────────────────────
    out = io.BytesIO()
    bg.convert('RGB').save(out, format='PNG', dpi=(300,300))
    return out.getvalue()


def _draw_photo_placeholder(c, x, y, w, h):
    from reportlab.lib import colors as _c
    c.setFillColor(_c.HexColor('#eeeeee'))
    c.rect(x, y, w, h, fill=1, stroke=0)
