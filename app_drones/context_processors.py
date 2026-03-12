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


def pending_orders_count(request):
    """Count of active drone orders — shown in navbar badge for masters."""
    if (
        hasattr(request, "user")
        and request.user.is_authenticated
        and request.user.has_perm("pilots.change_droneorder")
    ):
        from pilots.models import DroneOrder
        count = DroneOrder.objects.filter(
            status__in=["pending", "in_progress", "ready"]
        ).count()
        return {"active_orders_count": count}
    return {"active_orders_count": 0}
