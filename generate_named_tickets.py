"""
Pandora Awards 8th Edition — Auto Named Ticket Generator
Generates PNG tickets for all guests in the ticket register.

Steps:
1. Make sure render_ticket_tokens.csv is in this folder (export from dashboard)
   — OR — run with --db to create tickets in the local Django database directly
2. Run: python generate_named_tickets.py

Output:
  Named_Tickets/
    Special_Guest/   — 83 tickets
    VIP/             — 37 tickets
    Table_of_Ten/    — 10 tickets
  Named_Tickets.zip
"""

import os
import io
import csv
import uuid
import string
import secrets
import zipfile
import qrcode
from PIL import Image, ImageDraw, ImageFont

# ── Ticket register from PDF ──────────────────────────────────────────────────
# Format: (Name, SP_count, VIP_count, Table_count)
TICKET_REGISTER = [
    ("DJ AB",                        3, 0, 1),
    ("BEBEJI",                       1, 0, 0),
    ("DAN MUSA",                     1, 0, 0),
    ("DEE JOKER",                    0, 1, 0),
    ("Aisha Aliyu",                  1, 4, 0),
    ("SADIQ DUNIYA",                 1, 0, 1),
    ("MUDAHHAR ABDULKAREEM ISAH",    1, 0, 1),
    ("Saleem Goje",                  1, 0, 1),
    ("ABDULMUMIN SANI MATI",         1, 0, 1),
    ("MUBARAK MK",                   1, 2, 0),
    ("DAN BABAN GAWUNA",             1, 0, 0),
    ("Kikishi",                      1, 0, 0),
    ("Nuhu Abdullahi",               3, 5, 0),
    ("Shafa wali",                   1, 5, 0),
    ("MAHMOOD Mamman Lagos",         2, 5, 0),
    ("Sabeerah Sanusi",              1, 0, 0),
    ("Northern Trending",            1, 0, 0),
    ("HAJ. ZABBA'U YAKMUT",          1, 2, 0),
    ("MUHAMMAD SAMBO ALHASSAN",      2, 0, 1),
    ("Little chef leema",            2, 0, 0),
    ("OG Abba",                      1, 0, 0),
    ("YOUNG ALAJERH",                0, 1, 0),
    ("HAFSAT HABIB",                 0, 1, 0),
    ("AMNA MAKEUP",                  0, 1, 0),
    ("MADEENA MAI SHANU",            1, 0, 0),
    ("ABIS FULANI",                  1, 0, 0),
    ("ANAM & AMAR",                  2, 0, 0),
    ("CAPTAIN UNLOCK",               2, 0, 0),
    ("MC ASHRAF",                    1, 0, 0),
    ("AREWA 24 TV",                  0, 0, 1),
    ("S. FARI",                      1, 0, 0),
    ("RAUDAH TRAVELS",               1, 0, 0),
    ("WHITE BIRD TRAVELS",           1, 0, 1),
    ("UNGLDE",                       1, 0, 0),
    ("HAUWA GWANGWAZO",              4, 0, 1),
    ("ALAMIN USMAN",                 0, 1, 0),
    ("ZEE SURY",                     1, 0, 0),
    ("FEEZY",                        1, 0, 0),
    ("SAGY GEE",                     1, 0, 0),
    ("SAFIYA ALKALI AJIKOLO",        1, 0, 0),
    ("HABIBAT MUHAMMAD AMIN",        1, 0, 0),
    ("MISS NORTH CENTRAL",           1, 0, 0),
    ("UMAR BOLORI",                  1, 0, 0),
    ("HAJARA YASMIN ISA",            0, 2, 0),
    ("UMAR UK",                      3, 0, 0),
    ("SADIQ SANI SADIQ",             3, 0, 0),
    ("AISHA NAJAMU",                 1, 0, 0),
    ("MINAL AHMED",                  1, 0, 0),
    ("AHMAD ILIYAS TANTIRI",         1, 0, 0),
    ("AMEENA HASSAN",                1, 0, 0),
    ("ABUBAKAR UMAR XHAKA",          1, 0, 0),
    ("ABADAN",                       1, 0, 0),
    ("HASSAN GIGS",                  1, 0, 0),
    ("YAKUBU M. KUMO",               1, 0, 0),
    ("HAJ HABIBA SHEHU DAN FULANI",  5, 0, 0),
    ("ALIYU ABDULRAHMAN",            0, 0, 1),
    ("SADAUKIN JIBIYA",              2, 0, 0),
    ("SOPHY A CHINA",                1, 0, 0),
    ("SABEERA SANUSI",               1, 0, 0),
    ("RABIU ALIYU GARO",             1, 0, 0),
    ("Rayhan",                       2, 0, 0),
    ("Problem queen",                1, 2, 0),
    ("Kulthum",                      1, 0, 0),
    ("Rahama Saidu",                 1, 0, 0),
    ("Meerah Shuaibu",               1, 0, 0),
    ("Nabila kurfi",                 0, 1, 0),
    ("Pheer Dawsee",                 0, 1, 0),
    ("Raheela",                      0, 1, 0),
    ("Yar baba",                     1, 0, 0),
    ("Aunty rabi",                   1, 0, 0),
    ("Mubbas",                       0, 1, 0),
    ("Hajjo beauty",                 0, 1, 0),
    ("Zaleena",                      1, 0, 0),
    ("MARYAM AB YOLA",               1, 0, 0),
]

# ── Config ────────────────────────────────────────────────────────────────────
SITE_URL = 'https://pandoraaward8th.onrender.com'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR  = os.path.join(BASE_DIR, 'static', 'img')
OUT_DIR  = os.path.join(BASE_DIR, 'Named_Tickets')
ZIP_PATH = os.path.join(BASE_DIR, 'Named_Tickets.zip')

TYPE_CONFIG = {
    'Special Guest Seat': {
        'bg':          'Pandora Awards SPecial guestTicket Poster.png',
        'qr_cx_pct':   0.870, 'qr_cy_pct': 0.607,
        'qr_w_pct':    0.1384,'qr_h_pct':  0.2140,
        'cover_color': (4, 21, 2),
        'name_color':  (209, 153, 53, 255),   # exact gold from Special Guest ticket
        'folder':      'Special_Guest',
    },
    'VIP': {
        'bg':          'VIP.jpeg',
        'qr_cx_pct':   0.870, 'qr_cy_pct': 0.607,
        'qr_w_pct':    0.1384,'qr_h_pct':  0.2140,
        'cover_color': (5, 3, 4),
        'name_color':  (251, 156, 34, 255),   # exact gold from VIP ticket
        'folder':      'VIP',
    },
    'Table of Ten': {
        'bg':          'Pandora Awards Table for Ten Ticket.png',
        'qr_cx_pct':   0.870, 'qr_cy_pct': 0.607,
        'qr_w_pct':    0.1384,'qr_h_pct':  0.2140,
        'cover_color': (8, 0, 3),
        'name_color':  (236, 168, 56, 255),   # exact gold from Table ticket
        'folder':      'Table_of_Ten',
    },
}

FONT_PATHS = [
    'C:/Windows/Fonts/impact.ttf',      # Bold condensed display — perfect for ticket names
    'C:/Windows/Fonts/arialbd.ttf',
    'C:/Windows/Fonts/georgiab.ttf',
]

def get_font(size):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()

def metallic_gold_layers(ticket_type):
    """6-layer 3D metallic gold — darker rich tones."""
    t = ticket_type.upper()
    if 'SPECIAL' in t:
        return [
            (3,  3,  (20,  8,   0,   220)),
            (2,  2,  (50,  22,  0,   230)),
            (0,  0,  (110, 60,  0,   255)),
            (-1,-1,  (160, 95,  15,  255)),
            (-2,-2,  (195, 130, 30,  255)),
            (-3,-3,  (220, 160, 55,  200)),
        ]
    elif 'VIP' in t:
        return [
            (3,  3,  (20,  8,   0,   220)),
            (2,  2,  (50,  22,  0,   230)),
            (0,  0,  (110, 65,  0,   255)),
            (-1,-1,  (170, 100, 10,  255)),
            (-2,-2,  (200, 135, 25,  255)),
            (-3,-3,  (225, 165, 50,  200)),
        ]
    elif 'TABLE' in t:
        return [
            (3,  3,  (20,  8,   0,   220)),
            (2,  2,  (50,  22,  0,   230)),
            (0,  0,  (100, 55,  0,   255)),
            (-1,-1,  (155, 90,  10,  255)),
            (-2,-2,  (190, 125, 25,  255)),
            (-3,-3,  (215, 155, 45,  200)),
        ]
    else:
        return [
            (3,  3,  (20,  8,   0,   220)),
            (2,  2,  (50,  22,  0,   230)),
            (0,  0,  (100, 55,  0,   255)),
            (-1,-1,  (155, 90,  5,   255)),
            (-2,-2,  (185, 120, 20,  255)),
            (-3,-3,  (210, 150, 40,  200)),
        ]

def make_qr(token, size_px):
    url = f"{SITE_URL}/verify/qr/{token}/"
    qr  = qrcode.QRCode(version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white').convert('RGBA')
    return img.resize((size_px, size_px), Image.LANCZOS)

def make_ticket_number():
    chars  = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f"PDR26-{suffix}"

def make_named_ticket(guest_name, ticket_type, qr_token):
    cfg     = TYPE_CONFIG[ticket_type]
    bg_path = os.path.join(IMG_DIR, cfg['bg'])
    bg      = Image.open(bg_path).convert('RGBA')
    w, h    = bg.size

    # ── QR code ──────────────────────────────────────────────────────────
    qr_size = int(min(w * cfg['qr_w_pct'], h * cfg['qr_h_pct']))
    qr_cx   = int(w * cfg['qr_cx_pct'])
    qr_cy   = int(h * cfg['qr_cy_pct'])
    bg.paste(make_qr(qr_token, qr_size),
             (qr_cx - qr_size // 2, qr_cy - qr_size // 2))

    draw = ImageDraw.Draw(bg)

    # ── Cover TICKET HOLDER strip ────────────────────────────────────────
    # PIL y=0 at TOP; strip is at bottom ~82-92% of height from top
    strip_x1 = int(w * 0.07)
    strip_y1 = int(h * 0.818)   # top of strip (from top)
    strip_x2 = int(w * 0.735)
    strip_y2 = int(h * 0.920)   # bottom of strip
    cr, cg, cb = cfg['cover_color']
    draw.rectangle([strip_x1, strip_y1, strip_x2, strip_y2],
                   fill=(cr, cg, cb, 255))

    # ── Guest name — Impact font + 3D metallic gold ──────────────────────
    name    = guest_name.upper()
    max_w   = strip_x2 - strip_x1 - 16
    strip_h = strip_y2 - strip_y1

    # Auto-fit font size using Impact
    font_size = int(strip_h * 0.82)
    while font_size > 8:
        font = get_font(font_size)
        bbox = draw.textbbox((0, 0), name, font=font)
        if (bbox[2] - bbox[0]) <= max_w:
            break
        font_size -= 1

    text_h = bbox[3] - bbox[1]
    nx = strip_x1 + 10
    ny = strip_y1 + (strip_h - text_h) // 2 - bbox[1]

    # 3D metallic gold — layer by layer
    for ox, oy, color in metallic_gold_layers(ticket_type):
        draw.text((nx + ox, ny + oy), name, font=font, fill=color)

    return bg.convert('RGB')


def main():
    print("🎟  Pandora Awards — Named Ticket Generator")
    print("=" * 55)

    # Create output folders
    for cfg in TYPE_CONFIG.values():
        os.makedirs(os.path.join(OUT_DIR, cfg['folder']), exist_ok=True)

    # Expand register into individual ticket rows
    tickets = []
    used_numbers = set()

    for name, sp, vip, tbl in TICKET_REGISTER:
        for _ in range(sp):
            tickets.append((name, 'Special Guest Seat'))
        for _ in range(vip):
            tickets.append((name, 'VIP'))
        for _ in range(tbl):
            tickets.append((name, 'Table of Ten'))

    total = len(tickets)
    print(f"  Total tickets to generate: {total}")

    # Also save a CSV for database import
    csv_rows = []
    done = 0

    for guest_name, ticket_type in tickets:
        # Unique token and ticket number
        qr_token = uuid.uuid4().hex
        ticket_number = make_ticket_number()
        while ticket_number in used_numbers:
            ticket_number = make_ticket_number()
        used_numbers.add(ticket_number)

        cfg    = TYPE_CONFIG[ticket_type]
        folder = cfg['folder']
        safe_name = guest_name.replace(' ', '_').replace('/', '-').replace('.', '').replace("'", '')
        fname  = f"{safe_name}_{ticket_number}.png"

        img = make_named_ticket(guest_name, ticket_type, qr_token)
        img.save(os.path.join(OUT_DIR, folder, fname), 'PNG', dpi=(300, 300))

        csv_rows.append({
            'ticket_number': ticket_number,
            'qr_token':      qr_token,
            'ticket_type':   ticket_type,
            'guest_name':    guest_name,
            'filename':      f"{folder}/{fname}",
        })

        done += 1
        if done % 20 == 0 or done == total:
            print(f"  [{done}/{total}] {guest_name} — {ticket_type}")

    # Save CSV for database import
    csv_path = os.path.join(BASE_DIR, 'named_tickets.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['ticket_number', 'qr_token',
                                          'ticket_type', 'guest_name', 'filename'])
        w.writeheader()
        w.writerows(csv_rows)
    print(f"\n  ✔ CSV saved: named_tickets.csv ({len(csv_rows)} rows)")

    # Zip
    print("  Zipping ...")
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUT_DIR):
            for file in sorted(files):
                fp = os.path.join(root, file)
                zf.write(fp, os.path.relpath(fp, BASE_DIR))

    zip_mb = os.path.getsize(ZIP_PATH) / (1024 * 1024)
    print(f"  ✔ ZIP saved: Named_Tickets.zip ({zip_mb:.1f} MB)")
    print(f"\n  Breakdown:")
    for tname in ['Special Guest Seat', 'VIP', 'Table of Ten']:
        count = sum(1 for r in csv_rows if r['ticket_type'] == tname)
        print(f"    {tname}: {count} tickets")


if __name__ == '__main__':
    main()
