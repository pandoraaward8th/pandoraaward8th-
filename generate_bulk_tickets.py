"""
Pandora Awards 8th Edition — Bulk Plain Ticket Generator
Generates PNG tickets with QR codes but NO personal info.

Output:
  Pandora_Tickets/
    Regular/     — 200 tickets
    VIP/         — 150 tickets
    Special_Guest/ — 70 tickets
  Pandora_Tickets.zip

Run: python generate_bulk_tickets.py
"""

import csv
import io
import os
import uuid
import zipfile
import secrets
import string

import qrcode
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────
SITE_URL  = 'https://pandoraaward8th.onrender.com'
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
IMG_DIR   = os.path.join(BASE_DIR, 'static', 'img')
OUT_DIR   = os.path.join(BASE_DIR, 'Pandora_Tickets')
ZIP_PATH  = os.path.join(BASE_DIR, 'Pandora_Tickets.zip')

# QR position as % of image dimensions (matching utils.py config)
TICKET_TYPES = {
    'Regular': {
        'bg':         'REGULAR (1).PNG',
        'count':      200,
        'qr_cx_pct':  0.858,
        'qr_cy_pct':  1 - 0.393,   # flip Y (PIL y=0 at top)
        'qr_w_pct':   0.1384,       # 1.177in / 8.0in
        'qr_h_pct':   0.2140,       # 0.642in / 3.0in
    },
    'VIP': {
        'bg':         'VIP.jpeg',
        'count':      150,
        'qr_cx_pct':  0.870,
        'qr_cy_pct':  1 - 0.393,
        'qr_w_pct':   0.1384,
        'qr_h_pct':   0.2140,
    },
    'Special_Guest': {
        'bg':         'Pandora Awards SPecial guestTicket Poster.png',
        'count':      70,
        'qr_cx_pct':  0.870,
        'qr_cy_pct':  1 - 0.393,
        'qr_w_pct':   0.1384,
        'qr_h_pct':   0.2140,
    },
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_ticket_number():
    """Generate a unique ticket number like PDR26-X7K92M."""
    chars = string.ascii_uppercase + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f"PDR26-{suffix}"


def make_qr_token():
    return uuid.uuid4().hex


def generate_qr_png(qr_token: str, size_px: int) -> Image.Image:
    """Generate a QR code as a PIL Image at a given pixel size."""
    verify_url = f"{SITE_URL}/verify/qr/{qr_token}/"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    img = img.resize((size_px, size_px), Image.LANCZOS)
    return img


def generate_ticket_png(bg_path: str, cfg: dict, ticket_number: str, qr_token: str) -> Image.Image:
    """
    Overlay QR code onto the ticket background image.
    Returns a PIL Image.
    """
    # Load background
    bg = Image.open(bg_path).convert('RGBA')
    w, h = bg.size

    # QR box dimensions in pixels
    qr_w = int(w * cfg['qr_w_pct'])
    qr_h = int(h * cfg['qr_h_pct'])
    qr_size = min(qr_w, qr_h)   # keep square

    # QR centre position in pixels
    qr_cx = int(w * cfg['qr_cx_pct'])
    qr_cy = int(h * cfg['qr_cy_pct'])
    qr_x  = qr_cx - qr_size // 2
    qr_y  = qr_cy - qr_size // 2

    # Generate QR
    qr_img = generate_qr_png(qr_token, qr_size).convert('RGBA')

    # Paste QR onto background
    bg.paste(qr_img, (qr_x, qr_y))

    # Convert to RGB for PNG saving (removes alpha for clean print)
    return bg.convert('RGB')


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("🎟  Pandora Awards 8th Edition — Bulk Ticket Generator")
    print("=" * 55)

    # Create output folders
    os.makedirs(OUT_DIR, exist_ok=True)
    for folder in TICKET_TYPES:
        os.makedirs(os.path.join(OUT_DIR, folder), exist_ok=True)

    generated_numbers = set()
    all_tickets = []   # for CSV export
    total = sum(t['count'] for t in TICKET_TYPES.values())
    done  = 0

    for type_name, cfg in TICKET_TYPES.items():
        bg_path = os.path.join(IMG_DIR, cfg['bg'])
        if not os.path.exists(bg_path):
            print(f"  ✗ Background image not found: {cfg['bg']} — skipping {type_name}")
            continue

        folder = os.path.join(OUT_DIR, type_name)
        count  = cfg['count']
        print(f"\n  Generating {count} {type_name.replace('_', ' ')} tickets...")

        for i in range(1, count + 1):
            # Unique ticket number
            ticket_number = make_ticket_number()
            while ticket_number in generated_numbers:
                ticket_number = make_ticket_number()
            generated_numbers.add(ticket_number)

            qr_token = make_qr_token()

            # Generate PNG
            img = generate_ticket_png(bg_path, cfg, ticket_number, qr_token)

            # Save
            filename = f"{ticket_number}.png"
            img.save(os.path.join(folder, filename), 'PNG', dpi=(300, 300))

            # Track for CSV
            all_tickets.append({
                'ticket_number': ticket_number,
                'qr_token':      qr_token,
                'ticket_type':   type_name.replace('_', ' '),
                'filename':      f"{type_name}/{filename}",
            })

            done += 1
            if i % 25 == 0 or i == count:
                print(f"    [{done}/{total}] {ticket_number}")

    # Save CSV
    csv_path = os.path.join(BASE_DIR, 'bulk_tickets.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['ticket_number', 'qr_token', 'ticket_type', 'filename'])
        writer.writeheader()
        writer.writerows(all_tickets)
    print(f"  ✔ CSV saved:  bulk_tickets.csv ({len(all_tickets)} rows)")

    # Zip everything
    print(f"\n  Zipping into Pandora_Tickets.zip ...")
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(OUT_DIR):
            for file in files:
                filepath = os.path.join(root, file)
                arcname  = os.path.relpath(filepath, BASE_DIR)
                zf.write(filepath, arcname)

    zip_size = os.path.getsize(ZIP_PATH) / (1024 * 1024)
    print(f"\n  ✔ Done! {done} tickets generated.")
    print(f"  ✔ ZIP saved: Pandora_Tickets.zip ({zip_size:.1f} MB)")
    print(f"  📁 Folder:   {OUT_DIR}")


if __name__ == '__main__':
    main()
