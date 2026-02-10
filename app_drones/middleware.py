from django.http import Http404


def superuser_required_for_admin(get_response):
    def middleware(request):
        if request.path.startswith('/admin/') and not (
            request.user.is_authenticated and request.user.is_superuser
        ):
            raise Http404
        return get_response(request)
    return middleware
