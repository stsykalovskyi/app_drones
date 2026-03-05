"""
Assign DroneRole to UAVInstances that have role=None.

Rules (mirror parse_drone_import logic):
  purpose "Ударний"    → FPV
  purpose "Донаведення" → FPV
  purpose "Носій"      → Носій
  purpose "Мінувальник"→ Мінувальник
  purpose "Перехоплювач"→ Перехоплювач
  purpose "Бомбардувальник"→ Бомбардувальник

Usage:
  python manage.py fix_uav_roles            # dry-run
  python manage.py fix_uav_roles --commit   # apply
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from equipment_accounting.models import (
    DroneRole, FPVDroneType, OpticalDroneType, UAVInstance,
)

PURPOSE_TO_ROLE = {
    "Ударний":          "FPV",
    "Донаведення":      "FPV",
    "Носій":            "Носій",
    "Мінувальник":      "Мінувальник",
    "Перехоплювач":     "Перехоплювач",
    "Бомбардувальник":  "Бомбардувальник",
}


class Command(BaseCommand):
    help = "Assign DroneRole to UAVInstances that have role=None"

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Save changes (default: dry-run)",
        )

    def handle(self, *args, **options):
        commit = options["commit"]
        roles = {r.name: r for r in DroneRole.objects.all()}

        ct_fpv = ContentType.objects.get_for_model(FPVDroneType)
        ct_opt = ContentType.objects.get_for_model(OpticalDroneType)

        # Build map: (content_type_id, object_id) → purpose name
        type_purpose = {}
        for dt in FPVDroneType.objects.select_related("purpose"):
            type_purpose[(ct_fpv.pk, dt.pk)] = dt.purpose.name if dt.purpose else None
        for dt in OpticalDroneType.objects.select_related("purpose"):
            type_purpose[(ct_opt.pk, dt.pk)] = dt.purpose.name if dt.purpose else None

        qs = UAVInstance.objects.filter(role__isnull=True).exclude(status="deleted")
        total = updated = skipped = 0

        for uav in qs:
            total += 1
            purpose_name = type_purpose.get((uav.content_type_id, uav.object_id))
            role_name = PURPOSE_TO_ROLE.get(purpose_name)
            role = roles.get(role_name) if role_name else None

            if role is None:
                self.stdout.write(
                    f"  — пропущено  UAV#{uav.pk}  призначення={purpose_name or '—'}"
                )
                skipped += 1
                continue

            if commit:
                uav.role = role
                uav.save(update_fields=["role"])
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ UAV#{uav.pk}  {purpose_name} → {role.name}")
                )
            else:
                self.stdout.write(
                    f"  + UAV#{uav.pk}  {purpose_name} → {role.name}"
                )
            updated += 1

        action = "Оновлено" if commit else "Буде оновлено"
        self.stdout.write(
            f"\nВсього без ролі: {total}  |  {action}: {updated}  |  Пропущено: {skipped}"
        )
        if not commit:
            self.stdout.write(self.style.WARNING("  Запустіть з --commit щоб зберегти."))
