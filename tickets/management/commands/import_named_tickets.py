"""
Management command: python manage.py import_named_tickets

Reads named_tickets.csv and creates Guest + Ticket records in the database.
Each guest gets their own record — no placeholder used.
Tickets are created with pre-generated ticket_number and qr_token from the CSV
so the printed PNG tickets scan and verify correctly at the gate.

Usage:
  python manage.py import_named_tickets
  python manage.py import_named_tickets --clear   # remove existing and reimport
  python manage.py import_named_tickets --csv path/to/file.csv
"""

import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from tickets.models import Guest, Ticket, TicketType, Event


class Command(BaseCommand):
    help = 'Import named tickets from named_tickets.csv into the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            default=None,
            help='Path to CSV file (default: named_tickets.csv in project root)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all previously imported named tickets before importing',
        )

    def handle(self, *args, **options):
        csv_path = options['csv'] or os.path.join(settings.BASE_DIR, 'named_tickets.csv')

        if not os.path.exists(csv_path):
            raise CommandError(f'CSV not found: {csv_path}')

        # Active event
        event = Event.objects.filter(active=True).first()
        if not event:
            raise CommandError('No active event. Run seed_data first.')
        self.stdout.write(f'  Event: {event.event_name}')

        # Clear previously imported named tickets if requested
        if options['clear']:
            # Find all guests that were imported (not placeholders)
            excluded = ['Pandora Guest', 'Complimentary Guest']
            deleted = Ticket.objects.filter(
                is_complimentary=False,
            ).exclude(
                guest__full_name__in=excluded
            ).exclude(
                guest__phone_number='0000000000'
            ).delete()
            self.stdout.write(self.style.WARNING(
                f'  Cleared {deleted[0]} previously imported named tickets.'
            ))

        # Read CSV
        with open(csv_path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        self.stdout.write(f'  Importing {len(rows)} named tickets...')

        imported = 0
        skipped  = 0
        errors   = 0

        for row in rows:
            ticket_number = row.get('ticket_number', '').strip()
            qr_token      = row.get('qr_token', '').strip()
            ticket_type   = row.get('ticket_type', '').strip()
            guest_name    = row.get('guest_name', '').strip()

            if not all([ticket_number, qr_token, ticket_type, guest_name]):
                self.stdout.write(self.style.WARNING(f'  ⚠ Skipping incomplete row: {row}'))
                skipped += 1
                continue

            # Skip duplicates
            if Ticket.objects.filter(ticket_number=ticket_number).exists():
                skipped += 1
                continue
            if Ticket.objects.filter(qr_token=qr_token).exists():
                skipped += 1
                continue

            # Get ticket type
            ttype = TicketType.objects.filter(name__iexact=ticket_type).first()
            if not ttype:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ Ticket type not found: {ticket_type}'
                ))
                errors += 1
                continue

            try:
                # Get or create guest by name
                # Same name may have multiple tickets — reuse the guest record
                guest, created = Guest.objects.get_or_create(
                    full_name=guest_name,
                    defaults={
                        'phone_number': '',
                        'registration_source': Guest.RegistrationSource.PRE_REGISTERED,
                    }
                )

                # Create ticket with pre-generated number and token
                ticket = Ticket(
                    guest=guest,
                    event=event,
                    ticket_type=ttype,
                    status=Ticket.Status.ACTIVE,
                    is_complimentary=False,
                )
                # Bypass auto-generation — use the pre-generated values
                ticket.ticket_number = ticket_number
                ticket.qr_token      = qr_token
                ticket.save()

                imported += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  ✗ Error importing {guest_name} / {ticket_number}: {e}'
                ))
                errors += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n  ✔ Import complete!'
            f'\n    Imported : {imported}'
            f'\n    Skipped  : {skipped} (duplicates)'
            f'\n    Errors   : {errors}'
        ))
