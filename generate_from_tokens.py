"""
Pandora Awards 8th Edition — Generate PNG Tickets from Render Token CSV

Steps:
1. Log in to your Render app
2. Click "Export Ticket Tokens CSV" on the dashboard
3. Save the file as render_ticket_tokens.csv in this project folder
4. Run: python generate_from_tokens.py

Output:
  Pandora_Tickets/Regular/       — 200 PNGs
  Pandora_Tickets/VIP/           — 150 PNGs
  Pandora_Tickets/Special_Guest_Seat/ — 70 PNGs
  Pandora_Tickets.zip
"""

import csv
import io
import os
import zipfile

import qrcode
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
SITE_URL  = 'https://pandoraaward8th.onrender.com'
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
IMG_DIR   = os.path.join(BASE_DIR, 'static', 'img')
CSV_PATH  = os.path.join(BASE_DIR, 'render_ticket_tokens.csv')
OUT_DIR   = os.path.join(BASE_DIR, 'Pandora_Tickets')
ZIP_PATH  = os.path.join(BASE_DIR, 'Pandora_Tickets.zip')

# Background images per ticket type
TYPE_CONFIG = {
    'Regular': {
        'bg': 'REGULAR (1).PNG',
        'qr_cx_pct': 0.858, 'qr_cy_pct': 0.607,
        'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140,
    },
    'VIP': {
        'bg': 'VIP.jpeg',
        'qr_cx_pct': 0.870, 'qr_cy_pct': 0.607,
        'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140,
    },
    'Special Guest Seat': {
        'bg': 'Pandora Awards SPecial guestTicket Poster.png',
        'qr_cx_pct': 0.870, 'qr_cy_pct': 0.607,
        'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140,
    },
    'Table of Ten': {
        'bg': 'Pandora Awards Table for Ten Ticket.png',
        'qr_cx_pct': 0.870, 'qr_cy_pct': 0.607,
        'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140,
    },
}


def generate_qr(qr_token, size_px):
    verify_url = f"{SITE_URL}/verify/qr/{qr_token}/"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10, border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
    return img.resize((size_px, size_px), Image.LANCZOS)


def make_ticket_png(ticket_number, qr_token, ticket_type):
    cfg = TYPE_CONFIG.get(ticket_type, TYPE_CONFIG['Regular'])
    bg_path = os.path.join(IMG_DIR, cfg['bg'])

    bg = Image.open(bg_path).convert('RGBA')
    w, h = bg.size

    qr_size = int(min(w * cfg['qr_w_pct'], h * cfg['qr_h_pct']))
    qr_cx = int(w * cfg['qr_cx_pct'])
    qr_cy = int(h * cfg['qr_cy_pct'])
    qr_x = qr_cx - qr_size // 2
    qr_y = qr_cy - qr_size // 2

    qr_img = generate_qr(qr_token, qr_size)
    bg.paste(qr_img, (qr_x, qr_y))
    return bg.convert('RGB')


def main():
    if not os.path.exists(CSV_PATH):
        print(f"✗ CSV not found: {CSV_PATH}")
        print("  → Log in to your Render app, click 'Export Ticket Tokens CSV' on the dashboard,")
        print("    save it as render_ticket_tokens.csv in this folder, then run again.")
        return

    # Read CSV
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    print(f"🎟  Pandora Awards — Generating {len(rows)} ticket PNGs from Render tokens")
    print("=" * 60)

    # Create folders
    os.makedirs(OUT_DIR, exist_ok=True)
    for cfg_key in TYPE_CONFIG:
        os.makedirs(os.path.join(OUT_DIR, cfg_key.replace(' ', '_')), exist_ok=True)

    done = 0
    for row in rows:
        ticket_number = row['ticket_number'].strip()
        qr_token      = row['qr_token'].strip()
        ticket_type   = row['ticket_type'].strip()

        cfg = TYPE_CONFIG.get(ticket_type, TYPE_CONFIG['Regular'])
        bg_path = os.path.join(IMG_DIR, cfg['bg'])
        if not os.path.exists(bg_path):
            print(f"  ✗ Background not found: {cfg['bg']}")
            continue

        img = make_ticket_png(ticket_number, qr_token, ticket_type)
        folder = ticket_type.replace(' ', '_')
        img.save(os.path.join(OUT_DIR, folder, f"{ticket_number}.png"), 'PNG', dpi=(300, 300))

        done += 1
        if done % 50 == 0 or done == len(rows):
            print(f"  [{done}/{len(rows)}] {ticket_number} ({ticket_type})")

    # Zip
    print(f"\n  Zipping ...")
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUT_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                arcname  = os.path.relpath(filepath, BASE_DIR)
                zf.write(filepath, arcname)

    zip_mb = os.path.getsize(ZIP_PATH) / (1024 * 1024)
    print(f"\n  ✔ Done! {done} tickets generated.")
    print(f"  ✔ ZIP: Pandora_Tickets.zip ({zip_mb:.1f} MB)")
    print(f"  📁 Folder: {OUT_DIR}")


if __name__ == '__main__':
    main()
