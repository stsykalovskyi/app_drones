def user_groups(request):
    """Expose a set of group names and display name for the current user."""
    if hasattr(request, "user") and request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        display_name = profile.display_name if profile else request.user.username
        return {
            "user_groups": set(request.user.groups.values_list("name", flat=True)),
            "display_name": display_name,
        }
    return {"user_groups": set(), "display_name": ""}
