from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.text import slugify


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class TimeStampedModel(models.Model):
    """Reusable created/updated timestamp mixin."""

    created_at = models.DateTimeField("Створено", auto_now_add=True)
    updated_at = models.DateTimeField("Оновлено", auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Drone hierarchy: Category -> Type -> Drone (instance)
# ---------------------------------------------------------------------------

class DroneCategory(TimeStampedModel):
    """Top-level drone category (e.g. FPV, Mavic, Matrice, Autel, Wing)."""

    name = models.CharField("Назва", max_length=100, unique=True)
    slug = models.SlugField("Slug", unique=True, blank=True)
    description = models.TextField("Опис", blank=True)

    class Meta:
        verbose_name = "Категорія дрона"
        verbose_name_plural = "Категорії дронів"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Manufacturer(TimeStampedModel):
    """Drone / component manufacturer (e.g. DJI, Autel, TBS)."""

    name = models.CharField("Назва", max_length=100, unique=True)
    slug = models.SlugField("Slug", unique=True, blank=True)
    website = models.URLField("Сайт", blank=True)
    description = models.TextField("Опис", blank=True)

    class Meta:
        verbose_name = "Виробник"
        verbose_name_plural = "Виробники"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class DroneModel(TimeStampedModel):
    """Specific drone model name (e.g. Mavic 3, Matrice 350 RTK)."""

    name = models.CharField("Назва", max_length=100, unique=True)
    slug = models.SlugField("Slug", unique=True, blank=True)
    description = models.TextField("Опис", blank=True)

    class Meta:
        verbose_name = "Модель дрона"
        verbose_name_plural = "Моделі дронів"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Frequency(TimeStampedModel):
    """Reusable frequency value (e.g. 868 МГц, 2.4 ГГц, 5.8 ГГц)."""

    value = models.CharField("Значення", max_length=50, unique=True)

    class Meta:
        verbose_name = "Частота"
        verbose_name_plural = "Частоти"
        ordering = ["value"]

    def __str__(self):
        return self.value


class DroneType(TimeStampedModel):
    """Specific drone model / product line."""

    name = models.CharField("Назва", max_length=200, blank=True)

    category = models.ForeignKey(
        DroneCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drone_types",
        verbose_name="Категорія",
    )
    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drone_types",
        verbose_name="Виробник",
    )
    model = models.ForeignKey(
        DroneModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drone_types",
        verbose_name="Модель",
    )

    # Capability flags
    has_thermal_camera = models.BooleanField("Термальна камера", default=False)
    is_night_capable = models.BooleanField("Нічний режим", default=False)
    has_optical_fiber = models.BooleanField("Оптоволокно", default=False)
    has_guidance_system = models.BooleanField("Система донаведення", default=False)

    # Frequencies
    control_frequency = models.ForeignKey(
        Frequency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="control_drone_types",
        verbose_name="Частота керування",
    )
    video_frequency = models.ForeignKey(
        Frequency,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_drone_types",
        verbose_name="Частота відео",
    )

    notes = models.TextField("Примітки", blank=True)

    class Meta:
        verbose_name = "Тип дрона"
        verbose_name_plural = "Типи дронів"
        unique_together = ["manufacturer", "model"]
        ordering = ["manufacturer", "model"]

    def __str__(self):
        return f"{self.manufacturer} {self.model}"


class Drone(TimeStampedModel):
    """Physical drone unit in the inventory."""

    STATUS_CHOICES = [
        ("operational", "Працює"),
        ("maintenance", "На обслуговуванні"),
        ("damaged", "Пошкоджений"),
        ("repair", "В ремонті"),
        ("retired", "Списаний"),
    ]

    drone_type = models.ForeignKey(
        DroneType,
        on_delete=models.PROTECT,
        related_name="drones",
        verbose_name="Тип дрона",
    )
    serial_number = models.CharField("Серійний номер", max_length=100, unique=True)
    inventory_number = models.CharField("Інвентарний номер", max_length=50, unique=True)

    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="operational",
    )

    # Financial
    purchase_date = models.DateField("Дата придбання")
    purchase_price = models.DecimalField(
        "Ціна придбання", max_digits=10, decimal_places=2, null=True, blank=True,
    )

    # Location & assignment
    current_location = models.CharField("Поточна локація", max_length=200, blank=True)
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_drones",
        verbose_name="Відповідальна особа",
    )

    # Usage tracking
    total_flight_hours = models.FloatField("Загальний наліт (год)", default=0)
    total_flights = models.IntegerField("Кількість польотів", default=0)

    notes = models.TextField("Примітки", blank=True)

    class Meta:
        verbose_name = "Дрон"
        verbose_name_plural = "Дрони"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory_number} – {self.drone_type}"


# ---------------------------------------------------------------------------
# Component hierarchy: ComponentCategory -> ComponentType -> Component
# ---------------------------------------------------------------------------

class ComponentCategory(TimeStampedModel):
    """Dynamic, user-manageable category for components.

    Replaces a hard-coded choices list so new categories (battery, spool,
    propeller, camera, controller, charger, gimbal, antenna, case, …) can
    be added at any time via the admin panel.
    """

    name = models.CharField("Назва", max_length=100, unique=True)
    slug = models.SlugField("Slug", unique=True, blank=True)
    description = models.TextField("Опис", blank=True)

    class Meta:
        verbose_name = "Категорія комплектуючої"
        verbose_name_plural = "Категорії комплектуючих"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class ComponentType(TimeStampedModel):
    """A product-line description for a component (e.g. "Tattu 6S 1300 mAh")."""

    category = models.ForeignKey(
        ComponentCategory,
        on_delete=models.PROTECT,
        related_name="component_types",
        verbose_name="Категорія",
    )
    name = models.CharField("Назва", max_length=100)
    manufacturer = models.CharField("Виробник", max_length=100, blank=True)
    model = models.CharField("Модель", max_length=100, blank=True)

    compatible_drone_types = models.ManyToManyField(
        DroneType,
        blank=True,
        related_name="compatible_components",
        verbose_name="Сумісні типи дронів",
    )

    # Arbitrary specs as JSON (capacity_mah, voltage, fiber_length, …)
    specifications = models.JSONField(
        "Характеристики", default=dict, blank=True,
    )
    description = models.TextField("Опис", blank=True)

    class Meta:
        verbose_name = "Тип комплектуючої"
        verbose_name_plural = "Типи комплектуючих"
        unique_together = ["category", "manufacturer", "model"]
        ordering = ["category", "name"]

    def __str__(self):
        parts = [self.category.name]
        if self.manufacturer and self.model:
            parts.append(f"{self.manufacturer} {self.model}")
        else:
            parts.append(self.name)
        return " – ".join(parts)


class Component(TimeStampedModel):
    """Physical component unit in the inventory."""

    STATUS_CHOICES = [
        ("available", "Доступна"),
        ("in_use", "Використовується"),
        ("charging", "На зарядці"),
        ("maintenance", "На обслуговуванні"),
        ("damaged", "Пошкоджена"),
        ("retired", "Списана"),
    ]

    component_type = models.ForeignKey(
        ComponentType,
        on_delete=models.PROTECT,
        related_name="components",
        verbose_name="Тип комплектуючої",
    )
    serial_number = models.CharField("Серійний номер", max_length=100, blank=True)
    inventory_number = models.CharField(
        "Інвентарний номер", max_length=50, unique=True,
    )

    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="available",
    )

    # Financial
    purchase_date = models.DateField("Дата придбання")
    purchase_price = models.DecimalField(
        "Ціна придбання", max_digits=10, decimal_places=2, null=True, blank=True,
    )

    # Battery-specific fields
    current_charge_cycles = models.IntegerField(
        "Поточна кількість циклів заряду", default=0, null=True, blank=True,
    )
    health_percentage = models.IntegerField(
        "Здоров'я батареї (%)", default=100, null=True, blank=True,
    )
    last_charge_date = models.DateField(
        "Остання зарядка", null=True, blank=True,
    )

    # Spool-specific fields
    remaining_fiber_length = models.FloatField(
        "Залишок оптоволокна (м)", null=True, blank=True,
    )

    # Assignment
    assigned_to_drone = models.ForeignKey(
        Drone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="components",
        verbose_name="Закріплена за дроном",
    )

    current_location = models.CharField("Поточна локація", max_length=200, blank=True)
    notes = models.TextField("Примітки", blank=True)

    class Meta:
        verbose_name = "Комплектуюча"
        verbose_name_plural = "Комплектуючі"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory_number} – {self.component_type}"


# ---------------------------------------------------------------------------
# Operational logs
# ---------------------------------------------------------------------------

class FlightLog(models.Model):
    """Single flight record."""

    drone = models.ForeignKey(
        Drone,
        on_delete=models.CASCADE,
        related_name="flight_logs",
        verbose_name="Дрон",
    )
    pilot = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="flights",
        verbose_name="Пілот",
    )

    flight_date = models.DateTimeField("Дата і час польоту")
    duration_minutes = models.IntegerField("Тривалість (хв)")

    batteries_used = models.ManyToManyField(
        Component,
        blank=True,
        related_name="flight_logs",
        verbose_name="Використані батареї",
    )

    # Mission details
    mission_type = models.CharField("Тип місії", max_length=100, blank=True)
    location = models.CharField("Локація", max_length=200, blank=True)
    weather_conditions = models.CharField("Погодні умови", max_length=200, blank=True)

    # Flight results
    distance_km = models.FloatField("Дистанція (км)", null=True, blank=True)
    max_altitude = models.FloatField("Макс. висота (м)", null=True, blank=True)

    notes = models.TextField("Примітки", blank=True)
    created_at = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        verbose_name = "Запис про політ"
        verbose_name_plural = "Журнал польотів"
        ordering = ["-flight_date"]

    def __str__(self):
        return (
            f"{self.drone.inventory_number} – "
            f"{self.flight_date.strftime('%Y-%m-%d %H:%M')}"
        )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.drone.total_flight_hours += self.duration_minutes / 60
            self.drone.total_flights += 1
            self.drone.save(update_fields=["total_flight_hours", "total_flights"])


class MaintenanceRecord(models.Model):
    """Maintenance / repair journal entry."""

    MAINTENANCE_TYPES = [
        ("scheduled", "Планове ТО"),
        ("repair", "Ремонт"),
        ("upgrade", "Модернізація"),
        ("inspection", "Огляд"),
        ("calibration", "Калібрування"),
    ]

    drone = models.ForeignKey(
        Drone,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="maintenance_records",
        verbose_name="Дрон",
    )
    component = models.ForeignKey(
        Component,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="maintenance_records",
        verbose_name="Комплектуюча",
    )

    maintenance_type = models.CharField(
        "Тип обслуговування", max_length=20, choices=MAINTENANCE_TYPES,
    )
    date = models.DateField("Дата")

    description = models.TextField("Опис")
    parts_replaced = models.TextField("Замінені деталі", blank=True)

    cost = models.DecimalField(
        "Вартість", max_digits=10, decimal_places=2, null=True, blank=True,
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="performed_maintenance",
        verbose_name="Виконавець",
    )

    next_maintenance_date = models.DateField("Наступне ТО", null=True, blank=True)
    created_at = models.DateTimeField("Створено", auto_now_add=True)

    class Meta:
        verbose_name = "Запис про обслуговування"
        verbose_name_plural = "Журнал обслуговування"
        ordering = ["-date"]

    def __str__(self):
        target = self.drone or self.component
        return f"{self.get_maintenance_type_display()} – {target} ({self.date})"

    def clean(self):
        if not self.drone and not self.component:
            raise ValidationError(
                "Необхідно вказати дрон або комплектуючу."
            )
        if self.drone and self.component:
            raise ValidationError(
                "Можна вказати лише дрон АБО комплектуючу, не обидва."
            )
