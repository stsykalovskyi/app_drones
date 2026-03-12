from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


CREW_CHOICES = [(v, v) for v in [
    'АКУЛА', 'БОЦМАН', 'ДЕМЕНТОР', 'КАЙМАН', 'КАЖАН', 'КОСМОНАВТ', 'КАПЕР',
    'РАКЕТА', 'ПУГАЧ', 'ЗЛЮКА', 'СУЗУКІ', 'КРЕЧЕТ', 'АКВІЛА', 'ДЕВЕРСАНТ',
    'АЛЬГІЗ', 'ПЕКАРЬ', 'ПАЛІЙ', 'АМІГО', 'ФАРАДЕЙ', 'ГРИФ', 'ХАНТЕР',
    'СКАУТ', 'СТУДЕНТ', 'ГАРПІЯ', 'ЛЮТИЙ', 'ХАРОН', 'Мікі', 'Амулет',
    'ШЕРШЕНЬ', 'ВОРОН', 'КРОТ',
]]

WEAPON_TYPE_CHOICES = [(v, v) for v in [
    'FPV', 'FPV ОПТОВОЛОКНО', 'FPV БОМБЕР', 'VAMPIRE', 'MAVIC', 'MATRICE',
    'КАЖАН', 'HEAVY SHOT', 'NEMESIS', 'AVENGER', 'Перун', 'Батон 13', 'Шершень',
]]

WEAPON_NAME_CHOICES = [(v, v) for v in [
    'SHRIKE 7', 'SHRIKE 10', 'SHRIKE 10T', 'MAMONTH 10', 'MAMONTH 13',
    'MAMONTH 10T', 'F7', 'F10', 'F10T', 'KOLIBRI 7', 'KOLIBRI 8', 'KOLIBRI 10',
    'KOLIBRI 10T', 'SPARROW 2', 'SPARROW 2T', 'RUSORIZ 8', 'RUSORIZ 10',
    'PEGAS 7', 'PEGAS 7T', 'MOSKAL HUNTER', 'GENERAL CHERESHNYA',
    'GENERAL CHERESHNYA THERMAL', 'DYKIY SHERHEN', 'RIY POMSTY', 'VYRIY 10',
    'VYRIY 10T', 'VYRIY 10 OPTIC', 'OPTORIZ', 'OPTORIZ 13', 'STALKER 10',
    'STALKER 15', 'SPOOK 8', 'SPOOK 10', 'SPOOK 8T', 'SPOOK 10T', 'MOLFAR',
    'ENTERPRICE 10', 'ENTERPRICE 10T', 'ENTERPRICE 15', 'ENTERPRICE 13',
    'BLINK 8', 'BLINK 10', 'TIN', 'CHAYKA 10', 'CHAYKA 13', 'GRIM',
    'HUNTER 10', 'HUNTER 15', 'SKYRIPER', 'BATON', 'GARPIYA', 'SAPSAN',
    'MAVIC 3', 'MAVIC 3 PRO', 'MAVIC 3T', 'MAVIC 3E', 'AUTEL EVO MAX 4T',
    'AUTEL EVO MAX 4N', 'MATRICE 4E', 'MATRICE 4T', 'VAMPIRE GEN 2', 'KAZHAN',
    'MAD CAT  13', 'SWITLOWOD', 'KOLIBRI 7 ЖДУН', 'SHRIKE 10 ЖДУН',
    'BOMBUS 10', 'BOMBUS 10T', 'BOMBUS 15', 'BOMBUS 15T', 'SEAGULL 13',
    'ГОРИНЬ 13', 'ГОРИНЬ 13Т', 'SPALAKH 10', 'А 10', 'Гріф 10', 'VIPER',
    'NEMESIS', 'SHURIKEN 10', 'SHURIKEN 10 T', 'AVENGER', 'ПЕРУН', 'BATON 13',
    'БАХМУТ 10', 'ГОРОБЕЦЬ 13 ОВ', 'BESHKET 10', 'BESHKET 10 T',
]]

AMMO_CHOICES = [(v, v) for v in [
    'АО-1', 'АО-2.5', 'АО-2.5х2', 'БНПП 40', 'ВОГ-17', 'ВОГ-25',
    'ГРАНАТА-ЗАПАЛЬНИЧКА', 'ЗАБ', 'КЗ-6', 'ПГ-7', 'ПГ-9', 'ТАБ К1.4',
    'ТЕРМІТ 500', 'ТЕРМІТ 100', 'ТМ', 'У250', 'УФ1500', 'Ф1000', 'Ф1300',
    'Ф 1600', 'Ф2000', 'Ф3000', 'МОА1200', 'МОА4900', 'МОА9000', 'НАПАЛМ',
    'РКГ', 'ПОМ-2', 'ПФМ 1', 'ПТМ', 'ПТМ 2,4', 'ПТМ3М', 'Ф-1', 'М82',
    'Т2000', 'Т4000', 'МК 1500 ТЮЛЬПАН', 'АЕРОЗОЛЬ АКТИВОВАНИЙ',
    'ВОДА АКТИВОВАНА', 'ДИМ АКТИВОВАНИЙ', 'КОНЬЯК АКТИВОВАНИЙ', 'ПОСИЛКА',
    'КУ 900', 'КУ 1500', 'ЧІКУШКА', 'РОСА', 'ВАЛДАС', 'Т1000', 'ТЕРМІТ 1800',
    'Міна 60мм', 'Артріт', 'ФАБ 8.5', 'ФАБ 4.5', 'ОГ-9', 'УБ-65', 'БРЕВНО',
    'ТБ1800', 'ОГБ-1', 'УФ-2000 "ГОРОХ"', 'AVG-4000', 'Міна 120', 'ІБМ-1',
    'МІна Сир', 'У1000', 'F27',
]]

INITIATION_CHOICES = [(v, v) for v in [
    'УЗРГМ', 'УДЗ', 'УДЗ НА УДАР', 'МУВ', 'ЕЛЕКТРОДЕТОНАТОР', 'НАКОЛ',
    '3D ЗАМИКАЧ', 'ДЖОНІК', 'РОЗТЯЖКА', 'Запезпечення',
]]

TARGET_CHOICES = [(v, v) for v in [
    'КУЩ', 'АТ', 'ВАТ', 'БТ', 'МІНОМЕТ', 'ГАРМАТА', 'ІФС', 'ПІХОТА', 'РЕБ',
    'АНТЕНА', 'МАЙНО', 'ПММ', 'МОТОЦИКЛ', 'КВАДРОЦИКЛ', 'БК', 'ЖДУН',
    'ДОРОГА', 'БПЛА', 'НРК', 'ЗУ', 'РЛС', 'ІНШЕ', 'Посилка', 'Посадка',
]]

RESULT_CHOICES = [(v, v) for v in [
    '200', '300', 'Р-Н ЦІЛІ', 'НЕРОЗРИВ', 'НЕДОЛІТ', 'ОБРИВ ВОЛОКНА',
    'ДІЯ РЕБ', 'ЗБИЛИ ЗІ СТРІЛЕЦЬКОЇ ЗБРОЇ', 'МІНУВАННЯ', 'ВТРАТА КЕРУВАННЯ',
    'ВТРАТА ЗВЯЗКУ', 'ЗГОРІВ VTX', 'ДЕФЕКТ ДРОНА', 'Закінчилось волокно',
]]


class StrikeReport(models.Model):
    """Звіт пілота про результат удару БПЛА."""

    pilot = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='strike_reports', verbose_name="Пілот"
    )
    strike_date = models.DateField(verbose_name="Дата")
    crew = models.CharField(
        max_length=50, choices=CREW_CHOICES, verbose_name="Екіпаж"
    )
    weapon_type = models.CharField(
        max_length=50, choices=WEAPON_TYPE_CHOICES, verbose_name="Засіб"
    )
    weapon_name = models.CharField(
        max_length=100, choices=WEAPON_NAME_CHOICES, verbose_name="Назва засобу"
    )
    ammo_type = models.CharField(
        max_length=100, choices=AMMO_CHOICES, verbose_name="БК"
    )
    initiation_type = models.CharField(
        max_length=50, choices=INITIATION_CHOICES, verbose_name="Ініціація"
    )
    target_type = models.CharField(
        max_length=50, choices=TARGET_CHOICES, verbose_name="Ціль"
    )
    result_type = models.CharField(
        max_length=100, choices=RESULT_CHOICES, verbose_name="Результат"
    )
    notes = models.TextField(blank=True, verbose_name="Примітки")
    video = models.FileField(
        upload_to='strikes/videos/%Y/%m/',
        null=True, blank=True,
        verbose_name="Відео",
        help_text="Файл відео результату удару (MP4, MOV тощо)",
    )
    reported_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата звіту")

    class Meta:
        verbose_name = "Звіт про удар"
        verbose_name_plural = "Звіти про удари"
        ordering = ['-reported_at']

    def __str__(self):
        return f"{self.crew} — {self.strike_date}"


class DroneOrder(models.Model):
    """Замовлення дронів пілотом у майстерні."""

    STATUS_CHOICES = [
        ('pending', 'Очікує'),
        ('in_progress', 'В роботі'),
        ('ready', 'Готово'),
        ('delivered', 'Видано'),
        ('cancelled', 'Скасовано'),
    ]

    STATUS_COLORS = {
        'pending': 'warning',
        'in_progress': 'info',
        'ready': 'success',
        'delivered': 'muted',
        'cancelled': 'error',
    }

    pilot = models.ForeignKey(
        User, on_delete=models.PROTECT,
        related_name='drone_orders', verbose_name="Пілот"
    )
    # Polymorphic reference to FPVDroneType or OpticalDroneType
    content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT,
        null=True, blank=True, verbose_name="Тип БПЛА (тип)"
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    drone_type_obj = GenericForeignKey('content_type', 'object_id')

    batch_id = models.UUIDField(null=True, blank=True, db_index=True, verbose_name="Партія")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Кількість")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES,
        default='pending', verbose_name="Статус"
    )
    notes = models.TextField(blank=True, verbose_name="Примітки пілота")
    handled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='handled_drone_orders', verbose_name="Обробляє"
    )
    master_notes = models.TextField(blank=True, verbose_name="Примітки майстра")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Замовлено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Замовлення дрона"
        verbose_name_plural = "Замовлення дронів"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.pilot} — {self.drone_type_name} x{self.quantity}"

    @property
    def drone_type_name(self):
        obj = self.drone_type_obj
        return str(obj) if obj else '—'

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'info')
