"""Generate 6 new tickets: 5 SP + 1 VIP"""
import os, uuid, csv, qrcode, secrets, string
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = r'C:\Users\HighTension\Desktop\PANDORA AWARD 8TH'
IMG_DIR  = os.path.join(BASE_DIR, 'static', 'img')
IMPACT   = 'C:/Windows/Fonts/impact.ttf'
SITE_URL = 'https://pandoraaward8th.onrender.com'

SP_LAYERS  = [(3,3,(20,8,0,220)),(2,2,(50,22,0,230)),(0,0,(110,60,0,255)),
              (-1,-1,(160,95,15,255)),(-2,-2,(195,130,30,255)),(-3,-3,(220,160,55,200))]
VIP_LAYERS = [(3,3,(20,8,0,220)),(2,2,(50,22,0,230)),(0,0,(110,65,0,255)),
              (-1,-1,(170,100,10,255)),(-2,-2,(200,135,25,255)),(-3,-3,(225,165,50,200))]

def draw_m(draw, text, x, y, font, layers):
    for ox, oy, color in layers:
        draw.text((x+ox, y+oy), text, font=font, fill=color)

def make_qr(token, w, h):
    url = f'{SITE_URL}/verify/qr/{token}/'
    qr  = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_H,
                        box_size=10, border=2)
    qr.add_data(url); qr.make(fit=True)
    return qr.make_image(fill_color='black', back_color='white').convert('RGBA').resize((w, h), Image.LANCZOS)

def make_tnum(used):
    chars = string.ascii_uppercase + string.digits
    while True:
        t = 'PDR26-' + ''.join(secrets.choice(chars) for _ in range(6))
        if t not in used:
            used.add(t)
            return t

NEW_TICKETS = [
    ('SP-099',  'Abubakar S Muhammad',  'sp'),
    ('VIP-038', 'Xeevash',              'vip'),
    ('SP-100',  'Princess Mupheeda',    'sp'),
    ('SP-101',  'Isah Ferozkhan',       'sp'),
    ('SP-102',  'Fauziyya D. Sulaiman', 'sp'),
    ('SP-103',  'Ommeeta',              'sp'),
]

used = set()
csv_rows = []

for serial, guest_name, ttype in NEW_TICKETS:
    tnum  = make_tnum(used)
    token = uuid.uuid4().hex

    if ttype == 'sp':
        bg_file = 'Pandora Awards SPecial guestTicket Poster  .jpeg'
        out_dir = os.path.join(BASE_DIR, 'Named_Tickets', 'Special_Guest')
        layers  = SP_LAYERS
        ticket_type = 'Special Guest Seat'
    else:
        bg_file = 'VIP.jpeg'
        out_dir = os.path.join(BASE_DIR, 'Named_Tickets', 'VIP')
        layers  = VIP_LAYERS
        ticket_type = 'VIP'

    bg   = Image.open(os.path.join(IMG_DIR, bg_file)).convert('RGBA')
    w, h = bg.size
    draw = ImageDraw.Draw(bg)
    stub_cx = (int(w * 0.755) + w) // 2

    if ttype == 'sp':
        qr_w, qr_h_sz = 190, 170
        qr_x = stub_cx - qr_w // 2 + 20
        bg.paste(make_qr(token, qr_w, qr_h_sz), (qr_x, 280))
        sx1, sy1 = int(w*0.08), int(h*0.790)
        sx2, sy2 = int(w*0.70), int(h*0.930)
        strip_h  = sy2 - sy1
        fs = int(strip_h * 0.82)
        name = guest_name.upper()
        while fs > 8:
            fn = ImageFont.truetype(IMPACT, fs)
            b  = draw.textbbox((0,0), name, font=fn)
            if (b[2]-b[0]) <= (sx2-sx1-16): break
            fs -= 1
        b = draw.textbbox((0,0), name, font=fn)
        draw_m(draw, name, sx1+10, sy1+(strip_h-(b[3]-b[1]))//2-b[1], fn, layers)
        sfy = int(h*0.880)
        sfn = ImageFont.truetype(IMPACT, int(h*0.065))
        sb  = draw.textbbox((0,0), serial, font=sfn)
        draw_m(draw, serial, stub_cx-(sb[2]-sb[0])//2, sfy, sfn, layers)
    else:
        qr_size = int(min(w*0.1384, h*0.2140))
        qr_cx, qr_cy = int(w*0.870), int(h*0.607)
        bg.paste(make_qr(token, qr_size, qr_size), (qr_cx-qr_size//2, qr_cy-qr_size//2))
        sx1, sy1 = int(w*0.07), int(h*0.818)
        sx2, sy2 = int(w*0.735), int(h*0.920)
        draw.rectangle([sx1, sy1, sx2, sy2], fill=(5,3,4,255))
        name    = guest_name.upper()
        strip_h = sy2 - sy1
        fs = int(strip_h * 0.82)
        while fs > 8:
            fn = ImageFont.truetype(IMPACT, fs)
            b  = draw.textbbox((0,0), name, font=fn)
            if (b[2]-b[0]) <= (sx2-sx1-16): break
            fs -= 1
        b = draw.textbbox((0,0), name, font=fn)
        draw_m(draw, name, sx1+10, sy1+(strip_h-(b[3]-b[1]))//2-b[1], fn, layers)
        sfy = int(h*0.835)
        sfn = ImageFont.truetype(IMPACT, int(h*0.052))
        sb  = draw.textbbox((0,0), serial, font=sfn)
        draw_m(draw, serial, stub_cx-(sb[2]-sb[0])//2, sfy, sfn, layers)

    safe = guest_name.replace(' ', '_').replace('.', '').replace("'", '')
    out  = os.path.join(out_dir, f'{serial}_{safe}_{tnum}.png')
    bg.convert('RGB').save(out, 'PNG', dpi=(300,300))
    print(f'Saved: {serial} — {guest_name} ({tnum})')

    csv_rows.append({
        'ticket_number': tnum,
        'qr_token':      token,
        'ticket_type':   ticket_type,
        'guest_name':    guest_name,
        'filename':      f'{out_dir}/{serial}_{safe}_{tnum}.png',
    })

# Append to named_tickets.csv
csv_path = os.path.join(BASE_DIR, 'named_tickets.csv')
with open(csv_path, 'a', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['ticket_number','qr_token','ticket_type','guest_name','filename'])
    writer.writerows(csv_rows)

print(f'\nDone! {len(NEW_TICKETS)} tickets generated and CSV updated.')
