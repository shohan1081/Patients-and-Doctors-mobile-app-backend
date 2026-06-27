from django.utils import timezone

class UpdateLastActiveMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # After the response is generated, check if the user is authenticated.
        # This works for DRF JWT authentication because DRF populates the underlying
        # request.user during API execution.
        if hasattr(request, 'user') and request.user and request.user.is_authenticated:
            try:
                now = timezone.now()
                user = request.user
                # Update last_active if it is empty or has not been updated in the last 60 seconds
                if not user.last_active or (now - user.last_active).total_seconds() > 60:
                    user.last_active = now
                    user.save(update_fields=['last_active'])
            except Exception:
                # Fail silently if anything goes wrong (e.g. during migrations, test run, or DB errors)
                pass
                
        return response
