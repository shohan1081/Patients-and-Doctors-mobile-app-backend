from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.decorators import action
from .models import User, PendingProvider

class CustomUserAdmin(UserAdmin, ModelAdmin):
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

    def get_queryset(self, request):
        # Only show unverified provider accounts
        return super().get_queryset(request).filter(role=User.PROVIDER, is_verified=False)

admin.site.register(User, CustomUserAdmin)
admin.site.register(PendingProvider, PendingProviderAdmin)


