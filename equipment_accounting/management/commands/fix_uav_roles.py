"""
Assign DronePurpose to UAVInstances that have role=None,
based on the drone type's purpose.

Usage:
  python manage.py fix_uav_roles            # dry-run
  python manage.py fix_uav_roles --commit   # apply
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from equipment_accounting.models import (
    FPVDroneType, OpticalDroneType, UAVInstance,
)


class Command(BaseCommand):
    help = "Assign DronePurpose to UAVInstances that have role=None"

    def add_arguments(self, parser):
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Save changes (default: dry-run)",
        )

    def handle(self, *args, **options):
        commit = options["commit"]

        ct_fpv = ContentType.objects.get_for_model(FPVDroneType)
        ct_opt = ContentType.objects.get_for_model(OpticalDroneType)

        # Build map: (content_type_id, object_id) → DronePurpose
        type_purpose = {}
        for dt in FPVDroneType.objects.select_related("purpose"):
            if dt.purpose_id:
                type_purpose[(ct_fpv.pk, dt.pk)] = dt.purpose
        for dt in OpticalDroneType.objects.select_related("purpose"):
            if dt.purpose_id:
                type_purpose[(ct_opt.pk, dt.pk)] = dt.purpose

        qs = UAVInstance.objects.filter(role__isnull=True).exclude(status="deleted")
        total = updated = skipped = 0

        for uav in qs:
            total += 1
            purpose = type_purpose.get((uav.content_type_id, uav.object_id))

            if purpose is None:
                self.stdout.write(f"  — пропущено  UAV#{uav.pk}  (призначення не знайдено)")
                skipped += 1
                continue

            if commit:
                uav.role = purpose
                uav.save(update_fields=["role"])
                self.stdout.write(self.style.SUCCESS(f"  ✓ UAV#{uav.pk}  → {purpose.name}"))
            else:
                self.stdout.write(f"  + UAV#{uav.pk}  → {purpose.name}")
            updated += 1

        action = "Оновлено" if commit else "Буде оновлено"
        self.stdout.write(
            f"\nВсього без призначення: {total}  |  {action}: {updated}  |  Пропущено: {skipped}"
        )
        if not commit:
            self.stdout.write(self.style.WARNING("  Запустіть з --commit щоб зберегти."))
