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

from .models import ProviderProfile, PatientProfile

class ProviderProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderProfile
        fields = (
            'bio', 'specialty', 'experience_years', 'clinic_address', 
            'consultation_fee', 'profile_photo', 'is_available', 
            'created_at', 'updated_at'
        )
        read_only_fields = ('created_at', 'updated_at')

class PatientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientProfile
        fields = ('date_of_birth', 'gender', 'health_goal', 'profile_photo', 'created_at', 'updated_at')
        read_only_fields = ('created_at', 'updated_at')

class UserSerializer(serializers.ModelSerializer):
    provider_profile = ProviderProfileSerializer(read_only=True)
    patient_profile = PatientProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'full_name', 'role', 'phone_number', 'is_verified', 'last_active', 'provider_profile', 'patient_profile')


class PatientSimpleSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='full_name', read_only=True)
    mobile_number = serializers.CharField(source='phone_number', read_only=True)
    photo = serializers.SerializerMethodField()
    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'name', 'full_name', 'photo', 'profile_photo', 'mobile_number', 'phone_number', 'email')

    def get_photo(self, obj):
        request = self.context.get('request')
        try:
            profile = obj.patient_profile
            if profile and profile.profile_photo:
                photo_url = profile.profile_photo.url
                if request is not None:
                    return request.build_absolute_uri(photo_url)
                return photo_url
        except Exception:
            pass
        return None

    def get_profile_photo(self, obj):
        return self.get_photo(obj)


class PatientRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = User
        fields = (
            'full_name', 'email', 'phone_number', 
            'password', 'confirm_password'
        )
        extra_kwargs = {
            'full_name': {'required': True},
            'email': {'required': True},
            'phone_number': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        user = User.objects.create(
            role=User.PATIENT,
            is_active=True,
            is_verified=True,
            **validated_data
        )
        user.set_password(password)
        user.save()
        return user


class PatientProfileUpdateSerializer(serializers.ModelSerializer):
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=PatientProfile.GENDER_CHOICES, required=False, allow_null=True)
    health_goal = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    profile_photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('full_name', 'email', 'phone_number', 'date_of_birth', 'gender', 'health_goal', 'profile_photo')
        extra_kwargs = {
            'full_name': {'required': False},
            'email': {'required': False},
            'phone_number': {'required': False},
        }

    def validate_email(self, value):
        user = self.context['request'].user
        if User.objects.exclude(pk=user.pk).filter(email=value).exists():
            raise serializers.ValidationError("This email is already in use by another account.")
        return value

    def update(self, instance, validated_data):
        # Extract patient profile fields
        date_of_birth = validated_data.pop('date_of_birth', None)
        gender = validated_data.pop('gender', None)
        health_goal = validated_data.pop('health_goal', None)
        profile_photo = validated_data.pop('profile_photo', None)

        # Update User fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update or Create PatientProfile
        profile, created = PatientProfile.objects.get_or_create(user=instance)
        if date_of_birth is not None:
            profile.date_of_birth = date_of_birth
        if gender is not None:
            profile.gender = gender
        if health_goal is not None:
            profile.health_goal = health_goal
        if profile_photo is not None:
            profile.profile_photo = profile_photo
        profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "New password fields didn't match."})
        return attrs

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is not correct.")
        return value



