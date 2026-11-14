"""
Pandora E-Ticket System — Views (all phases)
"""

import csv
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import (
    super_admin_required, ticket_admin_required,
    walkin_staff_required, verify_staff_required,
    checkin_required, admin_required,
)
from .forms import (
    GuestRegistrationForm, TicketCreateForm, WalkInRegistrationForm,
    EventForm, TicketTypeForm, StaffCreateForm, StaffEditForm,
    VerifyTicketForm, GuestPhotoForm,
)
from .models import Event, Guest, Ticket, TicketType, UserProfile, VerificationLog, ReEntryLog
from .utils import get_client_ip, generate_ticket_pdf, save_qr_to_file


# ===========================================================================
# AUTH
# ===========================================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'dashboard'))
        messages.error(request, 'Invalid username or password.')
    return render(request, 'tickets/login.html')


@login_required
def logout_view(request):
    logout(request)
    return redirect('login')


# ===========================================================================
# DASHBOARD
# ===========================================================================

@login_required
def dashboard(request):
    # Gate Staff → verify portal (Gate 1)
    # Hall Staff → check-in portal (Gate 2)
    role = request.user.profile.role
    if role == 'GATE_STAFF':
        return redirect('verify_portal')
    if role == 'HALL_STAFF':
        return redirect('checkin_portal')

    active_event = Event.objects.filter(active=True).first()

    # Exclude plain (placeholder) tickets from named counts
    plain_placeholder = Guest.objects.filter(
        full_name='Pandora Guest', phone_number='0000000000'
    ).first()

    total        = Ticket.objects.count()
    plain_total  = Ticket.objects.filter(guest=plain_placeholder).count() if plain_placeholder else 0
    named_total  = total - plain_total

    pre_reg      = Ticket.objects.filter(guest__registration_source='PRE_REGISTERED').exclude(guest=plain_placeholder).count() if plain_placeholder else Ticket.objects.filter(guest__registration_source='PRE_REGISTERED').count()
    walk_in      = Ticket.objects.filter(guest__registration_source='WALK_IN').count()
    verified     = Ticket.objects.filter(status='VERIFIED').count()
    checked_in   = Ticket.objects.filter(status='USED').count()
    not_checked_in = Ticket.objects.filter(status='ACTIVE').exclude(guest=plain_placeholder).count() if plain_placeholder else Ticket.objects.filter(status='ACTIVE').count()
    cancelled    = Ticket.objects.filter(status='CANCELLED').count()

    # Breakdown by ticket type
    breakdown = (
        TicketType.objects.filter(active=True)
        .annotate(total=Count('tickets'), used=Count('tickets', filter=Q(tickets__status='USED')))
        .values('name', 'total', 'used')
    )

    # Recent check-ins
    recent_checkins = (
        Ticket.objects.filter(status='USED')
        .select_related('guest', 'ticket_type', 'checked_in_by')
        .order_by('-checked_in_at')[:10]
    )

    ctx = {
        'active_event':    active_event,
        'total':           total,
        'plain_total':     plain_total,
        'named_total':     named_total,
        'pre_reg':         pre_reg,
        'walk_in':         walk_in,
        'verified':        verified,
        'checked_in':      checked_in,
        'not_checked_in':  not_checked_in,
        'cancelled':       cancelled,
        'breakdown':       breakdown,
        'recent_checkins': recent_checkins,
    }
    return render(request, 'tickets/dashboard.html', ctx)


# ===========================================================================
# GUEST MANAGEMENT
# ===========================================================================

@login_required
@ticket_admin_required
def guest_list(request):
    q = request.GET.get('q', '').strip()
    guests = Guest.objects.prefetch_related('tickets').order_by('-created_at')
    if q:
        guests = guests.filter(
            Q(full_name__icontains=q) | Q(phone_number__icontains=q) | Q(email__icontains=q)
        )
    return render(request, 'tickets/guest_list.html', {'guests': guests, 'q': q})


@login_required
@ticket_admin_required
def guest_create(request):
    if request.method == 'POST':
        guest_form = GuestRegistrationForm(request.POST, request.FILES)
        ticket_form = TicketCreateForm(request.POST)
        if guest_form.is_valid() and ticket_form.is_valid():
            # Save guest WITHOUT photo first to guarantee record is created
            guest = guest_form.save(commit=False)
            guest.registration_source = Guest.RegistrationSource.PRE_REGISTERED
            guest.photo = None  # Clear photo temporarily
            guest.save()

            # Now try to save photo separately — never block registration if it fails
            photo = guest_form.cleaned_data.get('photo')
            if photo:
                try:
                    guest.photo = photo
                    guest.save(update_fields=['photo'])
                except Exception:
                    messages.warning(request, "Guest saved but photo upload failed. You can upload the photo later from the guest detail page.")

            # Create ticket
            ticket = ticket_form.save(commit=False)
            ticket.guest = guest
            ticket.save()

            # Generate QR — never block if it fails
            try:
                save_qr_to_file(ticket)
            except Exception:
                pass

            messages.success(request, f"Ticket {ticket.ticket_number} created for {guest.full_name}.")
            return redirect('ticket_detail', pk=ticket.pk)
        else:
            for field, errors in guest_form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
            for field, errors in ticket_form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        guest_form = GuestRegistrationForm()
        ticket_form = TicketCreateForm()
    return render(request, 'tickets/guest_create.html', {
        'guest_form': guest_form, 'ticket_form': ticket_form,
    })


@login_required
@ticket_admin_required
def guest_detail(request, pk):
    guest = get_object_or_404(Guest, pk=pk)
    tickets = guest.tickets.select_related('event', 'ticket_type', 'checked_in_by').all()
    photo_form = GuestPhotoForm(instance=guest)
    if request.method == 'POST':
        photo_form = GuestPhotoForm(request.POST, request.FILES, instance=guest)
        if photo_form.is_valid():
            photo_form.save()
            messages.success(request, "Photo updated.")
            return redirect('guest_detail', pk=pk)
    return render(request, 'tickets/guest_detail.html', {
        'guest': guest, 'tickets': tickets, 'photo_form': photo_form,
    })


@login_required
@ticket_admin_required
def guest_delete(request, pk):
    guest = get_object_or_404(Guest, pk=pk)
    if request.method == 'POST':
        name = guest.full_name
        # Delete all related tickets and logs first
        from .models import ReEntryLog, VerificationLog
        for ticket in guest.tickets.all():
            ReEntryLog.objects.filter(ticket=ticket).delete()
            VerificationLog.objects.filter(ticket=ticket).delete()
        guest.tickets.all().delete()
        guest.delete()
        messages.success(request, f"Guest '{name}' and all their tickets have been deleted.")
        return redirect('guest_list')
    return render(request, 'tickets/guest_delete_confirm.html', {'guest': guest})


# ===========================================================================
# TICKET MANAGEMENT
# ===========================================================================

@login_required
@ticket_admin_required
def ticket_list(request):
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    tickets = Ticket.objects.select_related('guest', 'event', 'ticket_type', 'checked_in_by').order_by('-created_at')
    if q:
        tickets = tickets.filter(
            Q(ticket_number__icontains=q)
            | Q(guest__full_name__icontains=q)
            | Q(guest__phone_number__icontains=q)
        )
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    return render(request, 'tickets/ticket_list.html', {
        'tickets': tickets, 'q': q, 'status_filter': status_filter,
    })


@login_required
@ticket_admin_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(
        Ticket.objects.select_related('guest', 'event', 'ticket_type', 'checked_in_by'), pk=pk
    )
    logs = ticket.verification_logs.select_related('staff_user').order_by('-timestamp')[:20]

    # Get QR URL — works with both Cloudinary and local storage
    qr_url = None
    try:
        from django.core.files.storage import default_storage
        qr_path = f"qrcodes/{ticket.ticket_number}.png"
        if default_storage.exists(qr_path):
            qr_url = default_storage.url(qr_path)
        else:
            # Regenerate on the fly if missing
            save_qr_to_file(ticket)
            qr_url = default_storage.url(qr_path)
    except Exception:
        qr_url = None

    return render(request, 'tickets/ticket_detail.html', {
        'ticket': ticket, 'logs': logs, 'qr_url': qr_url,
    })


@login_required
def ticket_download(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    # All logged-in roles may download
    pdf_bytes = generate_ticket_pdf(ticket)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    fname = f"Pandora_Ticket_{ticket.ticket_number}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


@login_required
def ticket_view_pdf(request, pk):
    """Inline PDF view (for preview in browser)."""
    ticket = get_object_or_404(Ticket, pk=pk)
    pdf_bytes = generate_ticket_pdf(ticket)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    fname = f"Pandora_Ticket_{ticket.ticket_number}.pdf"
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response


@login_required
@ticket_admin_required
def ticket_cancel(request, pk):
    ticket = get_object_or_404(Ticket, pk=pk)
    if not request.user.profile.can_cancel_ticket:
        messages.error(request, "You do not have permission to cancel tickets.")
        return redirect('ticket_detail', pk=pk)
    if request.method == 'POST':
        if ticket.status == Ticket.Status.CANCELLED:
            messages.warning(request, "Ticket is already cancelled.")
        else:
            ticket.status = Ticket.Status.CANCELLED
            ticket.cancelled_at = timezone.now()
            ticket.save()
            VerificationLog.objects.create(
                ticket=ticket,
                staff_user=request.user,
                action=VerificationLog.Action.REJECT,
                result=VerificationLog.Result.CANCELLED,
                ip_address=get_client_ip(request),
                notes="Cancelled via admin portal.",
            )
            messages.success(request, f"Ticket {ticket.ticket_number} has been cancelled.")
        return redirect('ticket_detail', pk=pk)
    return render(request, 'tickets/ticket_cancel_confirm.html', {'ticket': ticket})


# ===========================================================================
# VERIFICATION PORTAL — Gate 1 (GATE_STAFF + ADMIN)
# ===========================================================================

@login_required
@verify_staff_required
def verify_portal(request):
    # HALL_STAFF should not be here — redirect them to check-in portal
    if request.user.profile.role == 'HALL_STAFF':
        return redirect('checkin_portal')
    form = VerifyTicketForm()
    return render(request, 'tickets/verify_portal.html', {'form': form})


# ===========================================================================
# CHECK-IN PORTAL — Gate 2 (HALL_STAFF + ADMIN only)
# ===========================================================================

@login_required
@checkin_required
def checkin_portal(request):
    """
    Gate 2 — Event Hall dashboard.
    Shows live queue of VERIFIED tickets (sent from Gate 1).
    After check-in, ticket disappears from queue and appears in checked-in list.
    Auto-refreshes every 10 seconds.
    """
    verified_queue = Ticket.objects.filter(
        status=Ticket.Status.VERIFIED
    ).select_related('guest', 'ticket_type', 'event', 'verified_by').order_by('verified_at')

    checked_in_today = Ticket.objects.filter(
        status=Ticket.Status.USED
    ).select_related('guest', 'ticket_type', 'checked_in_by').order_by('-checked_in_at')[:30]

    return render(request, 'tickets/checkin_portal.html', {
        'verified_queue': verified_queue,
        'checked_in_today': checked_in_today,
        'queue_count': verified_queue.count(),
        'checked_in_count': Ticket.objects.filter(status=Ticket.Status.USED).count(),
    })


@login_required
@verify_staff_required
@require_POST
def verify_search(request):
    """POST — search by ticket number or phone number."""
    query = request.POST.get('query', '').strip()
    if not query:
        messages.warning(request, "Please enter a ticket number or phone number.")
        return redirect('verify_portal')

    ip = get_client_ip(request)

    # Try ticket number first
    ticket = Ticket.objects.filter(ticket_number__iexact=query).select_related(
        'guest', 'event', 'ticket_type', 'checked_in_by'
    ).first()

    if ticket:
        _log_verify(ticket, request.user, ip, query)
        return _render_ticket_result(request, ticket)

    # Try phone number
    guests = Guest.objects.filter(phone_number__icontains=query).prefetch_related('tickets')
    if guests.exists():
        all_tickets = Ticket.objects.filter(guest__in=guests).select_related(
            'guest', 'event', 'ticket_type', 'checked_in_by'
        ).order_by('-created_at')
        if all_tickets.count() == 1:
            ticket = all_tickets.first()
            _log_verify(ticket, request.user, ip, query)
            return _render_ticket_result(request, ticket)
        # Multiple tickets — show selection
        for t in all_tickets:
            VerificationLog.objects.create(
                ticket=t, staff_user=request.user,
                action=VerificationLog.Action.SEARCH,
                result=VerificationLog.Result.VALID if t.is_active else VerificationLog.Result.ALREADY_USED,
                ip_address=ip, notes=f"Phone search: {query}",
            )
        return render(request, 'tickets/verify_multiple.html', {'tickets': all_tickets, 'query': query})

    # Not found
    VerificationLog.objects.create(
        ticket=None, staff_user=request.user,
        action=VerificationLog.Action.SEARCH,
        result=VerificationLog.Result.INVALID,
        ip_address=ip,
        notes=f"Not found: {query}",
    )
    return render(request, 'tickets/verify_result.html', {
        'result': 'INVALID', 'query': query,
    })


@login_required
@login_required
@verify_staff_required
def verify_by_qr(request, qr_token):
    """Called by QR scanner — token is a 32-char hex UUID."""
    ip = get_client_ip(request)
    ticket = Ticket.objects.filter(qr_token=qr_token).select_related(
        'guest', 'event', 'ticket_type', 'checked_in_by'
    ).first()

    if not ticket:
        VerificationLog.objects.create(
            ticket=None, staff_user=request.user,
            action=VerificationLog.Action.VERIFY,
            result=VerificationLog.Result.INVALID,
            ip_address=ip,
            notes=f"QR token not found: {qr_token[:16]}...",
        )
        return render(request, 'tickets/verify_result.html', {'result': 'INVALID', 'query': qr_token})

    _log_verify(ticket, request.user, ip, f"QR: {qr_token[:8]}...")
    return _render_ticket_result(request, ticket)


@login_required
@verify_staff_required
def verify_by_qr_catchall(request, raw_path):
    """
    Catchall for malformed QR paths.
    Extracts the 32-char hex token from anywhere in the path.
    Handles cases like: /verify/qr/https://domain/verify/qr/TOKEN/
    """
    import re as _re
    match = _re.search(r'[a-f0-9]{32}', raw_path)
    if match:
        return verify_by_qr(request, qr_token=match.group(0))
    ip = get_client_ip(request)
    VerificationLog.objects.create(
        ticket=None, staff_user=request.user,
        action=VerificationLog.Action.VERIFY,
        result=VerificationLog.Result.INVALID,
        ip_address=ip,
        notes=f"QR catchall — no token found in: {raw_path[:50]}",
    )
    return render(request, 'tickets/verify_result.html', {'result': 'INVALID', 'query': raw_path})


def _log_verify(ticket, user, ip, notes=''):
    if ticket.is_active or ticket.is_verified:
        result = VerificationLog.Result.VALID
    elif ticket.is_used:
        result = VerificationLog.Result.ALREADY_USED
    else:
        result = VerificationLog.Result.CANCELLED
    VerificationLog.objects.create(
        ticket=ticket, staff_user=user,
        action=VerificationLog.Action.VERIFY,
        result=result, ip_address=ip, notes=notes,
    )


def _render_ticket_result(request, ticket):
    if ticket.is_active:
        result = 'VALID'
    elif ticket.is_verified:
        result = 'VERIFIED'
    elif ticket.is_used:
        result = 'ALREADY_USED'
    else:
        result = 'CANCELLED'
    return render(request, 'tickets/verify_result.html', {
        'result': result, 'ticket': ticket,
    })


# ===========================================================================
# GATE 1 VERIFY — marks ticket VERIFIED (sends to Gate 2 queue)
# ===========================================================================

@login_required
@verify_staff_required
@require_POST
def gate1_verify(request, pk):
    """
    Gate 1 action: mark ticket as VERIFIED.
    This puts the guest in Gate 2's check-in queue.
    Ticket: ACTIVE → VERIFIED
    """
    ip = get_client_ip(request)
    with transaction.atomic():
        ticket = get_object_or_404(
            Ticket.objects.select_for_update().select_related('guest', 'event', 'ticket_type'),
            pk=pk
        )
        if ticket.status != Ticket.Status.ACTIVE:
            # Already verified, used or cancelled
            return _render_ticket_result(request, ticket)

        ticket.status = Ticket.Status.VERIFIED
        ticket.verified_at = timezone.now()
        ticket.verified_by = request.user
        ticket.save()

        VerificationLog.objects.create(
            ticket=ticket, staff_user=request.user,
            action=VerificationLog.Action.VERIFY,
            result=VerificationLog.Result.VALID,
            ip_address=ip,
            notes="Gate 1 verified — sent to Gate 2 queue.",
        )

    return render(request, 'tickets/gate1_verified.html', {'ticket': ticket})


# ===========================================================================
# CHECK-IN  (atomic — prevents double check-in)
# ===========================================================================

@login_required
@checkin_required
@require_POST
def checkin(request, pk):
    ip = get_client_ip(request)
    with transaction.atomic():
        # select_for_update locks the row until commit
        ticket = get_object_or_404(
            Ticket.objects.select_for_update().select_related('guest', 'event', 'ticket_type'),
            pk=pk
        )
        if ticket.status not in (Ticket.Status.ACTIVE, Ticket.Status.VERIFIED):
            # Already used or cancelled — reject
            VerificationLog.objects.create(
                ticket=ticket, staff_user=request.user,
                action=VerificationLog.Action.CHECK_IN,
                result=VerificationLog.Result.ALREADY_USED if ticket.is_used else VerificationLog.Result.CANCELLED,
                ip_address=ip, notes="Duplicate check-in attempt blocked.",
            )
            return render(request, 'tickets/verify_result.html', {
                'result': 'ALREADY_USED' if ticket.is_used else 'CANCELLED',
                'ticket': ticket,
            })

        ticket.status = Ticket.Status.USED
        ticket.checked_in_at = timezone.now()
        ticket.checked_in_by = request.user
        ticket.save()

        VerificationLog.objects.create(
            ticket=ticket, staff_user=request.user,
            action=VerificationLog.Action.CHECK_IN,
            result=VerificationLog.Result.VALID,
            ip_address=ip, notes="Guest checked in successfully.",
        )

    # Hall Staff go back to Gate 2 dashboard (queue updates automatically)
    # Admin and Gate Staff see the success page
    if request.user.profile.role == 'HALL_STAFF':
        messages.success(request, f"✅ {ticket.guest.full_name} checked in.")
        return redirect('checkin_portal')

    return render(request, 'tickets/checkin_success.html', {'ticket': ticket})


# ===========================================================================
# WALK-IN REGISTRATION
# ===========================================================================

@login_required
@checkin_required
@require_POST
def approve_reentry(request, pk):
    """
    Approve re-entry for a guest whose ticket is already USED.
    Logs the re-entry with timestamp + staff name.
    Ticket status stays USED — just records the authorised re-entry.
    Only HALL_STAFF and ADMIN can approve.
    """
    ticket = get_object_or_404(
        Ticket.objects.select_related('guest', 'event', 'ticket_type'),
        pk=pk
    )
    ip = get_client_ip(request)

    ReEntryLog.objects.create(
        ticket=ticket,
        approved_by=request.user,
        ip_address=ip,
        notes=f"Re-entry approved at Gate 2",
    )

    # Also log in verification log
    VerificationLog.objects.create(
        ticket=ticket,
        staff_user=request.user,
        action=VerificationLog.Action.CHECK_IN,
        result=VerificationLog.Result.VALID,
        ip_address=ip,
        notes=f"RE-ENTRY approved by {request.user.get_full_name() or request.user.username}",
    )

    return render(request, 'tickets/reentry_success.html', {'ticket': ticket})


@login_required
@walkin_staff_required
def walkin_register(request):
    if request.method == 'POST':
        form = WalkInRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            # Save guest without photo first to guarantee record
            guest = Guest.objects.create(
                full_name=form.cleaned_data['full_name'],
                phone_number=form.cleaned_data['phone_number'],
                email=form.cleaned_data.get('email', ''),
                registration_source=Guest.RegistrationSource.WALK_IN,
            )
            # Try photo separately
            photo = form.cleaned_data.get('photo')
            if photo:
                try:
                    guest.photo = photo
                    guest.save(update_fields=['photo'])
                except Exception:
                    messages.warning(request, "Guest saved but photo upload failed.")

            ticket = Ticket.objects.create(
                guest=guest,
                event=form.cleaned_data['event'],
                ticket_type=form.cleaned_data['ticket_type'],
            )
            try:
                save_qr_to_file(ticket)
            except Exception:
                pass

            messages.success(request, f"Walk-in ticket {ticket.ticket_number} generated for {guest.full_name}.")
            return redirect('verify_result_direct', pk=ticket.pk)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = WalkInRegistrationForm()
    return render(request, 'tickets/walkin_register.html', {'form': form})


@login_required
@login_required
@verify_staff_required
def verify_result_direct(request, pk):
    """Show verify result for a freshly generated walk-in ticket.
    Result is derived from actual ticket status — never hardcoded."""
    ticket = get_object_or_404(
        Ticket.objects.select_related('guest', 'event', 'ticket_type', 'checked_in_by'), pk=pk
    )
    # Derive result from real ticket status — fixes hardcoded VALID bypass
    if ticket.is_active:
        result = 'VALID'
    elif ticket.is_used:
        result = 'ALREADY_USED'
    else:
        result = 'CANCELLED'
    return render(request, 'tickets/verify_result.html', {
        'result': result, 'ticket': ticket,
    })


# ===========================================================================
# EVENTS
# ===========================================================================

@login_required
@super_admin_required
def event_list(request):
    events = Event.objects.all()
    return render(request, 'tickets/event_list.html', {'events': events})


@login_required
@super_admin_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Event created.")
            return redirect('event_list')
    else:
        form = EventForm()
    return render(request, 'tickets/event_form.html', {'form': form, 'title': 'New Event'})


@login_required
@super_admin_required
def event_edit(request, pk):
    event = get_object_or_404(Event, pk=pk)
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated.")
            return redirect('event_list')
    else:
        form = EventForm(instance=event)
    return render(request, 'tickets/event_form.html', {'form': form, 'title': 'Edit Event'})


# ===========================================================================
# TICKET TYPES
# ===========================================================================

@login_required
@super_admin_required
def tickettype_list(request):
    types = TicketType.objects.all()
    return render(request, 'tickets/tickettype_list.html', {'types': types})


@login_required
@super_admin_required
def tickettype_create(request):
    if request.method == 'POST':
        form = TicketTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Ticket type created.")
            return redirect('tickettype_list')
    else:
        form = TicketTypeForm()
    return render(request, 'tickets/tickettype_form.html', {'form': form, 'title': 'New Ticket Type'})


@login_required
@super_admin_required
def tickettype_edit(request, pk):
    tt = get_object_or_404(TicketType, pk=pk)
    if request.method == 'POST':
        form = TicketTypeForm(request.POST, instance=tt)
        if form.is_valid():
            form.save()
            messages.success(request, "Ticket type updated.")
            return redirect('tickettype_list')
    else:
        form = TicketTypeForm(instance=tt)
    return render(request, 'tickets/tickettype_form.html', {'form': form, 'title': 'Edit Ticket Type'})


# ===========================================================================
# STAFF / USER MANAGEMENT
# ===========================================================================

@login_required
@super_admin_required
def staff_list(request):
    profiles = UserProfile.objects.select_related('user').order_by('user__username')
    return render(request, 'tickets/staff_list.html', {'profiles': profiles})


@login_required
@super_admin_required
def staff_create(request):
    if request.method == 'POST':
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=form.cleaned_data.get('email', ''),
            )
            # Use update_or_create — signal may have already created the profile
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'role': form.cleaned_data['role']}
            )
            messages.success(request, f"Staff account '{user.username}' created.")
            return redirect('staff_list')
    else:
        form = StaffCreateForm()
    return render(request, 'tickets/staff_form.html', {'form': form, 'title': 'Create Staff Account'})


@login_required
@super_admin_required
def staff_edit(request, pk):
    # Look up by User pk
    user = get_object_or_404(User, pk=pk)
    profile = get_object_or_404(UserProfile, user=user)
    if request.method == 'POST':
        form = StaffEditForm(request.POST)
        if form.is_valid():
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.email = form.cleaned_data.get('email', '')
            user.is_active = form.cleaned_data.get('is_active', True)
            user.save()
            profile.role = form.cleaned_data['role']
            profile.save()
            messages.success(request, "Staff account updated.")
            return redirect('staff_list')
    else:
        form = StaffEditForm(initial={
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'role': profile.role,
            'is_active': user.is_active,
        })
    return render(request, 'tickets/staff_form.html', {'form': form, 'title': 'Edit Staff Account', 'profile': profile})


@login_required
@super_admin_required
def staff_delete(request, pk):
    # Look up by User pk — more stable than UserProfile pk
    user = get_object_or_404(User, pk=pk)

    # Prevent admin from deleting their own account
    if user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('staff_list')

    try:
        profile = user.profile
    except Exception:
        profile = None

    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f"Staff account '{username}' has been deleted.")
        return redirect('staff_list')

    return render(request, 'tickets/staff_delete_confirm.html', {
        'profile': profile, 'user_obj': user
    })



# ===========================================================================
# REPORTS
# ===========================================================================

@login_required
@ticket_admin_required
def reports(request):
    tickets = Ticket.objects.select_related(
        'guest', 'event', 'ticket_type', 'checked_in_by'
    ).order_by('-created_at')

    # Filters
    source_filter = request.GET.get('source', '')
    status_filter = request.GET.get('status', '')
    ttype_filter = request.GET.get('ticket_type', '')

    if source_filter:
        tickets = tickets.filter(guest__registration_source=source_filter)
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if ttype_filter:
        tickets = tickets.filter(ticket_type__name__iexact=ttype_filter)

    ticket_types = TicketType.objects.filter(active=True)
    return render(request, 'tickets/reports.html', {
        'tickets': tickets,
        'source_filter': source_filter,
        'status_filter': status_filter,
        'ttype_filter': ttype_filter,
        'ticket_types': ticket_types,
    })


@login_required
@ticket_admin_required
def reports_export_csv(request):
    tickets = Ticket.objects.select_related(
        'guest', 'event', 'ticket_type', 'checked_in_by'
    ).order_by('-created_at')

    source_filter = request.GET.get('source', '').strip()
    status_filter = request.GET.get('status', '').strip()
    ttype_filter  = request.GET.get('ticket_type', '').strip()

    if source_filter:
        tickets = tickets.filter(guest__registration_source=source_filter)
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if ttype_filter:
        tickets = tickets.filter(ticket_type__name__iexact=ttype_filter)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="pandora_tickets_report.csv"'
    # UTF-8 BOM so Excel opens it correctly
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'Guest Name', 'Phone Number', 'Email',
        'Ticket Number', 'Ticket Type', 'Registration Source',
        'Event', 'Status', 'Issued At', 'Verified At',
        'Check-In Time', 'Checked In By',
    ])

    for t in tickets:
        writer.writerow([
            t.guest.full_name,
            t.guest.phone_number,
            t.guest.email or '',
            t.ticket_number,
            t.ticket_type.name,
            t.guest.get_registration_source_display(),
            t.event.event_name,
            t.get_status_display(),
            t.issued_at.strftime('%Y-%m-%d %H:%M') if t.issued_at else '',
            t.verified_at.strftime('%Y-%m-%d %H:%M') if t.verified_at else '',
            t.checked_in_at.strftime('%Y-%m-%d %H:%M') if t.checked_in_at else '',
            t.checked_in_by.get_full_name() or t.checked_in_by.username if t.checked_in_by else '',
        ])

    return response


# ===========================================================================
# VERIFICATION LOG
# ===========================================================================

@login_required
@admin_required
def clear_attendance(request):
    """
    Clear all guests, tickets and logs.
    Only Super Admin can do this. Requires POST confirmation.
    """
    if request.method == 'POST':
        from .models import ReEntryLog
        ReEntryLog.objects.all().delete()
        VerificationLog.objects.all().delete()
        Ticket.objects.all().delete()
        Guest.objects.all().delete()
        messages.success(request, "All guests, tickets and logs have been cleared.")
        return redirect('reports')
    return render(request, 'tickets/clear_attendance_confirm.html')


@login_required
@ticket_admin_required
def verification_log(request):
    logs = VerificationLog.objects.select_related('ticket', 'staff_user').order_by('-timestamp')[:200]
    reentry_logs = ReEntryLog.objects.select_related('ticket', 'approved_by').order_by('-timestamp')[:50]
    return render(request, 'tickets/verification_log.html', {
        'logs': logs,
        'reentry_logs': reentry_logs,
    })


# ===========================================================================
# PLAIN TICKETS — BULK DOWNLOAD (PNG ZIP)
# ===========================================================================

@login_required
@ticket_admin_required
def download_plain_tickets(request):
    """
    Generate PNG ticket images for all plain tickets (linked to the
    'Pandora Guest' placeholder) and return them as a ZIP file.
    Each PNG has the ticket background + QR code, no personal info.
    """
    import io as _io
    import os as _os
    import zipfile as _zipfile

    import qrcode as _qrcode
    from PIL import Image as _Image
    from django.conf import settings as _settings

    SITE_URL = 'https://pandoraaward8th.onrender.com'
    IMG_DIR  = _os.path.join(_settings.BASE_DIR, 'static', 'img')

    # QR overlay config per ticket type background
    QR_CFG = {
        'REGULAR (1).PNG':                         {'qr_cx_pct': 0.858, 'qr_cy_pct': 0.607, 'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140},
        'VIP.jpeg':                                {'qr_cx_pct': 0.870, 'qr_cy_pct': 0.607, 'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140},
        'Pandora Awards Table for Ten Ticket.png': {'qr_cx_pct': 0.870, 'qr_cy_pct': 0.607, 'qr_w_pct': 0.1384, 'qr_h_pct': 0.2140},
    }

    # Ticket type → background mapping
    TYPE_BG = {
        'Regular':       'REGULAR (1).PNG',
        'VIP':           'VIP.jpeg',
        'Table of Ten':  'Pandora Awards Table for Ten Ticket.png',
    }

    # Get plain tickets — filtered by type if specified
    placeholder = Guest.objects.filter(full_name='Pandora Guest', phone_number='0000000000').first()
    if not placeholder:
        messages.error(request, 'No plain tickets found. Run generate_plain_tickets first.')
        return redirect('dashboard')

    type_filter = request.GET.get('type', '').strip()
    tickets = Ticket.objects.filter(guest=placeholder).select_related('ticket_type').order_by('ticket_number')
    if type_filter:
        tickets = tickets.filter(ticket_type__name=type_filter)

    if not tickets.exists():
        messages.error(request, f'No plain tickets found{" for type: " + type_filter if type_filter else ""}.')
        return redirect('dashboard')

    zip_name = f"Pandora_{type_filter.replace(' ', '_')}_Tickets.zip" if type_filter else "Pandora_Plain_Tickets.zip"

    # Build ZIP in memory
    buf = _io.BytesIO()
    zf = _zipfile.ZipFile(buf, 'w', _zipfile.ZIP_DEFLATED)

    count = 0
    for ticket in tickets:
        ttype_name = ticket.ticket_type.name
        bg_file = TYPE_BG.get(ttype_name, 'REGULAR (1).PNG')
        bg_path = _os.path.join(IMG_DIR, bg_file)

        if not _os.path.exists(bg_path):
            # Skip if background missing
            continue

        cfg = QR_CFG.get(bg_file, QR_CFG['REGULAR (1).PNG'])

        # Load background
        bg = _Image.open(bg_path).convert('RGBA')
        w, h = bg.size

        # QR dimensions
        qr_w = int(w * cfg['qr_w_pct'])
        qr_h = int(h * cfg['qr_h_pct'])
        qr_size = min(qr_w, qr_h)

        # QR position (centre)
        qr_cx = int(w * cfg['qr_cx_pct'])
        qr_cy = int(h * cfg['qr_cy_pct'])
        qr_x = qr_cx - qr_size // 2
        qr_y = qr_cy - qr_size // 2

        # Generate QR code
        verify_url = f"{SITE_URL}/verify/qr/{ticket.qr_token}/"
        qr = _qrcode.QRCode(
            version=1,
            error_correction=_qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=2,
        )
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
        qr_img = qr_img.resize((qr_size, qr_size), _Image.LANCZOS)

        # Paste QR onto background
        bg.paste(qr_img, (qr_x, qr_y))

        # Save to ZIP
        folder = ttype_name.replace(' ', '_')
        arcname = f"{folder}/{ticket.ticket_number}.png"

        img_bytes = _io.BytesIO()
        bg.convert('RGB').save(img_bytes, 'PNG', dpi=(300, 300))
        img_bytes.seek(0)
        zf.writestr(arcname, img_bytes.getvalue())

        count += 1

    zf.close()
    buf.seek(0)

    response = HttpResponse(buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_name}"'
    return response


@login_required
@ticket_admin_required
def export_plain_ticket_tokens(request):
    """
    Export a lightweight CSV of all plain ticket numbers + QR tokens + serial numbers.
    Serial numbers: REG-001..200, VIP-001..100, TBL-001..040
    """
    placeholder = Guest.objects.filter(
        full_name='Pandora Guest', phone_number='0000000000'
    ).first()
    if not placeholder:
        messages.error(request, 'No plain tickets found.')
        return redirect('dashboard')

    # Serial prefix per type
    PREFIX = {
        'Regular':      'REG',
        'VIP':          'VIP',
        'Table of Ten': 'TBL',
    }

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="render_ticket_tokens.csv"'

    writer = csv.writer(response)
    writer.writerow(['ticket_number', 'qr_token', 'ticket_type', 'serial_number'])

    # Group by type, assign serial numbers in order
    for type_name, prefix in PREFIX.items():
        tickets = Ticket.objects.filter(
            guest=placeholder, ticket_type__name=type_name
        ).order_by('id')
        for i, t in enumerate(tickets, start=1):
            serial = f"{prefix}-{i:03d}"
            writer.writerow([t.ticket_number, t.qr_token, t.ticket_type.name, serial])

    return response
