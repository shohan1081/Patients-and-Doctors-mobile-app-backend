from rest_framework import generics, status, permissions, serializers
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (
    ProviderRegistrationSerializer, PatientRegistrationSerializer, UserSerializer, 
    ProviderProfileSerializer, PatientProfileUpdateSerializer, ChangePasswordSerializer,
    PatientSimpleSerializer
)
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db.models import Q

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


class PatientRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = PatientRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            {"message": "Registration successful. You can now log in."},
            status=status.HTTP_201_CREATED,
            headers=headers
        )


class IsPatient(permissions.BasePermission):
    """
    Allows access only to patient users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == User.PATIENT


class PatientProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsPatient]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PatientProfileUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(UserSerializer(instance).data)


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Set new password
        self.object.set_password(serializer.validated_data.get("new_password"))
        self.object.save()
        return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)


class VerifiedDoctorListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Return all verified doctor/provider users
        return User.objects.filter(role=User.PROVIDER, is_verified=True)


class IsProvider(permissions.BasePermission):
    """
    Allows access only to provider (doctor) users.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == User.PROVIDER


class PatientListView(generics.ListAPIView):
    serializer_class = PatientSimpleSerializer
    permission_classes = [permissions.IsAuthenticated, IsProvider]

    def get_queryset(self):
        queryset = User.objects.filter(role=User.PATIENT)
        search_query = (
            self.request.query_params.get('search') or 
            self.request.query_params.get('q') or 
            self.request.query_params.get('name') or 
            self.request.query_params.get('number')
        )
        if search_query:
            queryset = queryset.filter(
                Q(full_name__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            self._add_is_added_flag(request.user, data)
            return self.get_paginated_response(data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data
        self._add_is_added_flag(request.user, data)
        return Response(data)

    def _add_is_added_flag(self, doctor, serialized_patients):
        from appointments.models import DoctorPatientRelation
        added_patient_ids = set(
            DoctorPatientRelation.objects.filter(doctor=doctor)
            .values_list('patient_id', flat=True)
        )
        for item in serialized_patients:
            item['is_added'] = item['id'] in added_patient_ids




