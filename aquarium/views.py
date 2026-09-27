from datetime import timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .charts import build_sparkline
from .forms import MaintenanceEntryForm, MeasurementBatchForm, MeasurementForm, ParameterForm
from .models import MaintenanceEntry, Measurement, Parameter

SPARKLINE_POINTS = 12


def _recent_values(parameter: Parameter, limit: int) -> list[Measurement]:
    """Últimas mediciones en orden cronológico."""
    return list(reversed(parameter.measurements.order_by("-measured_at", "-id")[:limit]))


def dashboard(request):
    cards = []
    for parameter in Parameter.objects.filter(is_active=True):
        recent = _recent_values(parameter, SPARKLINE_POINTS)
        latest = recent[-1] if recent else None
        previous = recent[-2] if len(recent) > 1 else None
        trend = None
        if latest and previous:
            trend = "up" if latest.value > previous.value else "down" if latest.value < previous.value else "flat"
        cards.append(
            {
                "parameter": parameter,
                "latest": latest,
                "status": parameter.status_for(latest.value if latest else None),
                "trend": trend,
                "sparkline": build_sparkline(
                    [m.value for m in recent], parameter.min_value, parameter.max_value
                ),
            }
        )
    out_of_range = [c for c in cards if c["status"] in ("low", "high")]
    return render(
        request,
        "aquarium/dashboard.html",
        {
            "cards": cards,
            "out_of_range": out_of_range,
            "recent_maintenance": MaintenanceEntry.objects.all()[:3],
        },
    )


def measurement_add(request):
    parameters = Parameter.objects.filter(is_active=True)
    selected = request.GET.get("parameter")
    if selected:
        parameters = parameters.filter(pk=selected)

    form = MeasurementBatchForm(request.POST or None, parameters=parameters)
    if request.method == "POST" and form.is_valid():
        created = form.save()
        out = [m for m in created if m.status in ("low", "high")]
        messages.success(request, f"{len(created)} medición(es) guardada(s).")
        if out:
            names = ", ".join(m.parameter.name for m in out)
            messages.warning(request, f"Fuera de rango: {names}.")
        return redirect("aquarium:dashboard")
    return render(request, "aquarium/measurement_add.html", {"form": form, "single": bool(selected)})


def parameter_detail(request, pk):
    parameter = get_object_or_404(Parameter, pk=pk)
    since = timezone.now() - timedelta(days=30)
    stats = parameter.measurements.filter(measured_at__gte=since).aggregate(
        count=Count("id"), avg=Avg("value"), min=Min("value"), max=Max("value")
    )
    recent = _recent_values(parameter, 30)
    page = Paginator(parameter.measurements.all(), 50).get_page(request.GET.get("page"))
    return render(
        request,
        "aquarium/parameter_detail.html",
        {
            "parameter": parameter,
            "stats": {
                "count": stats["count"],
                "avg": parameter.format_value(stats["avg"]),
                "min": parameter.format_value(stats["min"]),
                "max": parameter.format_value(stats["max"]),
            },
            "sparkline": build_sparkline(
                [m.value for m in recent], parameter.min_value, parameter.max_value, width=320, height=120, pad=8
            ),
            "page": page,
        },
    )


def measurement_edit(request, pk):
    measurement = get_object_or_404(Measurement.objects.select_related("parameter"), pk=pk)
    form = MeasurementForm(request.POST or None, instance=measurement)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Medición actualizada.")
        return redirect("aquarium:parameter_detail", pk=measurement.parameter_id)
    return render(request, "aquarium/measurement_edit.html", {"form": form, "measurement": measurement})


@require_POST
def measurement_delete(request, pk):
    measurement = get_object_or_404(Measurement, pk=pk)
    parameter_id = measurement.parameter_id
    measurement.delete()
    messages.success(request, "Medición eliminada.")
    return redirect("aquarium:parameter_detail", pk=parameter_id)


def parameter_list(request):
    parameters = Parameter.objects.annotate(measurement_count=Count("measurements"))
    return render(request, "aquarium/parameter_list.html", {"parameters": parameters})


def parameter_form(request, pk=None):
    parameter = get_object_or_404(Parameter, pk=pk) if pk else None
    form = ParameterForm(request.POST or None, instance=parameter)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Parámetro guardado.")
        return redirect("aquarium:parameter_list")
    return render(request, "aquarium/parameter_form.html", {"form": form, "parameter": parameter})


def maintenance_list(request):
    page = Paginator(MaintenanceEntry.objects.all(), 30).get_page(request.GET.get("page"))
    return render(request, "aquarium/maintenance_list.html", {"page": page})


def maintenance_form(request, pk=None):
    entry = get_object_or_404(MaintenanceEntry, pk=pk) if pk else None
    form = MaintenanceEntryForm(request.POST or None, instance=entry)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Entrada del diario guardada.")
        return redirect("aquarium:maintenance_list")
    return render(request, "aquarium/maintenance_form.html", {"form": form, "entry": entry})


@require_POST
def maintenance_delete(request, pk):
    get_object_or_404(MaintenanceEntry, pk=pk).delete()
    messages.success(request, "Entrada del diario eliminada.")
    return redirect("aquarium:maintenance_list")
