from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class ProviderRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = (
            'full_name', 'email', 'phone_number', 'organization', 
            'license_number', 'title', 'license_file', 
            'password', 'confirm_password'
        )
        extra_kwargs = {
            'full_name': {'required': True},
            'email': {'required': True},
            'phone_number': {'required': True},
            'organization': {'required': True},
            'license_number': {'required': True},
            'title': {'required': True},
            'license_file': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User.objects.create(
            role=User.PROVIDER,
            is_active=True, # User can be active but not verified
            is_verified=False, # This is our custom verification flag
            **validated_data
        )
        user.set_password(password)
        user.save()
        return user

from .models import ProviderProfile

class ProviderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderProfile
        fields = (
            'bio', 'specialty', 'experience_years', 'clinic_address', 
            'consultation_fee', 'profile_photo', 'is_available', 
            'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at')

class UserSerializer(serializers.ModelSerializer):
    provider_profile = ProviderProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'is_verified', 'provider_profile')

