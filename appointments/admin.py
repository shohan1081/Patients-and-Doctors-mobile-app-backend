from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import DoctorAvailability, Appointment, DoctorPatientRelation, Protocol, ProtocolLog

@admin.register(DoctorAvailability)
class DoctorAvailabilityAdmin(ModelAdmin):
    list_display = ('doctor', 'day_of_week', 'start_time', 'end_time', 'slot_duration', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    search_fields = ('doctor__email', 'doctor__full_name')
    ordering = ('doctor', 'day_of_week', 'start_time')

@admin.register(Appointment)
class AppointmentAdmin(ModelAdmin):
    list_display = ('patient', 'doctor', 'date', 'start_time', 'end_time', 'status')
    list_filter = ('status', 'date')
    search_fields = ('doctor__email', 'doctor__full_name', 'patient__email', 'patient__full_name')
    ordering = ('-date', '-start_time')

@admin.register(DoctorPatientRelation)
class DoctorPatientRelationAdmin(ModelAdmin):
    list_display = ('doctor', 'patient', 'disease_title', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('doctor__email', 'doctor__full_name', 'patient__email', 'patient__full_name', 'disease_title')
    ordering = ('-created_at',)


@admin.register(Protocol)
class ProtocolAdmin(ModelAdmin):
    list_display = ('name', 'doctor', 'patient', 'duration', 'start_date', 'end_date', 'created_at')
    list_filter = ('start_date', 'end_date', 'created_at')
    search_fields = ('name', 'doctor__email', 'doctor__full_name', 'patient__email', 'patient__full_name')
    ordering = ('-created_at',)


@admin.register(ProtocolLog)
class ProtocolLogAdmin(ModelAdmin):
    list_display = ('protocol', 'date', 'completed_at')
    list_filter = ('date', 'completed_at')
    search_fields = ('protocol__name', 'protocol__patient__email', 'protocol__patient__full_name')
    ordering = ('-completed_at',)

