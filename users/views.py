from rest_framework import generics, status, permissions, serializers
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import ProviderRegistrationSerializer, UserSerializer, ProviderProfileSerializer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # We need to call super().validate(attrs) which handles authentication
        # But if we want to check is_verified BEFORE giving tokens, we can do it here.
        
        # Standard authentication
        data = super().validate(attrs)
        
        # self.user is set by super().validate(attrs)
        if self.user.role == User.PROVIDER and not self.user.is_verified:
            raise serializers.ValidationError(
                {"detail": "Your account is pending verification by an administrator."}
            )
        
        # Add extra info to response
        data['user'] = UserSerializer(self.user).data
        return data

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

from .models import ProviderProfile
from rest_framework.permissions import IsAuthenticated

class ProviderProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProviderProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Automatically get or create profile for the logged in provider
        profile, created = ProviderProfile.objects.get_or_create(user=self.request.user)
        return profile

class ProviderRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = ProviderRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"message": "Registration successful. Your account is pending verification."},
            status=status.HTTP_201_CREATED,
            headers=headers
        )

