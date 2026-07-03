import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Sum, Count

from .models import User, Service, Practitioner, Availability, Appointment
from .forms import SignUpForm, AvailabilityForm, AppointmentForm

def landing(request):
    services = Service.objects.all()
    # Check if there are no services, populate default mock ones for demo purposes
    if not services.exists():
        s1 = Service.objects.create(name="Deep Tissue Massage", description="Relieve chronic muscle tension with deep, targeted pressure.", duration_minutes=60, price=95.00)
        s2 = Service.objects.create(name="Acupuncture & Relaxation", description="Balance your energy flow and promote physical healing.", duration_minutes=75, price=110.00)
        s3 = Service.objects.create(name="Hydrating Facial", description="Cleanse, steam, exfoliate and hydrate your skin for a healthy glow.", duration_minutes=45, price=75.00)
        s4 = Service.objects.create(name="Private Yoga Session", description="Customized yoga instructions tailored to your experience and goals.", duration_minutes=60, price=80.00)
        services = Service.objects.all()
        
    return render(request, 'scheduler/landing.html', {'services': services})


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to Solace Wellness Spot, {user.first_name}!")
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'scheduler/register.html', {'form': form})


@login_required
def dashboard(request):
    user = request.user
    # Superuser / admin check must come FIRST — createsuperuser leaves role='client' by default
    if user.is_superuser or user.role == 'admin':
        return redirect('manager_dashboard')
    if user.role == 'client':
        cancelled_statuses = ['cancelled_by_client', 'cancelled_by_practitioner']
        upcoming_appointments = Appointment.objects.filter(
            client=user, date__gte=datetime.date.today()
        ).exclude(status__in=cancelled_statuses)
        past_appointments = Appointment.objects.filter(
            client=user, date__lt=datetime.date.today()
        ) | Appointment.objects.filter(client=user, status__in=cancelled_statuses)
        return render(request, 'scheduler/client_dashboard.html', {
            'upcoming_appointments': upcoming_appointments,
            'past_appointments': past_appointments
        })
    elif user.role == 'practitioner':
        practitioner = get_object_or_404(Practitioner, user=user)
        cancelled_statuses = ['cancelled_by_client', 'cancelled_by_practitioner']
        pending_appointments = Appointment.objects.filter(practitioner=practitioner, status='pending')
        upcoming_appointments = Appointment.objects.filter(
            practitioner=practitioner, date__gte=datetime.date.today(), status='confirmed'
        )
        past_appointments = Appointment.objects.filter(
            practitioner=practitioner, date__lt=datetime.date.today()
        ).exclude(status='pending') | Appointment.objects.filter(
            practitioner=practitioner, status__in=cancelled_statuses
        ) | Appointment.objects.filter(practitioner=practitioner, status='completed')
        availabilities = Availability.objects.filter(practitioner=practitioner)
        availability_form = AvailabilityForm()
        return render(request, 'scheduler/practitioner_dashboard.html', {
            'practitioner': practitioner,
            'pending_appointments': pending_appointments,
            'upcoming_appointments': upcoming_appointments,
            'past_appointments': past_appointments,
            'availabilities': availabilities,
            'availability_form': availability_form,
            'pending_count': pending_appointments.count(),
            'confirmed_count': upcoming_appointments.count(),
            'completed_count': Appointment.objects.filter(practitioner=practitioner, status='completed').count(),
        })
    elif user.role == 'admin' or user.is_superuser:
        return redirect('manager_dashboard')
    return redirect('landing')


@login_required
def book_appointment(request):
    if request.user.role != 'client':
        messages.error(request, "Only clients can book appointments.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.client = request.user
            try:
                appointment.save()
                
                # Create notification for practitioner
                from .models import Notification
                msg_p = f"New booking: Client {appointment.client.get_full_name() or appointment.client.username} has scheduled {appointment.service.name} for {appointment.date} at {appointment.start_time.strftime('%H:%M')}."
                Notification.objects.create(user=appointment.practitioner.user, message=msg_p)
                
                # Trigger console email simulation
                from django.core.mail import send_mail
                try:
                    send_mail(
                        'Appointment Scheduled Confirmation - Solace Wellness Spot',
                        f"Dear {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username},\n\nYou have a new booking:\nService: {appointment.service.name}\nDate: {appointment.date}\nTime: {appointment.start_time.strftime('%H:%M')} - {appointment.end_time.strftime('%H:%M')}\nClient: {appointment.client.get_full_name() or appointment.client.username}\nPhone: {appointment.client.phone_number or 'Not provided'}\nNotes: {appointment.notes or 'None'}\n\nWarmly,\nSolace Wellness Spot Care Team",
                        'no-reply@solacewellness.com',
                        [appointment.practitioner.user.email],
                        fail_silently=True
                    )
                    send_mail(
                        'Booking Confirmed - Solace Wellness Spot',
                        f"Dear {appointment.client.get_full_name() or appointment.client.username},\n\nYour appointment is confirmed:\nService: {appointment.service.name}\nPractitioner: {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username}\nDate: {appointment.date}\nTime: {appointment.start_time.strftime('%H:%M')} - {appointment.end_time.strftime('%H:%M')}\n\nWarmly,\nSolace Wellness Spot Care Team",
                        'no-reply@solacewellness.com',
                        [appointment.client.email],
                        fail_silently=True
                    )
                except Exception:
                    pass

                messages.success(request, "Your appointment has been successfully booked!")
                return redirect('dashboard')
            except Exception as e:
                # To catch validations raised in clean() method
                error_msg = str(e)
                if hasattr(e, 'message_dict'):
                    # format clean errors nicer
                    error_msg = "; ".join([f"{k}: {', '.join(v)}" for k, v in e.message_dict.items()])
                elif hasattr(e, 'messages'):
                    error_msg = "; ".join(e.messages)
                form.add_error(None, error_msg)
    else:
        form = AppointmentForm()

    practitioners_count = Practitioner.objects.count()
    return render(request, 'scheduler/book.html', {
        'form': form,
        'practitioners_count': practitioners_count,
        'has_practitioners': practitioners_count > 0,
    })


@login_required
def cancel_appointment(request, appointment_id):
    appointment = get_object_or_404(Appointment, pk=appointment_id)
    # Check permissions (only client who booked or Practitioner who is scheduled or Admin)
    is_client = (request.user.role == 'client' and appointment.client == request.user)
    is_pract = (request.user.role == 'practitioner' and appointment.practitioner.user == request.user)
    is_admin = (request.user.role == 'admin' or request.user.is_superuser)
    
    if not (is_client or is_pract or is_admin):
        return HttpResponseForbidden("You are not authorized to cancel this appointment.")
        
    appointment.status = 'cancelled_by_client' if request.user.role == 'client' else 'cancelled_by_practitioner'
    appointment.save()
    
    from .models import Notification
    from django.core.mail import send_mail
    
    # Notify practitioner if client cancelled
    if request.user.role == 'client':
        msg_p = f"Booking Cancelled: Client {appointment.client.get_full_name() or appointment.client.username} has cancelled the {appointment.service.name} appointment for {appointment.date} at {appointment.start_time.strftime('%H:%M')}."
        Notification.objects.create(user=appointment.practitioner.user, message=msg_p)
        try:
            send_mail(
                'Treatment Cancelled Alert - Solace Wellness Spot',
                f"Dear {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username},\n\nClient {appointment.client.get_full_name() or appointment.client.username} has cancelled the {appointment.service.name} appointment for {appointment.date} at {appointment.start_time.strftime('%H:%M')}.\n\nWarmly,\nSolace Wellness Spot Team",
                'no-reply@solacewellness.com',
                [appointment.practitioner.user.email], fail_silently=True
            )
        except Exception:
            pass
    # Notify client if practitioner cancelled
    elif request.user.role == 'practitioner':
        msg_c = f"Booking Cancelled: Practitioner {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username} has cancelled your {appointment.service.name} appointment for {appointment.date} at {appointment.start_time.strftime('%H:%M')}."
        Notification.objects.create(user=appointment.client, message=msg_c)
        try:
            send_mail(
                'Appointment Cancelled - Solace Wellness Spot',
                f"Dear {appointment.client.get_full_name() or appointment.client.username},\n\nPractitioner {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username} has cancelled your {appointment.service.name} session on {appointment.date}. Please rebook at your convenience.\n\nWarmly,\nSolace Wellness Spot Team",
                'no-reply@solacewellness.com',
                [appointment.client.email], fail_silently=True
            )
        except Exception:
            pass

    messages.success(request, "Appointment successfully cancelled.")
    return redirect('dashboard')


@login_required
def accept_appointment(request, appointment_id):
    """Practitioner accepts a pending booking."""
    if request.user.role != 'practitioner':
        return HttpResponseForbidden("Practitioners only.")
    practitioner = get_object_or_404(Practitioner, user=request.user)
    appointment = get_object_or_404(Appointment, pk=appointment_id, practitioner=practitioner, status='pending')
    appointment.status = 'confirmed'
    appointment.save()

    from .models import Notification
    from django.core.mail import send_mail
    msg = f"\u2705 Booking Confirmed! {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username} has accepted your {appointment.service.name} appointment on {appointment.date} at {appointment.start_time.strftime('%H:%M')}."
    Notification.objects.create(user=appointment.client, message=msg)
    try:
        send_mail(
            'Appointment Confirmed - Solace Wellness Spot',
            f"Dear {appointment.client.get_full_name() or appointment.client.username},\n\nYour {appointment.service.name} appointment with {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username} on {appointment.date} at {appointment.start_time.strftime('%H:%M')} has been confirmed!\n\nWarmly,\nSolace Wellness Spot Team",
            'no-reply@solacewellness.com',
            [appointment.client.email], fail_silently=True
        )
    except Exception:
        pass
    messages.success(request, "Appointment accepted and client notified!")
    return redirect('dashboard')


@login_required
def decline_appointment(request, appointment_id):
    """Practitioner declines a pending booking."""
    if request.user.role != 'practitioner':
        return HttpResponseForbidden("Practitioners only.")
    practitioner = get_object_or_404(Practitioner, user=request.user)
    appointment = get_object_or_404(Appointment, pk=appointment_id, practitioner=practitioner, status='pending')
    appointment.status = 'cancelled_by_practitioner'
    appointment.save()

    from .models import Notification
    from django.core.mail import send_mail
    msg = f"\u274c Booking Declined: Unfortunately {appointment.practitioner.user.get_full_name() or appointment.practitioner.user.username} has declined your {appointment.service.name} request for {appointment.date} at {appointment.start_time.strftime('%H:%M')}. Please rebook with another available slot."
    Notification.objects.create(user=appointment.client, message=msg)
    try:
        send_mail(
            'Booking Request Declined - Solace Wellness Spot',
            f"Dear {appointment.client.get_full_name() or appointment.client.username},\n\nWe regret to inform you that your {appointment.service.name} booking request for {appointment.date} at {appointment.start_time.strftime('%H:%M')} was declined by the practitioner. Please visit the booking page to select another slot.\n\nWarmly,\nSolace Wellness Spot Team",
            'no-reply@solacewellness.com',
            [appointment.client.email], fail_silently=True
        )
    except Exception:
        pass
    messages.success(request, "Appointment declined and client notified.")
    return redirect('dashboard')


@login_required
def complete_appointment(request, appointment_id):
    """Practitioner marks an appointment as completed."""
    if request.user.role != 'practitioner':
        return HttpResponseForbidden("Practitioners only.")
    practitioner = get_object_or_404(Practitioner, user=request.user)
    appointment = get_object_or_404(Appointment, pk=appointment_id, practitioner=practitioner, status='confirmed')
    appointment.status = 'completed'
    appointment.save()
    messages.success(request, "Session marked as completed.")
    return redirect('dashboard')


@login_required
def manager_dashboard(request):
    if not (request.user.role == 'admin' or request.user.is_superuser):
        return HttpResponseForbidden("Access Denied.")

    # Status breakdown
    total_appointments = Appointment.objects.count()
    pending_bookings = Appointment.objects.filter(status='pending').count()
    confirmed_bookings = Appointment.objects.filter(status='confirmed').count()
    completed_bookings = Appointment.objects.filter(status='completed').count()
    cancelled_by_client = Appointment.objects.filter(status='cancelled_by_client').count()
    cancelled_by_pract = Appointment.objects.filter(status='cancelled_by_practitioner').count()

    # Revenue from confirmed or completed
    total_revenue = Appointment.objects.filter(
        status__in=['confirmed', 'completed']
    ).aggregate(total=Sum('service__price'))['total'] or 0.00

    popular_services = Service.objects.annotate(booking_count=Count('appointments')).order_by('-booking_count')[:5]
    practitioners = Practitioner.objects.annotate(booking_count=Count('appointments_as_practitioner')).all()
    all_appointments = Appointment.objects.all().order_by('-date', '-start_time')
    all_users = User.objects.filter(role='practitioner')

    # Create practitioner form handling
    create_pract_error = None
    create_pract_success = None
    if request.method == 'POST' and 'create_practitioner' in request.POST:
        p_username = request.POST.get('pract_username', '').strip()
        p_email = request.POST.get('pract_email', '').strip()
        p_first = request.POST.get('pract_first_name', '').strip()
        p_last = request.POST.get('pract_last_name', '').strip()
        p_password = request.POST.get('pract_password', '').strip()
        p_bio = request.POST.get('pract_bio', '').strip()
        p_services = request.POST.getlist('pract_services')

        if not all([p_username, p_email, p_first, p_password]):
            create_pract_error = "Username, email, first name, and password are all required."
        elif User.objects.filter(username=p_username).exists():
            create_pract_error = f"Username '{p_username}' is already taken."
        else:
            new_user = User.objects.create_user(
                username=p_username, email=p_email, password=p_password,
                first_name=p_first, last_name=p_last, role='practitioner'
            )
            new_pract = Practitioner.objects.create(user=new_user, bio=p_bio)
            if p_services:
                new_pract.specialties.set(Service.objects.filter(pk__in=p_services))
            create_pract_success = f"Practitioner '{p_first} {p_last}' created successfully!"
            messages.success(request, create_pract_success)

    all_services = Service.objects.all()
    return render(request, 'scheduler/manager_dashboard.html', {
        'total_appointments': total_appointments,
        'pending_bookings': pending_bookings,
        'confirmed_bookings': confirmed_bookings,
        'completed_bookings': completed_bookings,
        'cancelled_by_client': cancelled_by_client,
        'cancelled_by_pract': cancelled_by_pract,
        'total_revenue': total_revenue,
        'popular_services': popular_services,
        'practitioners': practitioners,
        'all_appointments': all_appointments,
        'all_services': all_services,
        'create_pract_error': create_pract_error,
    })


@login_required
def manage_availability(request):
    if request.user.role != 'practitioner':
        return HttpResponseForbidden("Access Denied.")
    
    practitioner = get_object_or_404(Practitioner, user=request.user)
    
    if request.method == 'POST':
        form = AvailabilityForm(request.POST, practitioner=practitioner)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Availability block added successfully!")
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, 'messages'):
                    error_msg = "; ".join(e.messages)
                messages.error(request, f"Error: {error_msg}")
        else:
            messages.error(request, "Failed to add availability block. Please review fields.")
            
    return redirect('dashboard')


@login_required
def delete_availability(request, availability_id):
    if request.user.role != 'practitioner':
        return HttpResponseForbidden("Access Denied.")
        
    practitioner = get_object_or_404(Practitioner, user=request.user)
    avail = get_object_or_404(Availability, pk=availability_id, practitioner=practitioner)
    avail.delete()
    messages.success(request, "Availability slot removed.")
    return redirect('dashboard')


# AJAX Endpoint for dynamically loading available times
def get_available_slots(request):
    practitioner_id = request.GET.get('practitioner')
    service_id = request.GET.get('service')
    date_str = request.GET.get('date')
    
    if not (practitioner_id and service_id and date_str):
        return JsonResponse({'slots': []})
        
    try:
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        practitioner = Practitioner.objects.get(pk=practitioner_id)
        service = Service.objects.get(pk=service_id)
    except (ValueError, Practitioner.DoesNotExist, Service.DoesNotExist):
        return JsonResponse({'slots': []})
        
    # Check if date is in the past
    if date < datetime.date.today():
        return JsonResponse({'slots': [], 'error': 'Cannot book slots in the past.'})
        
    # Check weekday availability
    day_num = date.weekday()
    availabilities = Availability.objects.filter(practitioner=practitioner, day_of_week=day_num)
    
    slots = []
    duration = datetime.timedelta(minutes=service.duration_minutes)
    
    # Get existing non-cancelled appointments for this practitioner on this date
    existing_appts = Appointment.objects.filter(
        practitioner=practitioner,
        date=date
    ).exclude(status__in=['cancelled_by_client', 'cancelled_by_practitioner'])
    
    # Grid of slots at 30-min intervals during availability
    for avail in availabilities:
        # Generate datetime objects for loops
        start_dt = datetime.datetime.combine(date, avail.start_time)
        end_dt = datetime.datetime.combine(date, avail.end_time)
        
        current_dt = start_dt
        while current_dt + duration <= end_dt:
            slot_start = current_dt.time()
            slot_end = (current_dt + duration).time()
            
            # If current day is today, check if start_time is in the past
            is_past = False
            if date == datetime.date.today():
                now_dt = datetime.datetime.now()
                # Use current local date-time
                slot_dt = datetime.datetime.combine(date, slot_start)
                if slot_dt < now_dt:
                    is_past = True
            
            if not is_past:
                # Check overlaps
                overlaps = False
                for appt in existing_appts:
                    if not (slot_end <= appt.start_time or slot_start >= appt.end_time):
                        overlaps = True
                        break
                
                if not overlaps:
                    slots.append(slot_start.strftime('%H:%M'))
            
            current_dt += datetime.timedelta(minutes=30)
            
    return JsonResponse({'slots': slots})


@login_required
def get_notifications_api(request):
    notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:8]
    data = [{
        'id': n.id,
        'message': n.message,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
    } for n in notifications]
    return JsonResponse({'notifications': data})


@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
