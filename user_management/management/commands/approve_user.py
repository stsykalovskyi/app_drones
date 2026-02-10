from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Approves a user by setting their is_active status to True.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='The username of the user to approve.')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'User "{username}" does not exist.')

        if user.is_active:
            self.stdout.write(self.style.WARNING(f'User "{username}" is already approved.'))
        else:
            user.is_active = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'User "{username}" has been successfully approved.'))
