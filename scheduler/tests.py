import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Service, Practitioner, Availability, Appointment

User = get_user_model()

class SchedulerTestCase(TestCase):
    def setUp(self):
        # Create a client, a practitioner, and a manager
        self.client_user = User.objects.create_user(
            username='johndoe', email='john@example.com', password='password123',
            first_name='John', last_name='Doe', role='client'
        )
        self.pract_user = User.objects.create_user(
            username='drsmith', email='smith@example.com', password='password123',
            first_name='Dr. Jane', last_name='Smith', role='practitioner'
        )
        self.practitioner = Practitioner.objects.create(
            user=self.pract_user, bio="Expert massage therapist and skin care specialist."
        )
        
        # Create Services
        self.massage = Service.objects.create(
            name="Deep Tissue Massage", description="60 mins massage",
            duration_minutes=60, price=95.00
        )
        self.facial = Service.objects.create(
            name="Facial Treatment", description="45 mins facial",
            duration_minutes=45, price=75.00
        )

        # Associate service with practitioner
        self.practitioner.specialties.add(self.massage)
        # Note: self.practitioner does NOT provide self.facial

        # Set Availability for practitioner: Mondays 09:00 - 17:00
        # Let's say Monday is day_of_week=0.
        self.availability = Availability.objects.create(
            practitioner=self.practitioner,
            day_of_week=0,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0)
        )

    def test_user_roles(self):
        self.assertEqual(self.client_user.role, 'client')
        self.assertEqual(self.pract_user.role, 'practitioner')
        self.assertEqual(self.practitioner.user, self.pract_user)

    def test_availability_validation_time_order(self):
        # Start time must be before end time
        avail = Availability(
            practitioner=self.practitioner,
            day_of_week=1,
            start_time=datetime.time(17, 0),
            end_time=datetime.time(9, 0)
        )
        with self.assertRaises(ValidationError):
            avail.save()

    def test_availability_validation_overlap(self):
        # Create an overlapping availability slot on the same day (Monday)
        # Existing is 09:00 - 17:00. Overlap attempts: 10:00 - 12:00
        avail = Availability(
            practitioner=self.practitioner,
            day_of_week=0,
            start_time=datetime.time(10, 0),
            end_time=datetime.time(12, 0)
        )
        with self.assertRaises(ValidationError):
            avail.save()

    def test_appointment_booking_success(self):
        # Book on a Monday in the future
        # Let's find the next Monday
        today = datetime.date.today()
        # weekday() on Monday is 0
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            # If today is Monday, book next week's Monday to ensure it is in the future
            days_until_monday = 7
        booking_date = today + datetime.timedelta(days=days_until_monday)

        appt = Appointment(
            client=self.client_user,
            practitioner=self.practitioner,
            service=self.massage,
            date=booking_date,
            start_time=datetime.time(10, 0) # 10:00 - 11:00
        )
        # Should save without raising errors
        appt.save()
        self.assertEqual(appt.end_time, datetime.time(11, 0))
        self.assertEqual(appt.status, 'confirmed')

    def test_appointment_outside_working_hours(self):
        today = datetime.date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        booking_date = today + datetime.timedelta(days=days_until_monday)

        # Practitioner availability is Monday 09:00 - 17:00
        # Try booking at 19:00
        appt = Appointment(
            client=self.client_user,
            practitioner=self.practitioner,
            service=self.massage,
            date=booking_date,
            start_time=datetime.time(19, 0)
        )
        with self.assertRaises(ValidationError):
            appt.save()

    def test_appointment_unsupported_service(self):
        today = datetime.date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        booking_date = today + datetime.timedelta(days=days_until_monday)

        # Facial is not offered by self.practitioner
        appt = Appointment(
            client=self.client_user,
            practitioner=self.practitioner,
            service=self.facial,
            date=booking_date,
            start_time=datetime.time(10, 0)
        )
        with self.assertRaises(ValidationError):
            appt.save()

    def test_appointment_booking_overlap(self):
        today = datetime.date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        booking_date = today + datetime.timedelta(days=days_until_monday)

        # Book first appointment: 10:00 - 11:00
        appt1 = Appointment.objects.create(
            client=self.client_user,
            practitioner=self.practitioner,
            service=self.massage,
            date=booking_date,
            start_time=datetime.time(10, 0)
        )

        # Try booking second overlapping appointment at 10:30
        appt2 = Appointment(
            client=self.client_user,
            practitioner=self.practitioner,
            service=self.massage,
            date=booking_date,
            start_time=datetime.time(10, 30)
        )
        with self.assertRaises(ValidationError):
            appt2.save()

        # Try booking a non-overlapping appointment: 11:00 - 12:00
        appt3 = Appointment(
            client=self.client_user,
            practitioner=self.practitioner,
            service=self.massage,
            date=booking_date,
            start_time=datetime.time(11, 0)
        )
        appt3.save() # Should not raise
        self.assertEqual(appt3.end_time, datetime.time(12, 0))

    def test_notification_creation_and_api(self):
        # Create a notification
        from .models import Notification
        notif = Notification.objects.create(
            user=self.client_user,
            message="Test Notification Alert"
        )
        self.assertEqual(notif.is_read, False)
        self.assertEqual(notif.message, "Test Notification Alert")
        
        # Test API views via client login
        self.client.login(username='johndoe', password='password123')
        
        # Fetch notifications
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['notifications']), 1)
        self.assertEqual(data['notifications'][0]['message'], "Test Notification Alert")
        
        # Mark read
        response_read = self.client.post('/api/notifications/read/')
        self.assertEqual(response_read.status_code, 200)
        
        # Unread notifications count should be 0 now
        response2 = self.client.get('/api/notifications/')
        self.assertEqual(len(response2.json()['notifications']), 0)

