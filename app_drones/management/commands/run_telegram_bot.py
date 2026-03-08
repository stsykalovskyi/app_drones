import time
import requests
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from user_management.models import Profile

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Runs the interactive Telegram bot polling with DB verification.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        self.admin_chat_id = getattr(settings, 'TELEGRAM_CHAT_ID', None)
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0

    def handle(self, *args, **options):
        if not self.token:
            self.stdout.write(self.style.ERROR("TELEGRAM_BOT_TOKEN not set!"))
            return

        self.stdout.write(self.style.SUCCESS("Telegram bot polling started (with DB storage)..."))
        
        while True:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.process_update(update)
                time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                time.sleep(5)

    def get_updates(self):
        url = f"{self.base_url}/getUpdates?offset={self.offset + 1}&timeout=30"
        try:
            response = requests.get(url, timeout=35)
            if response.status_code == 200:
                result = response.json().get("result", [])
                if result:
                    self.offset = result[-1]["update_id"]
                return result
        except Exception:
            pass
        return []

    def send_message(self, chat_id, text, reply_markup=None):
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(url, json=payload, timeout=10)

    def process_update(self, update):
        message = update.get("message")
        if not message:
            return

        chat_id = str(message["chat"]["id"])
        
        # 1. Handle Contact (Verification)
        if "contact" in message:
            self.handle_verification(chat_id, message["contact"])
            return

        # 2. Check DB for verified profile OR .env Admin ID
        profile = Profile.objects.filter(telegram_chat_id=chat_id, user__is_active=True).first()
        is_admin = self.admin_chat_id and chat_id == str(self.admin_chat_id)

        if not profile and not is_admin:
            self.ask_for_contact(chat_id)
            return

        # 3. Access Granted: Handle commands
        text = message.get("text", "")
        username = profile.user.username if profile else "Admin"

        if text == "/start":
            name = profile.display_name if profile else "Адміністратор"
            self.send_message(chat_id, f"✅ Вітаємо, <b>{name}!</b>\nВи маєте доступ до системи.")
        elif text == "/status":
            from equipment_accounting.models import UAVInstance
            count = UAVInstance.objects.count()
            self.send_message(chat_id, f"📊 В базі зараз: <b>{count}</b> БПЛА.")
        else:
            self.send_message(chat_id, "Команда не розпізнана. Доступні: /start, /status")

    def ask_for_contact(self, chat_id):
        reply_markup = {
            "keyboard": [[{
                "text": "📱 Поділитися номером телефону",
                "request_contact": True
            }]],
            "resize_keyboard": True,
            "one_time_keyboard": True
        }
        self.send_message(
            chat_id, 
            "🔒 <b>Доступ обмежено.</b>\n\nДля верифікації, будь ласка, поділіться номером телефону. Ваш номер має бути вказаний у профілі на сайті.",
            reply_markup=reply_markup
        )

    def handle_verification(self, chat_id, contact):
        phone = contact.get("phone_number", "").replace(" ", "").replace("-", "")
        # Normalize: ensure starts with +
        if not phone.startswith("+"):
            phone = "+" + phone
        
        # Search for active user with this phone
        profile = Profile.objects.filter(phone_number=phone, user__is_active=True).first()
        
        if profile:
            profile.telegram_chat_id = chat_id
            profile.save()
            
            remove_keyboard = {"remove_keyboard": True}
            self.send_message(
                chat_id, 
                f"✅ <b>Доступ надано!</b>\nВи тепер верифіковані як {profile.display_name}. Бот буде вас пам'ятати.",
                reply_markup=remove_keyboard
            )
            logger.info(f"User {profile.user.username} verified and saved Telegram chat_id {chat_id}")
        else:
            self.send_message(chat_id, "❌ Помилка: Ваш номер телефону не знайдено в базі активних користувачів сайту.")
