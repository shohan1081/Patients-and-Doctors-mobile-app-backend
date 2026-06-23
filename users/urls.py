from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import ProviderRegistrationView, CustomTokenObtainPairView

urlpatterns = [
    path('register/provider/', ProviderRegistrationView.as_view(), name='register_provider'),
    path('login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
