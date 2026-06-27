from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin, StackedInline
from unfold.decorators import action
from .models import User, PendingProvider, ProviderProfile, PatientProfile

class ProviderProfileInline(StackedInline):
    model = ProviderProfile
    can_delete = False
    verbose_name_plural = 'Provider Professional Profile'
    fk_name = 'user'

class PatientProfileInline(StackedInline):
    model = PatientProfile
    can_delete = False
    verbose_name_plural = 'Patient Personal Profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin, ModelAdmin):
    inlines = (ProviderProfileInline, PatientProfileInline)
    list_display = ('email', 'full_name', 'role', 'is_verified', 'is_staff')
    list_filter = ('role', 'is_verified', 'is_staff', 'is_active')
    search_fields = ('email', 'full_name', 'organization', 'license_number')
    ordering = ('email',)
    
    actions = ['verify_providers']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'full_name', 'phone_number', 'is_verified')}),
        ('Provider Details', {'fields': ('organization', 'license_number', 'title', 'license_file', 'view_license_file')}),
    )
    
    readonly_fields = ('view_license_file',)
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Custom Fields', {
            'classes': ('wide',),
            'fields': (
                'email', 'role', 'full_name', 'phone_number', 'is_verified',
                'organization', 'license_number', 'title', 'license_file'
            ),
        }),
    )

    def view_license_file(self, obj):
        if obj.license_file:
            return mark_safe(f'<a href="{obj.license_file.url}" target="_blank" style="font-weight: bold; color: #4f46e5;">View Uploaded Document</a>')
        return "No document uploaded"
    view_license_file.short_description = "License Document Link"

    @action(description="Verify selected providers", icon="domain_verification")
    def verify_providers(self, request, queryset):
        providers = queryset.filter(role=User.PROVIDER, is_verified=False)
        count = 0
        for provider in providers:
            provider.is_verified = True
            provider.save()
            count += 1
        self.message_user(request, f"Successfully verified {count} providers and sent verification emails.")

class PendingProviderAdmin(CustomUserAdmin):
    list_display = ('email', 'full_name', 'organization', 'license_number', 'title', 'is_verified', 'date_joined')
    list_filter = ('organization', 'date_joined')
    search_fields = ('email', 'full_name', 'organization', 'license_number')
    ordering = ('-date_joined',)

    # Unclutter edit layout: show only provider info and the is_verified checkbox
    fieldsets = (
        ('Provider Information', {
            'fields': ('full_name', 'email', 'phone_number', 'title', 'organization', 'license_number', 'view_license_file')
        }),
        ('Verification Decision', {
            'fields': ('is_verified',),
            'description': 'Toggle this field to Yes/True to approve the provider. Deleting this record will reject and decline their application.'
        }),
    )

    readonly_fields = ('full_name', 'email', 'phone_number', 'title', 'organization', 'license_number', 'view_license_file')

    # Registrations should only originate from the signup API
    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).filter(role=User.PROVIDER, is_verified=False)


admin.site.register(User, CustomUserAdmin)
admin.site.register(PendingProvider, PendingProviderAdmin)

@admin.register(PatientProfile)
class PatientProfileAdmin(ModelAdmin):
    list_display = ('user', 'date_of_birth', 'gender', 'created_at')
    list_filter = ('gender', 'created_at')
    search_fields = ('user__email', 'user__full_name', 'health_goal')
    ordering = ('-created_at',)


