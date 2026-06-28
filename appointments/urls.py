from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DoctorAvailabilityViewSet, AppointmentViewSet, GetAvailableSlotsView, 
    DoctorPatientRelationViewSet, ProtocolViewSet, RecipeViewSet
)

router = DefaultRouter()
router.register('availability', DoctorAvailabilityViewSet, basename='doctor_availability')
router.register('bookings', AppointmentViewSet, basename='appointment')
router.register('patients', DoctorPatientRelationViewSet, basename='doctor_patient_relation')
router.register('protocols', ProtocolViewSet, basename='protocol')
router.register('recipes', RecipeViewSet, basename='recipe')

urlpatterns = [
    path('available-slots/', GetAvailableSlotsView.as_view(), name='available_slots'),
    path('', include(router.urls)),
]
