from django.contrib.auth import SESSION_KEY
from rest_framework.authentication import SessionAuthentication

SESSION_VERSION_KEY = 'account_session_version'


class VersionedSessionAuthentication(SessionAuthentication):
    def authenticate(self, request):
        user = request._request.user
        if not user.is_authenticated or not user.is_active:
            if request.session.get(SESSION_KEY):
                request.session.flush()
            return None
        if request.session.get(SESSION_VERSION_KEY) != user.session_version:
            request.session.flush()
            return None
        self.enforce_csrf(request)
        return user, None
