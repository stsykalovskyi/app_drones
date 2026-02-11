def user_groups(request):
    """Expose a set of group names the current user belongs to."""
    if hasattr(request, "user") and request.user.is_authenticated:
        return {"user_groups": set(request.user.groups.values_list("name", flat=True))}
    return {"user_groups": set()}
