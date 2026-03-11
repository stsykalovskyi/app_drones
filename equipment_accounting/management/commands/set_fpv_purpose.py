"""
Create the "FPV" DronePurpose and reassign all UAVInstances
whose current role is "Ударний" to the new "FPV" purpose.

Usage:
  python manage.py set_fpv_purpose            # dry-run
  python manage.py set_fpv_purpose --commit   # apply
"""

from django.core.management.base import BaseCommand

from equipment_accounting.models import DronePurpose, UAVInstance


class Command(BaseCommand):
    help = 'Create DronePurpose "FPV" and reassign Ударний UAVs to it'

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

        qs = UAVInstance.objects.filter(role=ударний).exclude(status='deleted')
        count = qs.count()

        if count == 0:
            self.stdout.write('No UAVInstances with role "Ударний" found.')
            return

        if commit:
            fpv, created = DronePurpose.objects.get_or_create(name='FPV')
            action = 'Created' if created else 'Found existing'
            self.stdout.write(self.style.SUCCESS(f'{action} DronePurpose "FPV" (pk={fpv.pk})'))
            updated = qs.update(role=fpv)
            self.stdout.write(self.style.SUCCESS(f'Updated {updated} UAVInstances: Ударний → FPV'))
        else:
            self.stdout.write(f'Would create DronePurpose "FPV" (if not exists)')
            self.stdout.write(f'Would reassign {count} UAVInstances from "Ударний" → "FPV"')
            self.stdout.write(self.style.WARNING('Dry-run — use --commit to apply.'))
