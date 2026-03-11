"""
Create the "FPV" DronePurpose and reassign all "Ударний" entries to it:
  - UAVInstances with role="Ударний"
  - FPVDroneType / OpticalDroneType with purpose="Ударний"

Usage:
  python manage.py set_fpv_purpose            # dry-run
  python manage.py set_fpv_purpose --commit   # apply
"""

from django.core.management.base import BaseCommand

from equipment_accounting.models import (
    DronePurpose, FPVDroneType, OpticalDroneType, UAVInstance,
)


class Command(BaseCommand):
    help = 'Create DronePurpose "FPV" and reassign all Ударний entries to it'

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Save changes (default: dry-run)',
        )

    def handle(self, *args, **options):
        commit = options['commit']

        try:
            ударний = DronePurpose.objects.get(name='Ударний')
        except DronePurpose.DoesNotExist:
            self.stdout.write(self.style.ERROR('DronePurpose "Ударний" not found — nothing to do.'))
            return

        uav_count = UAVInstance.objects.filter(role=ударний).exclude(status='deleted').count()
        fpv_type_count = FPVDroneType.objects.filter(purpose=ударний).count()
        opt_type_count = OpticalDroneType.objects.filter(purpose=ударний).count()

        self.stdout.write(f'UAVInstances (active):  {uav_count}')
        self.stdout.write(f'FPVDroneTypes:          {fpv_type_count}')
        self.stdout.write(f'OpticalDroneTypes:      {opt_type_count}')

        if uav_count == 0 and fpv_type_count == 0 and opt_type_count == 0:
            self.stdout.write('Nothing to update.')
            return

        if commit:
            fpv, created = DronePurpose.objects.get_or_create(name='FPV')
            action = 'Created' if created else 'Found existing'
            self.stdout.write(self.style.SUCCESS(f'{action} DronePurpose "FPV" (pk={fpv.pk})'))

            if uav_count:
                updated = UAVInstance.objects.filter(role=ударний).exclude(status='deleted').update(role=fpv)
                self.stdout.write(self.style.SUCCESS(f'Updated {updated} UAVInstances: Ударний → FPV'))
            if fpv_type_count:
                updated = FPVDroneType.objects.filter(purpose=ударний).update(purpose=fpv)
                self.stdout.write(self.style.SUCCESS(f'Updated {updated} FPVDroneTypes: Ударний → FPV'))
            if opt_type_count:
                updated = OpticalDroneType.objects.filter(purpose=ударний).update(purpose=fpv)
                self.stdout.write(self.style.SUCCESS(f'Updated {updated} OpticalDroneTypes: Ударний → FPV'))
        else:
            self.stdout.write(self.style.WARNING('Dry-run — use --commit to apply.'))
