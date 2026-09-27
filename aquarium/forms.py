from django import forms
from django.utils import timezone

from .models import MaintenanceEntry, Measurement, Parameter

DATETIME_LOCAL_FORMAT = "%Y-%m-%dT%H:%M"


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format=DATETIME_LOCAL_FORMAT, **kwargs)


def local_now():
    return timezone.localtime().replace(second=0, microsecond=0)


def datetime_field(label: str) -> forms.DateTimeField:
    return forms.DateTimeField(
        label=label,
        widget=DateTimeLocalInput(),
        input_formats=[DATETIME_LOCAL_FORMAT, "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"],
    )


def value_field(parameter: Parameter) -> forms.DecimalField:
    return forms.DecimalField(
        label=parameter.name,
        required=False,
        max_digits=10,
        decimal_places=4,
        localize=True,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}),
    )


class MeasurementBatchForm(forms.Form):
    """Registra varios parámetros de un mismo test en una sola pantalla."""

    measured_at = datetime_field("Fecha y hora")
    notes = forms.CharField(
        label="Notas",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Kit usado, observaciones…"}),
    )

    def __init__(self, *args, parameters, **kwargs):
        super().__init__(*args, **kwargs)
        self.parameters = list(parameters)
        if not self.is_bound:
            self.fields["measured_at"].initial = local_now()
        for parameter in self.parameters:
            self.fields[self.field_name(parameter)] = value_field(parameter)

    @staticmethod
    def field_name(parameter: Parameter) -> str:
        return f"value_{parameter.pk}"

    def value_fields(self):
        """Pares (parámetro, campo enlazado) para pintar el formulario."""
        return [(p, self[self.field_name(p)]) for p in self.parameters]

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(self.field_name(p)) is not None for p in self.parameters):
            raise forms.ValidationError("Introduce al menos un valor.")
        return cleaned

    def save(self) -> list[Measurement]:
        measured_at = self.cleaned_data["measured_at"]
        notes = self.cleaned_data.get("notes", "")
        measurements = [
            Measurement(
                parameter=parameter,
                value=self.cleaned_data[self.field_name(parameter)],
                measured_at=measured_at,
                notes=notes,
                source=Measurement.Source.MANUAL,
            )
            for parameter in self.parameters
            if self.cleaned_data.get(self.field_name(parameter)) is not None
        ]
        return Measurement.objects.bulk_create(measurements)


class MeasurementForm(forms.ModelForm):
    measured_at = datetime_field("Fecha y hora")

    class Meta:
        model = Measurement
        fields = ["value", "measured_at", "notes"]
        localized_fields = ["value"]
        widgets = {
            "value": forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class ParameterForm(forms.ModelForm):
    class Meta:
        model = Parameter
        fields = ["code", "name", "unit", "group", "min_value", "max_value", "decimals", "order", "is_active", "description"]
        localized_fields = ["min_value", "max_value"]
        widgets = {
            "min_value": forms.TextInput(attrs={"inputmode": "decimal"}),
            "max_value": forms.TextInput(attrs={"inputmode": "decimal"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class MaintenanceEntryForm(forms.ModelForm):
    occurred_at = datetime_field("Fecha y hora")

    class Meta:
        model = MaintenanceEntry
        fields = ["occurred_at", "category", "title", "description"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "p. ej. Cambio de agua de 20 L"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.fields["occurred_at"].initial = local_now()
