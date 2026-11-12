"""
Management command: python manage.py import_bulk_tickets

Imports pre-generated plain tickets (no personal info) into the database.
Reads ticket data from bulk_tickets.csv in the project root.

Each ticket is linked to:
  - A shared placeholder guest "Pandora Guest"
  - The currently active event
  - The ticket type matching the CSV row

Usage:
  python manage.py import_bulk_tickets
  python manage.py import_bulk_tickets --csv path/to/file.csv
  python manage.py import_bulk_tickets --clear   # wipe existing bulk tickets first
"""

import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from tickets.models import Guest, Ticket, TicketType, Event, UserProfile


class Command(BaseCommand):
    help = 'Import pre-generated plain tickets from bulk_tickets.csv into the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            default=None,
            help='Path to the CSV file (default: bulk_tickets.csv in project root)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing bulk plain tickets before importing',
        )

    def handle(self, *args, **options):
        from django.conf import settings

        csv_path = options['csv'] or os.path.join(settings.BASE_DIR, 'bulk_tickets.csv')

        if not os.path.exists(csv_path):
            raise CommandError(f'CSV file not found: {csv_path}')

        # ── Active event ──────────────────────────────────────────────────
        event = Event.objects.filter(active=True).first()
        if not event:
            raise CommandError('No active event found. Run seed_data first.')
        self.stdout.write(f'  Event: {event.event_name}')

        # ── Optionally clear existing bulk tickets ─────────────────────────
        if options['clear']:
            deleted = Ticket.objects.filter(
                guest__full_name='Pandora Guest',
                guest__phone_number='0000000000',
            ).delete()
            self.stdout.write(self.style.WARNING(
                f'  Cleared {deleted[0]} existing bulk tickets.'
            ))

        # ── Get or create the shared placeholder guest ─────────────────────
        # Plain tickets have no personal info — all linked to one placeholder
        placeholder_guest, created = Guest.objects.get_or_create(
            full_name='Pandora Guest',
            phone_number='0000000000',
            defaults={
                'email': '',
                'registration_source': Guest.RegistrationSource.PRE_REGISTERED,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  ✔ Placeholder guest created.'))
        else:
            self.stdout.write('  — Placeholder guest already exists.')

        # ── Read CSV and import ────────────────────────────────────────────
        imported = 0
        skipped  = 0
        errors   = 0

        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f'  Importing {len(rows)} tickets from CSV...')

        for row in rows:
            ticket_number = row.get('ticket_number', '').strip()
            qr_token      = row.get('qr_token', '').strip()
            type_name     = row.get('ticket_type', '').strip()

            if not ticket_number or not qr_token or not type_name:
                self.stdout.write(self.style.WARNING(f'  ⚠ Skipping invalid row: {row}'))
                skipped += 1
                continue

            # Skip if already exists
            if Ticket.objects.filter(ticket_number=ticket_number).exists():
                skipped += 1
                continue
            if Ticket.objects.filter(qr_token=qr_token).exists():
                skipped += 1
                continue

            # Get ticket type
            ticket_type = TicketType.objects.filter(
                name__iexact=type_name
            ).first()
            if not ticket_type:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ Ticket type not found: {type_name} — skipping {ticket_number}'
                ))
                errors += 1
                continue

            try:
                ticket = Ticket(
                    guest=placeholder_guest,
                    event=event,
                    ticket_type=ticket_type,
                    status=Ticket.Status.ACTIVE,
                )
                # Bypass auto-generation — use the pre-generated values
                ticket.ticket_number = ticket_number
                ticket.qr_token = qr_token
                ticket.save()
                imported += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error on {ticket_number}: {e}'))
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n  ✔ Import complete!'
            f'\n    Imported : {imported}'
            f'\n    Skipped  : {skipped}'
            f'\n    Errors   : {errors}'
        ))
