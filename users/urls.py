from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    ProviderRegistrationView, PatientRegistrationView, CustomTokenObtainPairView, 
    ProviderProfileView, PatientProfileView, ChangePasswordView, VerifiedDoctorListView,
    PatientListView
)

urlpatterns = [
    path('register/provider/', ProviderRegistrationView.as_view(), name='register_provider'),
    path('register/patient/', PatientRegistrationView.as_view(), name='register_patient'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', ProviderProfileView.as_view(), name='provider_profile'),
    path('profile/patient/', PatientProfileView.as_view(), name='patient_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('doctors/', VerifiedDoctorListView.as_view(), name='verified_doctors'),
    path('patients/', PatientListView.as_view(), name='patient_list'),
]
