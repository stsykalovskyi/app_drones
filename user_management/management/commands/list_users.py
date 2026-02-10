from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Lists all usernames in the system.'

    def handle(self, *args, **options):
        User = get_user_model()
        users = User.objects.all().order_by('username')

        if not users:
            self.stdout.write(self.style.WARNING('No users found in the system.'))
            return

        if not users:
            self.stdout.write(self.style.WARNING('No users found in the system.'))
            return

        # Prepare data for table
        data = []
        for user in users:
            data.append({
                'username': user.username,
                'approved': 'Yes' if user.is_active else 'No',
                'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S'),
            })

        if not data: # This check is redundant due to 'if not users' above, but harmless.
            self.stdout.write(self.style.WARNING('No users found in the system.'))
            return

        # Determine column widths
        col_widths = {
            'username': len('Username'),
            'approved': len('Approved'),
            'date_joined': len('Registration Date'),
        }

        for row in data:
            col_widths['username'] = max(col_widths['username'], len(row['username']))
            col_widths['approved'] = max(col_widths['approved'], len(row['approved']))
            col_widths['date_joined'] = max(col_widths['date_joined'], len(row['date_joined']))

        # Print header
        header_line = (
            f"{'Username':<{col_widths['username']}}   "
            f"{'Approved':<{col_widths['approved']}}   "
            f"{'Registration Date':<{col_widths['date_joined']}}"
        )
        self.stdout.write(self.style.SUCCESS(header_line))
        self.stdout.write(self.style.SUCCESS("-" * len(header_line)))

        # Print rows
        for row in data:
            self.stdout.write(
                f"{row['username']:<{col_widths['username']}}   "
                f"{row['approved']:<{col_widths['approved']}}   "
                f"{row['date_joined']:<{col_widths['date_joined']}}"
            )
