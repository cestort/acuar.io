from django.contrib import admin

from .models import MaintenanceEntry, Measurement, Parameter


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "unit", "group", "min_value", "max_value", "is_active", "order")
    list_editable = ("is_active", "order")
    list_filter = ("group", "is_active", "is_predefined")


@admin.register(Measurement)
class MeasurementAdmin(admin.ModelAdmin):
    list_display = ("parameter", "value", "measured_at", "source")
    list_filter = ("parameter", "source")
    date_hierarchy = "measured_at"


@admin.register(MaintenanceEntry)
class MaintenanceEntryAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "category", "title")
    list_filter = ("category",)
    date_hierarchy = "occurred_at"
    search_fields = ("title", "description")
