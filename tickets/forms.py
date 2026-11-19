"""
Pandora E-Ticket System — Forms
"""

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Guest, Ticket, Event, TicketType, UserProfile

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
MAX_PHOTO_SIZE_MB = 5


def validate_photo(file):
    if file.size > MAX_PHOTO_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Photo must be smaller than {MAX_PHOTO_SIZE_MB} MB.")
    if hasattr(file, 'content_type') and file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError("Only JPEG, PNG, WEBP or GIF images are allowed.")


# ---------------------------------------------------------------------------
# Guest + Ticket creation (pre-registered)
# ---------------------------------------------------------------------------

class GuestRegistrationForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = ['full_name', 'phone_number', 'email', 'photo']
        widgets = {
            'full_name':    forms.TextInput(attrs={'placeholder': 'Full name as it should appear on ticket'}),
            'phone_number': forms.TextInput(attrs={'placeholder': '+234... (optional)'}),
            'email':        forms.EmailInput(attrs={'placeholder': 'Optional'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone_number'].required = False

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            validate_photo(photo)
        return photo


class TicketCreateForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ['event', 'ticket_type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['event'].queryset = Event.objects.filter(active=True)
        self.fields['ticket_type'].queryset = TicketType.objects.filter(active=True)


# ---------------------------------------------------------------------------
# Walk-in registration (combined guest + ticket on one form)
# ---------------------------------------------------------------------------

class WalkInRegistrationForm(forms.Form):
    full_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'Guest full name'}),
    )
    phone_number = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+234... (optional)'}),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'Optional'}),
    )
    photo = forms.ImageField(required=False)
    event = forms.ModelChoiceField(queryset=Event.objects.filter(active=True))
    ticket_type = forms.ModelChoiceField(queryset=TicketType.objects.filter(active=True))

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            validate_photo(photo)
        return photo


# ---------------------------------------------------------------------------
# Event management
# ---------------------------------------------------------------------------

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['event_name', 'description', 'venue', 'event_date', 'event_time', 'logo', 'background', 'active']
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'event_time': forms.TimeInput(attrs={'type': 'time'}),
        }


# ---------------------------------------------------------------------------
# Ticket type management
# ---------------------------------------------------------------------------

class TicketTypeForm(forms.ModelForm):
    class Meta:
        model = TicketType
        fields = ['name', 'description', 'active']


# ---------------------------------------------------------------------------
# Staff / user management
# ---------------------------------------------------------------------------

ROLE_CHOICES = [
    ('ADMIN',      'Admin — Full Access (Register guests, manage tickets, reports)'),
    ('GATE_STAFF', 'Gate Staff — Gate 1 Venue Entrance (Verify identity only, no check-in)'),
    ('HALL_STAFF', 'Hall Staff — Gate 2 Event Hall (Verify + Check-in guests)'),
]


class StaffCreateForm(forms.Form):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(widget=forms.PasswordInput())
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        help_text='Gate 1 = venue entrance (verify only). Gate 2 = event hall (verify + check-in).'
    )

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("That username is already taken.")
        return username


class StaffEditForm(forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    is_active = forms.BooleanField(required=False)


# ---------------------------------------------------------------------------
# Verification search
# ---------------------------------------------------------------------------

class VerifyTicketForm(forms.Form):
    query = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter ticket number or phone number…',
            'class': 'form-control form-control-lg',
            'autocomplete': 'off',
            'autofocus': True,
        }),
    )


# ---------------------------------------------------------------------------
# Guest photo update
# ---------------------------------------------------------------------------

class GuestPhotoForm(forms.ModelForm):
    class Meta:
        model = Guest
        fields = ['photo']

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            validate_photo(photo)
        return photo
