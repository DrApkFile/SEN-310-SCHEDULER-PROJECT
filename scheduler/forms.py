from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Availability, Appointment, Service, Practitioner

class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(
        choices=(('client', 'Client'), ('practitioner', 'Practitioner')),
        required=True,
        help_text="Register as a Client (to book services) or Practitioner (to offer services)."
    )
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    phone_number = forms.CharField(max_length=20, required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('first_name', 'last_name', 'email', 'role', 'phone_number')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = self.cleaned_data['role']
        user.phone_number = self.cleaned_data['phone_number']
        if commit:
            user.save()
            if user.role == 'practitioner':
                # Create corresponding Practitioner record automatically
                Practitioner.objects.get_or_create(user=user)
        return user


class AvailabilityForm(forms.ModelModelForm if hasattr(forms, 'ModelModelForm') else forms.ModelForm):
    class Meta:
        model = Availability
        fields = ['day_of_week', 'start_time', 'end_time']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-input'}),
            'day_of_week': forms.Select(attrs={'class': 'form-input'})
        }

    def __init__(self, *args, **kwargs):
        self.practitioner = kwargs.pop('practitioner', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.practitioner:
            instance.practitioner = self.practitioner
        if commit:
            instance.save()
        return instance


class AppointmentForm(forms.ModelForm):
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input', 'id': 'booking-date'}),
        help_text="Select a date for your appointment."
    )
    start_time = forms.TimeField(
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-input', 'id': 'booking-time'}),
        help_text="Select a start files slot."
    )

    class Meta:
        model = Appointment
        fields = ['service', 'practitioner', 'date', 'start_time', 'notes']
        widgets = {
            'service': forms.Select(attrs={'class': 'form-input', 'id': 'booking-service'}),
            'practitioner': forms.Select(attrs={'class': 'form-input', 'id': 'booking-practitioner'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Any special requests or details...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Load all services and practitioners
        self.fields['service'].queryset = Service.objects.all()
        self.fields['practitioner'].queryset = Practitioner.objects.all()
