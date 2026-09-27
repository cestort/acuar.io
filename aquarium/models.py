from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Parameter(models.Model):
    """Un parámetro del agua que se mide (KH, Ca, temperatura...)."""

    class Group(models.TextChoices):
        PHYSICAL = "physical", "Físicos"
        MAJOR = "major", "Mayoritarios"
        NUTRIENT = "nutrient", "Nutrientes"
        CUSTOM = "custom", "Otros"

    code = models.CharField("código", max_length=20, unique=True, help_text="Nombre corto, p. ej. KH.")
    name = models.CharField("nombre", max_length=80)
    unit = models.CharField("unidad", max_length=20, blank=True)
    group = models.CharField("grupo", max_length=20, choices=Group.choices, default=Group.CUSTOM)
    min_value = models.DecimalField("mínimo objetivo", max_digits=10, decimal_places=4, null=True, blank=True)
    max_value = models.DecimalField("máximo objetivo", max_digits=10, decimal_places=4, null=True, blank=True)
    decimals = models.PositiveSmallIntegerField("decimales a mostrar", default=2)
    order = models.PositiveSmallIntegerField("orden", default=100)
    is_active = models.BooleanField("activo", default=True)
    is_predefined = models.BooleanField("predefinido", default=False, editable=False)
    description = models.TextField("descripción", blank=True)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "parámetro"
        verbose_name_plural = "parámetros"

    def __str__(self) -> str:
        return f"{self.name} ({self.unit})" if self.unit else self.name

    def clean(self):
        if self.min_value is not None and self.max_value is not None and self.min_value > self.max_value:
            raise ValidationError({"max_value": "El máximo debe ser mayor o igual que el mínimo."})

    def status_for(self, value: Decimal | None) -> str:
        """Devuelve 'ok', 'low', 'high' o 'unknown' para un valor."""
        if value is None:
            return "unknown"
        if self.min_value is not None and value < self.min_value:
            return "low"
        if self.max_value is not None and value > self.max_value:
            return "high"
        if self.min_value is None and self.max_value is None:
            return "unknown"
        return "ok"

    def format_value(self, value: Decimal | None) -> str:
        if value is None:
            return "—"
        return f"{value:.{self.decimals}f}".replace(".", ",")

    @property
    def range_display(self) -> str:
        """Rango objetivo legible, p. ej. '7,0 – 9,0'."""
        if self.min_value is not None and self.max_value is not None:
            return f"{self.format_value(self.min_value)} – {self.format_value(self.max_value)}"
        if self.min_value is not None:
            return f"≥ {self.format_value(self.min_value)}"
        if self.max_value is not None:
            return f"≤ {self.format_value(self.max_value)}"
        return ""


class Measurement(models.Model):
    """Una medición de un parámetro en un momento dado."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        KH_GUARDIAN = "kh_guardian", "KH Guardian"
        OTHER = "other", "Otro dispositivo"

    parameter = models.ForeignKey(
        Parameter, on_delete=models.PROTECT, related_name="measurements", verbose_name="parámetro"
    )
    value = models.DecimalField("valor", max_digits=10, decimal_places=4)
    measured_at = models.DateTimeField("fecha de medición", default=timezone.now, db_index=True)
    source = models.CharField("origen", max_length=20, choices=Source.choices, default=Source.MANUAL)
    notes = models.TextField("notas", blank=True)
    created_at = models.DateTimeField("registrado", auto_now_add=True)

    class Meta:
        ordering = ["-measured_at", "-id"]
        indexes = [models.Index(fields=["parameter", "-measured_at"], name="measurement_param_date")]
        verbose_name = "medición"
        verbose_name_plural = "mediciones"

    def __str__(self) -> str:
        return f"{self.parameter.code} = {self.value} ({self.measured_at:%Y-%m-%d %H:%M})"

    @property
    def status(self) -> str:
        return self.parameter.status_for(self.value)

    @property
    def formatted_value(self) -> str:
        return self.parameter.format_value(self.value)


class MaintenanceEntry(models.Model):
    """Entrada del diario de mantenimiento."""

    class Category(models.TextChoices):
        WATER_CHANGE = "water_change", "Cambio de agua"
        DOSING = "dosing", "Dosificación"
        LIVESTOCK = "livestock", "Fauna / corales"
        EQUIPMENT = "equipment", "Equipo"
        CLEANING = "cleaning", "Limpieza"
        OTHER = "other", "Otro"

    occurred_at = models.DateTimeField("fecha", default=timezone.now, db_index=True)
    category = models.CharField("categoría", max_length=20, choices=Category.choices, default=Category.OTHER)
    title = models.CharField("título", max_length=150)
    description = models.TextField("descripción", blank=True)
    created_at = models.DateTimeField("registrado", auto_now_add=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        verbose_name = "entrada del diario"
        verbose_name_plural = "diario de mantenimiento"

    def __str__(self) -> str:
        return f"{self.occurred_at:%Y-%m-%d} · {self.title}"
