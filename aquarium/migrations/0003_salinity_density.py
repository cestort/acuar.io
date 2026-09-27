from decimal import Decimal

from django.db import migrations


def salinity_to_density(apps, schema_editor):
    Parameter = apps.get_model("aquarium", "Parameter")
    Parameter.objects.filter(code="SAL").update(
        name="Salinidad (densidad)",
        unit="SG",
        min_value=Decimal("1.0240"),
        max_value=Decimal("1.0260"),
        decimals=3,
    )


def density_to_ppt(apps, schema_editor):
    Parameter = apps.get_model("aquarium", "Parameter")
    Parameter.objects.filter(code="SAL").update(
        name="Salinidad",
        unit="ppt",
        min_value=Decimal("34.0"),
        max_value=Decimal("35.5"),
        decimals=1,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("aquarium", "0002_predefined_parameters"),
    ]

    operations = [
        migrations.RunPython(salinity_to_density, density_to_ppt),
    ]
