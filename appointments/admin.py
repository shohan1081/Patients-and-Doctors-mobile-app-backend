from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import DoctorAvailability, Appointment

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
