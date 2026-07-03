import datetime
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    ROLE_CHOICES = (
        ('client', 'Client'),
        ('practitioner', 'Practitioner'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role.capitalize()})"


class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(help_text="Duration in minutes")
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} - {self.duration_minutes} mins (${self.price})"


class Practitioner(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, limit_choices_to={'role': 'practitioner'})
    bio = models.TextField(blank=True)
    specialties = models.ManyToManyField(Service, related_name='practitioners', blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class Availability(models.Model):
    DAY_CHOICES = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )
    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE, related_name='availabilities')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name_plural = "Availabilities"
        ordering = ['day_of_week', 'start_time']

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(_("Start time must be before end time."))
        
        # Check for overlapping availability blocks
        overlaps = Availability.objects.filter(
            practitioner=self.practitioner,
            day_of_week=self.day_of_week
        ).exclude(pk=self.pk)
        
        for p in overlaps:
            if not (self.end_time <= p.start_time or self.start_time >= p.end_time):
                raise ValidationError(_("This availability block overlaps with an existing block."))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.practitioner} - {self.get_day_of_week_display()} ({self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')})"


class Appointment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled_by_client', 'Cancelled by Client'),
        ('cancelled_by_practitioner', 'Cancelled by Practitioner'),
    )
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='appointments_as_client', limit_choices_to={'role': 'client'})
    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE, related_name='appointments_as_practitioner')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(blank=True, help_text="Automatically calculated based on service duration")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']

    def clean(self):
        # 1. Start time before end time (if manually provided)
        # Calculate End Time if not set
        if self.start_time and self.service:
            duration = datetime.timedelta(minutes=self.service.duration_minutes)
            # convert start_time to datetime to add duration
            dummy_dt = datetime.datetime.combine(self.date or datetime.date.today(), self.start_time)
            self.end_time = (dummy_dt + duration).time()
        
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError(_("Start time must be before end time."))

        # 2. Date in the past check (except for updates which are already saved)
        if not self.pk and self.date and self.date < datetime.date.today():
            raise ValidationError(_("Cannot book appointments in the past."))

        # 3. Check if practitioner is active and offers this service
        if self.practitioner and self.service:
            if not self.practitioner.specialties.filter(pk=self.service.pk).exists():
                raise ValidationError(_(f"Practitioner {self.practitioner} does not offer service '{self.service.name}'."))

        # 4. Check if date/time fits practitioner's Availabilities
        if self.date and self.start_time and self.end_time and self.practitioner:
            day_num = self.date.weekday()
            availabilities = Availability.objects.filter(
                practitioner=self.practitioner,
                day_of_week=day_num
            )
            
            fits_in_slot = False
            for avail in availabilities:
                if self.start_time >= avail.start_time and self.end_time <= avail.end_time:
                    fits_in_slot = True
                    break
            
            if not fits_in_slot:
                raise ValidationError(_("The requested time is outside the practitioner's working hours for this day."))

        # 5. Overlap detection (exclude any cancelled-type status)
        if self.date and self.start_time and self.end_time and self.practitioner:
            cancelled_statuses = ['cancelled_by_client', 'cancelled_by_practitioner']
            overlaps = Appointment.objects.filter(
                practitioner=self.practitioner,
                date=self.date
            ).exclude(status__in=cancelled_statuses).exclude(pk=self.pk)
            
            for appt in overlaps:
                if not (self.end_time <= appt.start_time or self.start_time >= appt.end_time):
                    raise ValidationError(_("The practitioner is already booked during this time."))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client} with {self.practitioner} - {self.service.name} ({self.date} {self.start_time.strftime('%H:%M')})"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:30]}"

