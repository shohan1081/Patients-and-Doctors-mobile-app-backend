from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DoctorAvailabilityViewSet, AppointmentViewSet, GetAvailableSlotsView

router = DefaultRouter()
router.register('availability', DoctorAvailabilityViewSet, basename='doctor_availability')
router.register('bookings', AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('available-slots/', GetAvailableSlotsView.as_view(), name='available_slots'),
    path('', include(router.urls)),
]
