from rest_framework import viewsets, status, permissions, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta, time

from .models import DoctorAvailability, Appointment, DoctorPatientRelation, Protocol, ProtocolLog, Recipe, RecipeFavorite, RecipeRecommendation
from .serializers import DoctorAvailabilitySerializer, AppointmentSerializer, DoctorPatientRelationSerializer, ProtocolSerializer, RecipeSerializer

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


class IsProvider(permissions.BasePermission):
    """
    Allows access only to provider (doctor) users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == User.PROVIDER


class DoctorPatientRelationViewSet(viewsets.ModelViewSet):
    serializer_class = DoctorPatientRelationSerializer
    permission_classes = [permissions.IsAuthenticated, IsProvider]

    def get_queryset(self):
        # Doctors can only see their own linked patients
        return DoctorPatientRelation.objects.filter(doctor=self.request.user)

    def perform_create(self, serializer):
        # Auto-set doctor to the logged-in doctor (provider)
        serializer.save(doctor=self.request.user)


class IsProtocolDoctorOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow doctors of a protocol to edit/delete it.
    """
    def has_object_permission(self, request, view, obj):
        # Allow the patient to mark the protocol as done
        if view.action == 'mark_done':
            return obj.patient == request.user

        # Read permissions are allowed to both patient and doctor of the protocol
        if request.method in permissions.SAFE_METHODS:
            return obj.patient == request.user or obj.doctor == request.user
        # Write permissions are only allowed to the doctor who created it
        return obj.doctor == request.user


class ProtocolViewSet(viewsets.ModelViewSet):
    serializer_class = ProtocolSerializer
    permission_classes = [permissions.IsAuthenticated, IsProtocolDoctorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        if user.role == User.PROVIDER:
            # Enforce patient_id query parameter only for listing protocols
            if self.action == 'list':
                patient_id = self.request.query_params.get('patient_id') or self.request.query_params.get('patient')
                if not patient_id:
                    from rest_framework.exceptions import ValidationError
                    raise ValidationError(
                        {"detail": "patient_id query parameter is required for doctors to view a patient's protocols."}
                    )
                queryset = Protocol.objects.filter(doctor=user, patient_id=patient_id)
            else:
                queryset = Protocol.objects.filter(doctor=user)
        else:
            # Patients see protocols assigned to them
            queryset = Protocol.objects.filter(patient=user)

        # Support filtering by active_today
        active_today = self.request.query_params.get('active_today')
        if active_today == 'true':
            today = datetime.now().date()
            queryset = queryset.filter(start_date__lte=today, end_date__gte=today)

        return queryset

    def perform_create(self, serializer):
        # Auto-set the logged-in doctor
        if self.request.user.role != User.PROVIDER:
            self.permission_denied(
                self.request,
                message="Only doctors can create/assign protocols."
            )
        serializer.save(doctor=self.request.user)

    @action(detail=True, methods=['post'], url_path='mark-done')
    def mark_done(self, request, pk=None):
        protocol = self.get_object()

        # Access control: only the assigned patient can mark it as done
        if request.user != protocol.patient:
            return Response(
                {"detail": "Only the assigned patient can mark this protocol as done."},
                status=status.HTTP_403_FORBIDDEN
            )

        today = datetime.now().date()

        # Check if today is within protocol active range
        if not (protocol.start_date <= today <= protocol.end_date):
            return Response(
                {"detail": "This protocol is not active today."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create completion log for today
        log, created = ProtocolLog.objects.get_or_create(protocol=protocol, date=today)
        if not created:
            return Response(
                {"detail": "This protocol is already marked as done for today.", "progress_percentage": protocol.progress_percentage},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "detail": "Protocol marked as done for today.",
            "progress_percentage": protocol.progress_percentage,
            "completed_today": True
        }, status=status.HTTP_200_OK)


class IsRecipeCreatorOrReadOnly(permissions.BasePermission):
    """
    Allow read-only requests to any user, but edits/deletes only to the doctor creator.
    """
    def has_object_permission(self, request, view, obj):
        # Allow favorite / unfavorite / recommend / unrecommend actions to pass object level checks
        if view.action in ['favorite', 'unfavorite', 'recommend', 'unrecommend']:
            return True
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.creator == request.user


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [permissions.IsAuthenticated, IsRecipeCreatorOrReadOnly]

    def get_queryset(self):
        queryset = Recipe.objects.all()

        # Support category filter (e.g. ?category=breakfast)
        category_param = self.request.query_params.get('category')
        if category_param:
            queryset = queryset.filter(category=category_param)

        # Support favorites filter (e.g. ?is_favorite=true or ?favorites=true)
        favorites_param = self.request.query_params.get('is_favorite') or self.request.query_params.get('favorites')
        if favorites_param == 'true':
            queryset = queryset.filter(favorites__user=self.request.user)

        # Support recommended filter (e.g. ?recommended=true)
        recommended_param = self.request.query_params.get('recommended')
        if recommended_param == 'true':
            # For patients, return recipes recommended to them
            if self.request.user.role == User.PATIENT:
                queryset = queryset.filter(recommendations__patient=self.request.user)
            # For doctors, return recipes recommended to a patient_id query param
            else:
                patient_id = self.request.query_params.get('patient_id')
                if patient_id:
                    queryset = queryset.filter(recommendations__patient_id=patient_id)

        return queryset

    def perform_create(self, serializer):
        # Only doctors (providers) can create recipes
        if self.request.user.role != User.PROVIDER:
            self.permission_denied(
                self.request,
                message="Only doctors can create recipes."
            )
        serializer.save(creator=self.request.user)

    @action(detail=True, methods=['post'], url_path='favorite')
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        if request.user.role != User.PATIENT:
            return Response(
                {"detail": "Only patients can favorite recipes."},
                status=status.HTTP_403_FORBIDDEN
            )
        RecipeFavorite.objects.get_or_create(user=request.user, recipe=recipe)
        return Response(
            {"detail": f"Recipe '{recipe.name}' added to favorites."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='unfavorite')
    def unfavorite(self, request, pk=None):
        recipe = self.get_object()
        if request.user.role != User.PATIENT:
            return Response(
                {"detail": "Only patients can unfavorite recipes."},
                status=status.HTTP_403_FORBIDDEN
            )
        RecipeFavorite.objects.filter(user=request.user, recipe=recipe).delete()
        return Response(
            {"detail": f"Recipe '{recipe.name}' removed from favorites."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='recommend')
    def recommend(self, request, pk=None):
        recipe = self.get_object()
        if request.user.role != User.PROVIDER:
            return Response(
                {"detail": "Only doctors can recommend recipes."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        patient_id = request.data.get('patient')
        if not patient_id:
            return Response(
                {"detail": "patient ID is required in request body."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            patient = User.objects.get(id=patient_id, role=User.PATIENT)
        except User.DoesNotExist:
            return Response(
                {"detail": "Selected patient does not exist."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce that the patient is under this doctor's care
        if not DoctorPatientRelation.objects.filter(doctor=request.user, patient=patient).exists():
            return Response(
                {"detail": "You can only recommend recipes to patients under your care."},
                status=status.HTTP_400_BAD_REQUEST
            )

        RecipeRecommendation.objects.get_or_create(recipe=recipe, patient=patient, doctor=request.user)
        return Response(
            {"detail": f"Recipe '{recipe.name}' recommended to patient '{patient.full_name}'."},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], url_path='unrecommend')
    def unrecommend(self, request, pk=None):
        recipe = self.get_object()
        if request.user.role != User.PROVIDER:
            return Response(
                {"detail": "Only doctors can unrecommend recipes."},
                status=status.HTTP_403_FORBIDDEN
            )
            
        patient_id = request.data.get('patient')
        if not patient_id:
            return Response(
                {"detail": "patient ID is required in request body."},
                status=status.HTTP_400_BAD_REQUEST
            )

        RecipeRecommendation.objects.filter(recipe=recipe, patient_id=patient_id, doctor=request.user).delete()
        return Response(
            {"detail": f"Recipe '{recipe.name}' recommendation removed."},
            status=status.HTTP_200_OK
        )


