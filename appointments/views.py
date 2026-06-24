from rest_framework import viewsets, status, permissions, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta, time

from .models import DoctorAvailability, Appointment
from .serializers import DoctorAvailabilitySerializer, AppointmentSerializer

User = get_user_model()

class DoctorAvailabilityViewSet(viewsets.ModelViewSet):
    serializer_class = DoctorAvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # A doctor can only manage their own availability
        return DoctorAvailability.objects.filter(doctor=self.request.user)

    def perform_create(self, serializer):
        # Auto-set the logged-in doctor
        serializer.save(doctor=self.request.user)

class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.PROVIDER:
            # Filter by date/status if query params are provided
            queryset = Appointment.objects.filter(doctor=user)
        else:
            queryset = Appointment.objects.filter(patient=user)
        
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        return queryset

    def perform_create(self, serializer):
        # Patients create appointments. Auto-set patient to request.user
        # The frontend passes the doctor ID and datetime in post parameters.
        # We compute end_time based on availability slot_duration.
        doctor_id = self.request.data.get('doctor')
        doctor = get_object_or_404(User, id=doctor_id, role=User.PROVIDER)
        
        date_str = self.request.data.get('date')
        start_time_str = self.request.data.get('start_time')
        
        # Determine slot duration from doctor's availability template or default to 30 mins
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        weekday = date_obj.weekday()
        
        availability = DoctorAvailability.objects.filter(
            doctor=doctor, 
            day_of_week=weekday,
            is_active=True
        ).first()
        
        duration = availability.slot_duration if availability else 30
        
        start_time_obj = datetime.strptime(start_time_str, '%H:%M:%S').time()
        start_dt = datetime.combine(date_obj, start_time_obj)
        end_dt = start_dt + timedelta(minutes=duration)
        
        serializer.save(
            patient=self.request.user,
            doctor=doctor,
            end_time=end_dt.time(),
            status='pending'
        )

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        appointment = self.get_object()
        if appointment.doctor != request.user:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        appointment.status = 'accepted'
        appointment.save()
        return Response(AppointmentSerializer(appointment).data)

    @action(detail=True, methods=['post'])
    def decline(self, request, pk=None):
        appointment = self.get_object()
        if appointment.doctor != request.user:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        appointment.status = 'declined'
        appointment.save()
        return Response(AppointmentSerializer(appointment).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        appointment = self.get_object()
        if appointment.doctor != request.user:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        notes = request.data.get('notes', appointment.notes)
        prescription = request.data.get('prescription', appointment.prescription)
        
        appointment.status = 'completed'
        appointment.notes = notes
        appointment.prescription = prescription
        appointment.save()
        return Response(AppointmentSerializer(appointment).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        # Both doctor and patient can cancel
        if appointment.doctor != request.user and appointment.patient != request.user:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        
        appointment.status = 'cancelled'
        appointment.save()
        return Response(AppointmentSerializer(appointment).data)

class GetAvailableSlotsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        date_str = request.query_params.get('date') # Format: YYYY-MM-DD

        if not doctor_id or not date_str:
            return Response(
                {"detail": "Both doctor_id and date query parameters are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST
            )

        doctor = get_object_or_404(User, id=doctor_id, role=User.PROVIDER)
        weekday = date_obj.weekday()

        # Fetch active availability templates for that day of week
        availabilities = DoctorAvailability.objects.filter(
            doctor=doctor,
            day_of_week=weekday,
            is_active=True
        )

        # Get existing appointments for this doctor on this day (exclude cancelled/declined)
        existing_appointments = Appointment.objects.filter(
            doctor=doctor,
            date=date_obj
        ).exclude(status__in=['cancelled', 'declined'])

        booked_slots = set()
        for app in existing_appointments:
            booked_slots.add(app.start_time.strftime('%H:%M:%S'))

        available_slots = []

        for availability in availabilities:
            slot_duration = availability.slot_duration
            start_dt = datetime.combine(date_obj, availability.start_time)
            end_dt = datetime.combine(date_obj, availability.end_time)

            current_dt = start_dt
            while current_dt + timedelta(minutes=slot_duration) <= end_dt:
                slot_start = current_dt.time()
                slot_end = (current_dt + timedelta(minutes=slot_duration)).time()
                
                start_time_str = slot_start.strftime('%H:%M:%S')
                is_available = start_time_str not in booked_slots
                
                # Double safety: do not show past slots if date is today
                if date_obj == datetime.now().date() and slot_start < datetime.now().time():
                    is_available = False

                available_slots.append({
                    "start_time": start_time_str,
                    "end_time": slot_end.strftime('%H:%M:%S'),
                    "is_available": is_available
                })
                current_dt += timedelta(minutes=slot_duration)

        return Response({
            "doctor_id": doctor.id,
            "date": date_str,
            "slots": available_slots
        })
