# Fixhub(app_drones)

## Логування

Усі логи пишуться в папку `logs/` у корені проекту.

| Файл | Що містить |
|------|-----------|
| `logs/app.log` | Усе (INFO і вище) |
| `logs/errors.log` | Тільки помилки (ERROR і вище) |

Файли ротуються автоматично (10 MB / 5 MB, 5 резервних копій).

### Корисні команди

```bash
# Дивитись помилки в реальному часі
tail -f logs/errors.log

# Знайти конкретну помилку
grep "whatsapp" logs/errors.log

# Весь лог
tail -f logs/app.log
```

### Docker

Якщо веб-застосунок запущено в контейнері — переконайтесь, що `BASE_DIR` змонтовано як volume, інакше логи залишаться всередині контейнера.

---

## WhatsApp Sender

Відправляє повідомлення та відео у WhatsApp групи через Playwright/Chromium (WhatsApp Web).

### Перший запуск (авторизація)

Необхідно один раз авторизуватися — відсканувати QR код:

```bash
python manage.py run_whatsapp_setup
```

Відкриється вікно браузера. Відскануйте QR код телефоном. Після появи списку чатів сесія збережеться у `./whatsapp_session/` і команда завершиться.

### Запуск воркера

```bash
screen -S wasender
python manage.py run_whatsapp_sender
```

Воркер опитує чергу `OutgoingMessage` кожні 5 секунд. Повернутися до сесії: `screen -r wasender`.

### Налаштування `.env`

```
WHATSAPP_GROUP=Назва групи
WHATSAPP_STRIKE_GROUP=Назва групи для звітів ударів
```

### Якщо WhatsApp змінить UI

Селектори зберігаються у `whatsapp_monitor/management/commands/base.py`.
Якщо відправка перестала працювати — перевірте актуальні `aria-label` / `data-testid` / `data-icon` через DevTools у WhatsApp Web і оновіть константи в `_send_file` та `_open_group`.
