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


class AvailabilityForm(forms.Form):
    days_of_week = forms.MultipleChoiceField(
        choices=Availability.DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'days-checkbox-list'}),
        label="Days of Week",
        required=True
    )
    
    # 30-minute time intervals from 00:00 to 23:30
    TIME_CHOICES = [(f"{h:02d}:{m:02d}:00", f"{h:02d}:{m:02d}") for h in range(24) for m in (0, 30)]
    
    start_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
        initial='09:00:00'
    )
    end_time = forms.ChoiceField(
        choices=TIME_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
        initial='17:00:00'
    )

    def __init__(self, *args, **kwargs):
        self.practitioner = kwargs.pop('practitioner', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_str = cleaned_data.get('start_time')
        end_str = cleaned_data.get('end_time')
        
        if start_str and end_str:
            import datetime
            try:
                start_t = datetime.datetime.strptime(start_str, '%H:%M:%S').time()
                end_t = datetime.datetime.strptime(end_str, '%H:%M:%S').time()
                if start_t >= end_t:
                    raise forms.ValidationError("Start time must be before end time.")
            except ValueError:
                pass
        return cleaned_data



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
