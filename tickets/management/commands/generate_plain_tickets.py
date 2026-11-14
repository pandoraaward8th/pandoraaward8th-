"""
Management command: python manage.py generate_plain_tickets

Creates plain tickets (no personal info) directly in the database and
generates matching PNG ticket images with QR codes.

Tickets are created as ACTIVE and linked to a shared placeholder guest.
After running this command, the QR codes on the generated PNGs will
scan and verify correctly.

Usage:
  python manage.py generate_plain_tickets
  python manage.py generate_plain_tickets --clear   # wipe and regenerate
"""

import io
import os
import zipfile

import qrcode
from PIL import Image
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from tickets.models import Guest, Ticket, TicketType, Event


# ── Ticket counts and background images ───────────────────────────────────────
TICKET_PLAN = [
    {'type': 'Regular',       'count': 200, 'bg': 'REGULAR (1).PNG',
     'qr_cx_pct': 0.858, 'qr_cy_pct': 0.607, 'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140},
    {'type': 'VIP',           'count': 100, 'bg': 'VIP.jpeg',
     'qr_cx_pct': 0.870, 'qr_cy_pct': 0.607, 'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140},
    {'type': 'Table of Ten',  'count':  40, 'bg': 'Pandora Awards Table for Ten Ticket.png',
     'qr_cx_pct': 0.870, 'qr_cy_pct': 0.607, 'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140},
]

SITE_URL = 'https://pandoraaward8th.onrender.com'
IMG_DIR  = os.path.join(settings.BASE_DIR, 'static', 'img')


class Command(BaseCommand):
    help = 'Generate plain tickets in the database and export PNG images with QR codes.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing plain tickets before generating new ones',
        )
        parser.add_argument(
            '--out',
            default=None,
            help='Output directory for PNGs (default: Pandora_Tickets in project root)',
        )

    def handle(self, *args, **options):
        out_dir = options['out'] or os.path.join(settings.BASE_DIR, 'Pandora_Tickets')
        img_dir = os.path.join(settings.BASE_DIR, 'static', 'img')

        # ── Active event ──────────────────────────────────────────────
        event = Event.objects.filter(active=True).first()
        if not event:
            raise CommandError('No active event found. Run seed_data first.')
        self.stdout.write(f'  Event: {event.event_name}')

        # ── Placeholder guest ─────────────────────────────────────────
        placeholder, created = Guest.objects.get_or_create(
            full_name='Pandora Guest',
            phone_number='0000000000',
            defaults={'registration_source': Guest.RegistrationSource.PRE_REGISTERED},
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  ✔ Placeholder guest created.'))

        # ── Clear existing plain tickets ──────────────────────────────
        if options['clear']:
            deleted = Ticket.objects.filter(guest=placeholder).delete()
            self.stdout.write(self.style.WARNING(
                f'  Cleared {deleted[0]} existing plain tickets.'
            ))

        # ── Create output folders ────────────────────────────────────
        os.makedirs(out_dir, exist_ok=True)
        for plan in TICKET_PLAN:
            folder = plan['type'].replace(' ', '_')
            os.makedirs(os.path.join(out_dir, folder), exist_ok=True)

        # ── Generate tickets ──────────────────────────────────────────
        total_created = 0
        total_skipped = 0

        for plan in TICKET_PLAN:
            ttype = TicketType.objects.filter(name=plan['type']).first()
            if not ttype:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ Ticket type not found: {plan["type"]} — skipping'
                ))
                continue

            bg_path = os.path.join(img_dir, plan['bg'])
            if not os.path.exists(bg_path):
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ Background not found: {plan["bg"]} — skipping'
                ))
                continue

            folder = plan['type'].replace(' ', '_')
            count = plan['count']
            self.stdout.write(f'\n  Generating {count} {plan["type"]} tickets...')

            for i in range(1, count + 1):
                # Skip if we already have enough of this type
                existing = Ticket.objects.filter(
                    guest=placeholder, ticket_type=ttype
                ).count()
                if existing >= count:
                    total_skipped += count - 0
                    self.stdout.write(f'    — Already have {existing} {plan["type"]} tickets, skipping.')
                    break

                # Create ticket in database
                ticket = Ticket(
                    guest=placeholder,
                    event=event,
                    ticket_type=ttype,
                    status=Ticket.Status.ACTIVE,
                )
                ticket.save()  # auto-generates ticket_number and qr_token

                # Generate PNG
                png = self._generate_png(ticket, bg_path, plan)
                filename = f"{ticket.ticket_number}.png"
                png.save(os.path.join(out_dir, folder, filename), 'PNG', dpi=(300, 300))

                total_created += 1
                if i % 25 == 0 or i == count:
                    self.stdout.write(f'    [{total_created}/{sum(p["count"] for p in TICKET_PLAN)}] {ticket.ticket_number}')

        # ── Summary ───────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            f'\n  ✔ Done!'
            f'\n    Created : {total_created} tickets in database'
            f'\n    PNGs    : {out_dir}'
            f'\n    Total in DB: {Ticket.objects.filter(guest=placeholder).count()} plain tickets'
        ))

    def _generate_png(self, ticket, bg_path, plan):
        """Overlay QR code onto the ticket background image."""
        bg = Image.open(bg_path).convert('RGBA')
        w, h = bg.size

        # QR dimensions
        qr_w = int(w * plan['qr_w_pct'])
        qr_h = int(h * plan['qr_h_pct'])
        qr_size = min(qr_w, qr_h)

        # QR position (centre)
        qr_cx = int(w * plan['qr_cx_pct'])
        qr_cy = int(h * plan['qr_cy_pct'])
        qr_x = qr_cx - qr_size // 2
        qr_y = qr_cy - qr_size // 2

        # Generate QR code
        verify_url = f"{SITE_URL}/verify/qr/{ticket.qr_token}/"
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
        qr_img = qr_img.resize((qr_size, qr_size), Image.LANCZOS)

        # Paste QR onto background
        bg.paste(qr_img, (qr_x, qr_y))

        return bg.convert('RGB')
