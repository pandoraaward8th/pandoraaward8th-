"""
Management command: python manage.py create_complimentary

Creates 5 complimentary tickets:
  - 3 Regular
  - 2 VIP

These tickets scan and verify at the gate but are completely
excluded from all dashboard attendance counts.

Usage:
  python manage.py create_complimentary
  python manage.py create_complimentary --clear   # remove existing and recreate
"""

from django.core.management.base import BaseCommand, CommandError
from tickets.models import Guest, Ticket, TicketType, Event


COMPLIMENTARY_PLAN = [
    ('Regular', 3),
    ('VIP',     2),
]

PLACEHOLDER_NAME  = 'Complimentary Guest'
PLACEHOLDER_PHONE = '0000000001'


class Command(BaseCommand):
    help = 'Create 5 complimentary tickets (3 Regular + 2 VIP) hidden from dashboard counts.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing complimentary tickets and recreate them.',
        )

    def handle(self, *args, **options):
        event = Event.objects.filter(active=True).first()
        if not event:
            raise CommandError('No active event found. Run seed_data first.')

        placeholder, _ = Guest.objects.get_or_create(
            full_name=PLACEHOLDER_NAME,
            phone_number=PLACEHOLDER_PHONE,
            defaults={'registration_source': Guest.RegistrationSource.PRE_REGISTERED},
        )

        if options['clear']:
            deleted = Ticket.objects.filter(guest=placeholder).delete()
            self.stdout.write(self.style.WARNING(
                f'  Cleared {deleted[0]} existing complimentary tickets.'
            ))

        created = 0
        for type_name, count in COMPLIMENTARY_PLAN:
            ttype = TicketType.objects.filter(name=type_name).first()
            if not ttype:
                self.stdout.write(self.style.WARNING(f'  ⚠ Ticket type not found: {type_name}'))
                continue
            existing = Ticket.objects.filter(
                guest=placeholder, ticket_type=ttype, is_complimentary=True
            ).count()
            needed = count - existing
            for _ in range(needed):
                Ticket.objects.create(
                    guest=placeholder,
                    event=event,
                    ticket_type=ttype,
                    status=Ticket.Status.ACTIVE,
                    is_complimentary=True,
                )
                created += 1
            if needed > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'  ✔ Created {needed} complimentary {type_name} ticket(s)'
                ))
            else:
                self.stdout.write(f'  — {type_name}: already have {existing}/{count}')

        self.stdout.write(self.style.SUCCESS(
            f'\n  ✔ Done! {created} complimentary tickets created.'
        ))
