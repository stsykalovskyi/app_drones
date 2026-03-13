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

### Налаштування `.env`

```
WHATSAPP_GROUP=Назва групи
WHATSAPP_STRIKE_GROUP=Назва групи для звітів ударів
```

---

### Локальне налаштування

#### 1. Встановити залежності

```bash
pip install playwright
playwright install chromium
```

#### 2. Авторизація (QR код)

```bash
python manage.py run_whatsapp_setup
```

Відкриється вікно браузера. Відскануйте QR код телефоном. Після появи списку чатів сесія збережеться у `./whatsapp_session/` і команда завершиться.

#### 3. Запуск воркера

```bash
python manage.py run_whatsapp_sender
```

---

### Production (сервер)

Django app працює в Docker контейнері `app_drones`, але воркер та бот запускаються **на хості** з host `.venv`.

#### 1. Авторизація

На сервері потрібен дисплей — використовуйте X11 forwarding або VNC:

```bash
ssh -X backend
cd /root/MyProjects/python/app_drones
python manage.py run_whatsapp_setup
```

> Якщо X11 недоступний — запустіть локально з `--session-dir` що вказує на продакшн директорію, або скопіюйте `whatsapp_session/` з локальної машини на сервер.

#### 2. Запуск воркера у screen

```bash
screen -S wasender
python manage.py run_whatsapp_sender
# Ctrl+A, D — відʼєднатись
```

Повернутися: `screen -r wasender`. Перевірити статус: `screen -list`.

#### 3. Перезапуск після деплою

Деплой перезапускає воркер автоматично (якщо screen сесія ще не існує). Щоб перезапустити вручну:

```bash
screen -S wasender -X quit
screen -S wasender
python manage.py run_whatsapp_sender
```

---

### Якщо WhatsApp змінить UI

Селектори зберігаються у `whatsapp_monitor/management/commands/base.py`.
Якщо відправка перестала працювати — перевірте актуальні `aria-label` / `data-testid` / `data-icon` через DevTools у WhatsApp Web і оновіть константи в `_send_file` та `_open_group`.
