from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import DoctorAvailability, Appointment
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
