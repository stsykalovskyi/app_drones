from django.contrib.auth import get_user_model
from django.http import Http404


def superuser_required_for_admin(get_response):
    def middleware(request):
        if request.path.startswith('/admin/') and not (
            request.user.is_authenticated and request.user.is_superuser
        ):
            raise Http404
        return get_response(request)
    return middleware


class ImpersonateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        original_id = request.session.get('_impersonate')
        if original_id and request.user.is_authenticated:
            User = get_user_model()
            try:
                request.real_user = User.objects.get(pk=original_id)
                request.is_impersonating = True
            except User.DoesNotExist:
                request.session.pop('_impersonate', None)
                request.is_impersonating = False
                request.real_user = request.user
        else:
            request.is_impersonating = False
            request.real_user = request.user
        return self.get_response(request)
