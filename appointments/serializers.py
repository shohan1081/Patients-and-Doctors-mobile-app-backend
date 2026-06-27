from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DoctorAvailability, Appointment, DoctorPatientRelation, Protocol
from users.serializers import UserSerializer

User = get_user_model()

class DoctorAvailabilitySerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = DoctorAvailability
        fields = ('id', 'day_of_week', 'day_name', 'start_time', 'end_time', 'slot_duration', 'is_active')

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError("Start time must be before end time.")
        return attrs

class AppointmentSerializer(serializers.ModelSerializer):
    doctor_detail = UserSerializer(source='doctor', read_only=True)
    patient_detail = UserSerializer(source='patient', read_only=True)

    class Meta:
        model = Appointment
        fields = (
            'id', 'doctor', 'patient', 'doctor_detail', 'patient_detail', 
            'date', 'start_time', 'end_time', 'status', 
            'reason_for_visit', 'notes', 'prescription', 
            'created_at', 'updated_at'
        )
        read_only_fields = ('doctor', 'patient', 'status', 'created_at', 'updated_at')


class DoctorPatientRelationSerializer(serializers.ModelSerializer):
    patient_id = serializers.IntegerField(source='patient.id', read_only=True)
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    patient_photo = serializers.SerializerMethodField()
    patient_mobile_number = serializers.CharField(source='patient.phone_number', read_only=True, allow_null=True)
    todays_progress_percentage = serializers.SerializerMethodField()
    todays_missed_protocols_count = serializers.SerializerMethodField()

    class Meta:
        model = DoctorPatientRelation
        fields = (
            'id', 'patient', 'patient_id', 'patient_name', 'patient_photo', 'patient_mobile_number',
            'disease_title', 'health_goals', 'current_conditions',
            'current_medications', 'allergies_intolerances', 
            'todays_progress_percentage', 'todays_missed_protocols_count',
            'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at')
        extra_kwargs = {
            'patient': {'write_only': True}
        }

    def get_patient_photo(self, obj):
        request = self.context.get('request')
        patient = obj.patient
        if hasattr(patient, 'patient_profile') and patient.patient_profile and patient.patient_profile.profile_photo:
            url = patient.patient_profile.profile_photo.url
            if request:
                return request.build_absolute_uri(url)
            return url
        return None

    def get_todays_progress_percentage(self, obj):
        from datetime import datetime
        from appointments.models import Protocol, ProtocolLog
        today = datetime.now().date()
        protocols = Protocol.objects.filter(doctor=obj.doctor, patient=obj.patient, start_date__lte=today, end_date__gte=today)
        total = protocols.count()
        if total == 0:
            return 0.0
        completed = ProtocolLog.objects.filter(protocol__in=protocols, date=today).count()
        pct = (completed / total) * 100
        return round(pct, 2)

    def get_todays_missed_protocols_count(self, obj):
        from datetime import datetime
        from appointments.models import Protocol, ProtocolLog
        today = datetime.now().date()
        protocols = Protocol.objects.filter(doctor=obj.doctor, patient=obj.patient, start_date__lte=today, end_date__gte=today)
        total = protocols.count()
        completed = ProtocolLog.objects.filter(protocol__in=protocols, date=today).count()
        return total - completed

    def validate_patient(self, value):
        if value.role != User.PATIENT:
            raise serializers.ValidationError("Selected user is not a patient.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        # Check unique constraint only on creation, not on update
        if not self.instance and request and request.user:
            doctor = request.user
            patient = attrs.get('patient')
            if DoctorPatientRelation.objects.filter(doctor=doctor, patient=patient).exists():
                raise serializers.ValidationError("This patient is already added under your care.")
        return attrs


class ProtocolSerializer(serializers.ModelSerializer):
    progress_percentage = serializers.FloatField(read_only=True)
    completed_today = serializers.SerializerMethodField()
    is_active_today = serializers.SerializerMethodField()

    class Meta:
        model = Protocol
        fields = (
            'id', 'patient',
            'name', 'description', 'instructions', 'duration',
            'start_date', 'end_date', 'progress_percentage', 'completed_today',
            'is_active_today', 'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at', 'progress_percentage')
        extra_kwargs = {
            'patient': {'write_only': True}
        }

    def get_completed_today(self, obj):
        from datetime import datetime
        today = datetime.now().date()
        return obj.daily_logs.filter(date=today).exists()

    def get_is_active_today(self, obj):
        from datetime import datetime
        today = datetime.now().date()
        return obj.start_date <= today <= obj.end_date

    def validate_patient(self, value):
        if value.role != User.PATIENT:
            raise serializers.ValidationError("Selected user is not a patient.")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        if not self.instance and request and request.user:
            doctor = request.user
            patient = attrs.get('patient')
            if not DoctorPatientRelation.objects.filter(doctor=doctor, patient=patient).exists():
                raise serializers.ValidationError("You can only assign protocols to patients under your care.")
        return attrs



