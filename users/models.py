from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class User(AbstractUser):
    PATIENT = 'patient'
    PROVIDER = 'provider'
    ROLE_CHOICES = [
        (PATIENT, 'Patient'),
        (PROVIDER, 'Provider'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=PATIENT)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    
    # Provider specific fields
    organization = models.CharField(max_length=255, blank=True, null=True)
    license_number = models.CharField(max_length=100, blank=True, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    license_file = models.FileField(upload_to='licenses/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    
    # Use email as unique identifier
    email = models.EmailField(unique=True)
    
    # Make username optional or use email as username
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'full_name']

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
            
        send_verification_email = False
        if self.role == self.PROVIDER:
            if self.pk:
                try:
                    old_instance = User.objects.get(pk=self.pk)
                    if not old_instance.is_verified and self.is_verified:
                        send_verification_email = True
                except User.DoesNotExist:
                    pass
            elif self.is_verified:
                send_verification_email = True

        super().save(*args, **kwargs)

        if send_verification_email:
            self.send_verification_notification()

    def send_verification_notification(self):
        login_url = getattr(settings, 'FRONTEND_LOGIN_URL', 'http://localhost:3000/login')
        subject = "Account Verified - Wellness Simplified"
        
        # HTML Content
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Account Verified</title>
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            background-color: #f4f5f7;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
        }}
        .email-container {{
            max-width: 600px;
            margin: 40px auto;
            background: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
            border: 1px solid #e1e4e8;
        }}
        .email-header {{
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
            padding: 40px 20px;
            text-align: center;
            color: #ffffff;
        }}
        .email-header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        .email-body {{
            padding: 40px 30px;
            color: #334155;
        }}
        .email-body h2 {{
            margin-top: 0;
            font-size: 20px;
            color: #1e293b;
            font-weight: 600;
        }}
        .email-body p {{
            font-size: 16px;
            margin-bottom: 24px;
            color: #475569;
        }}
        .btn-container {{
            text-align: center;
            margin: 35px 0;
        }}
        .btn {{
            background-color: #4f46e5;
            color: #ffffff !important;
            text-decoration: none;
            padding: 14px 30px;
            font-size: 16px;
            font-weight: 600;
            border-radius: 8px;
            display: inline-block;
            box-shadow: 0 4px 6px rgba(79, 70, 229, 0.15);
            text-decoration: none;
        }}
        .divider {{
            height: 1px;
            background-color: #e2e8f0;
            margin: 30px 0;
        }}
        .email-footer {{
            padding: 0 30px 40px;
            text-align: center;
            font-size: 13px;
            color: #94a3b8;
        }}
        .email-footer p {{
            margin: 5px 0;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <h1>Wellness Simplified</h1>
        </div>
        <div class="email-body">
            <h2>Account Verified Successfully!</h2>
            <p>Hello {self.full_name},</p>
            <p>We are excited to let you know that your provider account has been manually reviewed and verified by our administrative team. Your credentials and license details have been successfully validated.</p>
            <p>You can now log in to the platform, complete your professional profile, and start engaging with patients.</p>
            <div class="btn-container">
                <a href="{login_url}" class="btn" target="_blank" style="color: #ffffff;">Log In to Your Account</a>
            </div>
            <p>If you have any questions or require support setting up your profile, feel free to reply to this email or contact our support desk.</p>
            <div class="divider"></div>
            <p style="font-size: 14px; color: #64748b; margin-bottom: 0;">Warm regards,<br><strong>The Wellness Simplified Team</strong></p>
        </div>
        <div class="email-footer">
            <p>© 2026 Wellness Simplified. All rights reserved.</p>
            <p>You received this email because your account was registered as a provider on our platform.</p>
        </div>
    </div>
</body>
</html>"""
        
        # Plain text fallback
        text_content = (
            f"Hello {self.full_name},\n\n"
            f"We are excited to let you know that your provider account has been manually reviewed and verified by our administrative team. "
            f"Your credentials and license details have been successfully validated.\n\n"
            f"You can now log in to your account here: {login_url}\n\n"
            f"Warm regards,\n"
            f"The Wellness Simplified Team"
        )
        
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@wellnesssimplified.com')
        to_email = self.email
        
        msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
        msg.attach_alternative(html_content, "text/html")
        
        try:
            msg.send(fail_silently=False)
            logger.info(f"Verification email sent to {self.email}")
        except Exception as e:
            logger.error(f"Failed to send provider verification email to {self.email}: {e}")

    def __str__(self):
        return f"{self.email} ({self.role})"


class PendingProviderManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(role='provider', is_verified=False)

class PendingProvider(User):
    objects = PendingProviderManager()

    class Meta:
        proxy = True
        verbose_name = "Pending Provider Verification"
        verbose_name_plural = "Pending Provider Verifications"

