"""
Management command: python manage.py seed_data
Seeds the Pandora Awards 8th Edition event, ticket types,
and creates a default superadmin account.
"""

import datetime
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from tickets.models import Event, TicketType, UserProfile


class Command(BaseCommand):
    help = 'Seed Pandora Awards 8th Edition event data and default admin account.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('Seeding Pandora Awards 8th Edition data...'))

        # ── Event ──────────────────────────────────────────────────────────
        event, created = Event.objects.get_or_create(
            event_name='Pandora Awards 8th Edition',
            defaults={
                'description': (
                    'An unforgettable evening of celebration, recognition, glamour and excellence. '
                    'Pandora Awards 2026 — Live in Abuja. 🏆✨'
                ),
                'venue': 'A Class Event Center, Sapphire Hall, Along Kashmiri Ibrahim Way, Maitama, Abuja',
                'event_date': datetime.date(2026, 11, 29),
                'event_time': datetime.time(16, 0),   # Red carpet 4 PM
                'active': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('  ✔ Event created: Pandora Awards 8th Edition'))
        else:
            self.stdout.write('  — Event already exists.')

        # ── Ticket types ───────────────────────────────────────────────────
        types = [
            ('Regular',             'Standard event admission — Red Carpet from 4 PM'),
            ('VIP',                 'VIP admission with premium seating'),
            ('Special Guest Seat',  'Exclusive Special Guest Seat with premium privileges'),
            ('Table of Ten',         'Exclusive Table for 10 guests — ₦800,000'),
        ]
        for name, desc in types:
            tt, created = TicketType.objects.get_or_create(name=name, defaults={'description': desc, 'active': True})
            if created:
                self.stdout.write(self.style.SUCCESS(f'  ✔ Ticket type: {name}'))
            else:
                self.stdout.write(f'  — Ticket type already exists: {name}')

        # Deactivate/delete Media and Staff ticket types
        from tickets.models import TicketType as TT
        for remove_name in ['Media', 'Staff']:
            TT.objects.filter(name=remove_name).update(active=False)
            self.stdout.write(f'  — Deactivated ticket type: {remove_name}')

        # Rename Gold Table → Table of Ten (only if Table of Ten doesn't exist yet)
        from tickets.models import TicketType as TT
        if not TT.objects.filter(name='Table of Ten').exists():
            TT.objects.filter(name='Gold Table').update(name='Table of Ten')
            self.stdout.write(self.style.SUCCESS('  ✔ Renamed: Gold Table → Table of Ten'))
        else:
            # Table of Ten exists — just deactivate any leftover Gold Table
            TT.objects.filter(name='Gold Table').update(active=False)
            self.stdout.write('  — Table of Ten already exists.')

        # ── Super admin account ────────────────────────────────────────────
        if not User.objects.filter(username='Admin').exists():
            user = User.objects.create_superuser(
                username='Admin',
                password='Admin1234@',
                first_name='Pandora',
                last_name='Administrator',
                email='info.pandoraawards@gmail.com',
            )
            # Signal will create profile, update role to SUPER_ADMIN
            try:
                user.profile.role = UserProfile.Role.ADMIN
                user.profile.save()
            except Exception:
                UserProfile.objects.create(user=user, role=UserProfile.Role.ADMIN)
            self.stdout.write(self.style.SUCCESS(
                '  ✔ Super admin created — username: Admin  password: Admin1234@'
            ))
            self.stdout.write(self.style.WARNING(
                '  ⚠  CHANGE THIS PASSWORD immediately after first login!'
            ))
        else:
            self.stdout.write('  — Admin account already exists.')

        # ── Plain tickets (no personal info) ──────────────────────────────
        self._seed_plain_tickets()

        self.stdout.write(self.style.SUCCESS('\nSeed complete. 🏆'))

    def _seed_plain_tickets(self):
        """Create plain tickets linked to a placeholder guest."""
        from tickets.models import Guest, Ticket

        PLAN = [
            ('Regular',            200),
            ('VIP',                150),
            ('Special Guest Seat',   70),
        ]

        placeholder, created = Guest.objects.get_or_create(
            full_name='Pandora Guest',
            phone_number='0000000000',
            defaults={'registration_source': Guest.RegistrationSource.PRE_REGISTERED},
        )

        event = Event.objects.filter(active=True).first()
        if not event:
            return

        total_created = 0
        for type_name, count in PLAN:
            ttype = TicketType.objects.filter(name=type_name).first()
            if not ttype:
                continue
            existing = Ticket.objects.filter(guest=placeholder, ticket_type=ttype).count()
            needed = count - existing
            for _ in range(needed):
                Ticket.objects.create(
                    guest=placeholder,
                    event=event,
                    ticket_type=ttype,
                    status=Ticket.Status.ACTIVE,
                )
                total_created += 1
            if needed > 0:
                self.stdout.write(self.style.SUCCESS(
                    f'  ✔ Created {needed} {type_name} plain tickets'
                ))
            else:
                self.stdout.write(f'  — {type_name}: already have {existing}/{count}')

        if total_created:
            self.stdout.write(self.style.SUCCESS(
                f'  ✔ {total_created} new plain tickets created'
            ))
