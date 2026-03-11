"""
Django management command: python manage.py send_whatsapp

Enqueues a message for the WhatsApp sender worker.
The worker (run_whatsapp_sender) must be running to deliver it.

Usage:
    python manage.py send_whatsapp --group "Майстерня" --message "Тест"
"""
from django.core.management.base import BaseCommand

from whatsapp_monitor.models import OutgoingMessage


class Command(BaseCommand):
    help = 'Enqueue a WhatsApp message for the sender worker.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--group', '-g',
            required=True,
            help='Exact WhatsApp group display name.',
        )
        parser.add_argument(
            '--message', '-m',
            required=True,
            help='Message text to send.',
        )

    def handle(self, *args, **options):
        msg = OutgoingMessage.objects.create(
            group_name=options['group'],
            message_text=options['message'],
        )
        self.stdout.write(self.style.SUCCESS(
            f'Queued message #{msg.id} → [{msg.group_name}]: {msg.message_text}'
        ))
        self.stdout.write(
            'The sender worker will deliver it within its poll interval.\n'
            'Check status:\n'
            '  python manage.py shell -c "'
            'from whatsapp_monitor.models import OutgoingMessage; '
            f'print(OutgoingMessage.objects.get(pk={msg.id}).status)"'
        )
