from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


# ============== ДОВІДНИКИ ==============

class Manufacturer(models.Model):
    """Виробник"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Назва")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    class Meta:
        verbose_name = "Виробник"
        verbose_name_plural = "Виробники"
        ordering = ['name']

    def __str__(self):
        return self.name


class DroneModel(models.Model):
    """Модель дрона (Вирій, Шрайк, Бомбус)"""
    name = models.CharField(max_length=100, verbose_name="Назва")
    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.PROTECT,
        related_name='drone_models',
        verbose_name="Виробник"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    class Meta:
        verbose_name = "Модель дрона"
        verbose_name_plural = "Моделі дронів"
        ordering = ['manufacturer', 'name']
        unique_together = ['manufacturer', 'name']

    def __str__(self):
        return f"{self.manufacturer.name} {self.name}"


class DronePurpose(models.Model):
    """Призначення дрона"""
    name = models.CharField(max_length=100, unique=True, verbose_name="Назва")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    class Meta:
        verbose_name = "Призначення дрона"
        verbose_name_plural = "Призначення дронів"
        ordering = ['name']

    def __str__(self):
        return self.name


class Frequency(models.Model):
    """Частота"""
    UNIT_CHOICES = [
        ('mhz', 'MHz'),
        ('ghz', 'GHz'),
    ]

    value = models.FloatField(verbose_name="Значення")
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, verbose_name="Одиниця")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    class Meta:
        verbose_name = "Частота"
        verbose_name_plural = "Частоти"
        ordering = ['value']
        unique_together = ['value', 'unit']

    def __str__(self):
        return f"{self.value} {self.get_unit_display()}"


# ============== ШАБЛОНИ СУМІСНОСТІ ==============

class PowerTemplate(models.Model):
    """Шаблон живлення для батарей"""

    CONNECTOR_CHOICES = [
        ('xt30', 'XT30'),
        ('xt60', 'XT60'),
        ('xt90', 'XT90'),
        ('deans', 'Deans'),
        ('ec5', 'EC5'),
    ]

    CONFIGURATION_CHOICES = [
        ('3s1p', '3S1P'),
        ('3s2p', '3S2P'),
        ('3s3p', '3S3P'),
        ('4s1p', '4S1P'),
        ('4s2p', '4S2P'),
        ('4s3p', '4S3P'),
        ('4s4p', '4S4P'),
        ('6s1p', '6S1P'),
        ('6s2p', '6S2P'),
        ('6s3p', '6S3P'),
    ]

    name = models.CharField(max_length=100, unique=True, verbose_name="Назва")
    connector = models.CharField(max_length=20, choices=CONNECTOR_CHOICES, verbose_name="Тип конектора")
    configuration = models.CharField(max_length=10, choices=CONFIGURATION_CHOICES, verbose_name="Конфігурація")
    capacity = models.IntegerField(verbose_name="Ємність (mAh)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    class Meta:
        verbose_name = "Шаблон живлення"
        verbose_name_plural = "Шаблони живлення"
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def voltage(self):
        """Автоматичний розрахунок напруги для Li-Ion (3.7V номінал на осередок)"""
        cells = int(self.configuration.split('s')[0])
        return cells * 3.7


class VideoTemplate(models.Model):
    """Шаблон відео для оптоволоконних котушок"""

    name = models.CharField(max_length=100, unique=True, verbose_name="Назва")
    is_analog = models.BooleanField(default=True, verbose_name="Аналоговий сигнал")
    max_distance = models.IntegerField(verbose_name="Дальність польоту (км)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")

    class Meta:
        verbose_name = "Шаблон відео"
        verbose_name_plural = "Шаблони відео"
        ordering = ['name']

    def __str__(self):
        return self.name


# ============== ТИПИ БПЛА ==============

class BaseDroneType(models.Model):
    """Базова абстрактна модель для всіх типів дронів"""

    PROP_SIZE_CHOICES = [
        ('7', '7"'),
        ('8', '8"'),
        ('10', '10"'),
        ('11', '11"'),
        ('13', '13"'),
        ('15', '15"'),
        ('16', '16"'),
    ]

    model = models.ForeignKey(
        DroneModel,
        on_delete=models.PROTECT,
        verbose_name="Модель"
    )
    purpose = models.ForeignKey(
        DronePurpose,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Призначення"
    )
    prop_size = models.CharField(
        max_length=3,
        choices=PROP_SIZE_CHOICES,
        verbose_name="Розмір пропелерів"
    )
    control_frequency = models.ForeignKey(
        Frequency,
        on_delete=models.PROTECT,
        related_name='%(class)s_control',
        verbose_name="Частота керування"
    )
    power_template = models.ForeignKey(
        PowerTemplate,
        on_delete=models.PROTECT,
        verbose_name="Шаблон живлення"
    )
    has_thermal = models.BooleanField(
        default=False,
        verbose_name="Термальна камера"
    )
    is_unusable = models.BooleanField(
        default=False,
        verbose_name="Не може використовуватися"
    )
    notes = models.TextField(blank=True, verbose_name="Примітки")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.model.name} ({self.prop_size}\")"


class FPVDroneType(BaseDroneType):
    """FPV дрони з радіовідео"""

    video_frequency = models.ForeignKey(
        Frequency,
        on_delete=models.PROTECT,
        related_name='fpv_video',
        verbose_name="Частота відео"
    )

    class Meta:
        verbose_name = "Тип FPV дрона"
        verbose_name_plural = "Типи FPV дронів"


class OpticalDroneType(BaseDroneType):
    """Оптичні дрони з оптоволокном"""

    video_template = models.ForeignKey(
        VideoTemplate,
        on_delete=models.PROTECT,
        verbose_name="Шаблон відео"
    )

    class Meta:
        verbose_name = "Тип оптичного дрона"
        verbose_name_plural = "Типи оптичних дронів"


# ============== КОМПЛЕКТУЮЧІ ==============

class BaseComponentType(models.Model):
    """Базова абстрактна модель для всіх типів комплектуючих"""

    model = models.CharField(max_length=100, verbose_name="Модель")
    notes = models.TextField(blank=True, verbose_name="Примітки")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        abstract = True

    def __str__(self):
        return self.model


class BatteryType(BaseComponentType):
    """Типи батарей"""

    power_template = models.ForeignKey(
        PowerTemplate,
        on_delete=models.PROTECT,
        verbose_name="Шаблон живлення"
    )

    class Meta:
        verbose_name = "Тип батареї"
        verbose_name_plural = "Типи батарей"


class SpoolType(BaseComponentType):
    """Типи котушок"""

    video_template = models.ForeignKey(
        VideoTemplate,
        on_delete=models.PROTECT,
        verbose_name="Шаблон відео"
    )

    class Meta:
        verbose_name = "Тип котушки"
        verbose_name_plural = "Типи котушок"


class OtherComponentType(BaseComponentType):
    """Інші комплектуючі"""

    CATEGORY_CHOICES = [
        ('controller', 'Пульт'),
        ('charger', 'Зарядка'),
        ('propeller', 'Пропелер'),
        ('other', 'Інше'),
    ]

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name="Категорія"
    )

    class Meta:
        verbose_name = "Інша комплектуюча"
        verbose_name_plural = "Інші комплектуючі"


class Component(models.Model):
    """Конкретні екземпляри комплектуючих"""

    STATUS_CHOICES = [
        ('available', 'Доступна'),
        ('in_use', 'Використовується'),
        ('damaged', 'Пошкоджена'),
        ('retired', 'Списана'),
    ]

    # Полиморфне посилання на тип комплектуючої
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        verbose_name="Тип комплектуючої"
    )
    object_id = models.PositiveIntegerField()
    component_type = GenericForeignKey('content_type', 'object_id')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available',
        verbose_name="Статус"
    )
    assigned_to_uav = models.ForeignKey(
        'UAVInstance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='components',
        verbose_name="Закріплена за БПЛА"
    )
    notes = models.TextField(blank=True, verbose_name="Примітки")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "Комплектуюча"
        verbose_name_plural = "Комплектуючі"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.component_type} - {self.status}"


# ============== ІНВЕНТАРНІ ЕКЗЕМПЛЯРИ ==============

class UAVInstance(models.Model):
    """Конкретні екземпляри БПЛА в інвентарі"""

    STATUS_CHOICES = [
        ('inspection', 'На перевірці'),
        ('ready', 'Готовий'),
        ('repair', 'Ремонт'),
        ('deferred', 'Відкладено'),
    ]

    # Полиморфне посилання на тип БПЛА
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        verbose_name="Тип БПЛА"
    )
    object_id = models.PositiveIntegerField()
    uav_type = GenericForeignKey('content_type', 'object_id')

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='inspection',
        verbose_name="Статус"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_uavs',
        verbose_name="Додав"
    )
    notes = models.TextField(blank=True, verbose_name="Примітки")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Створено")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Оновлено")

    class Meta:
        verbose_name = "БПЛА (екземпляр)"
        verbose_name_plural = "БПЛА (екземпляри)"
        ordering = ['-created_at']

    def __str__(self):
        return f"БПЛА #{self.pk} - {self.uav_type}"

    def get_category(self):
        """Отримати категорію БПЛА"""
        type_map = {
            'fpvdronetype': 'FPV',
            'opticaldronetype': 'Оптика',
        }
        return type_map.get(self.content_type.model, 'Невідомо')
