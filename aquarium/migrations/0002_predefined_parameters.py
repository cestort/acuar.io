from decimal import Decimal

from django.db import migrations

# Rangos orientativos habituales en un acuario de arrecife. Se pueden editar desde la app.
PREDEFINED = [
    # code, name, unit, group, min, max, decimals, order
    ("TEMP", "Temperatura", "°C", "physical", "24.5", "26.5", 1, 10),
    ("SAL", "Salinidad", "ppt", "physical", "34.0", "35.5", 1, 20),
    ("PH", "pH", "", "physical", "7.90", "8.40", 2, 30),
    ("KH", "KH (alcalinidad)", "dKH", "major", "7.0", "9.0", 1, 40),
    ("CA", "Calcio", "mg/L", "major", "400", "450", 0, 50),
    ("MG", "Magnesio", "mg/L", "major", "1250", "1400", 0, 60),
    ("NO3", "Nitrato", "mg/L", "nutrient", "2.0", "15.0", 1, 70),
    ("PO4", "Fosfato", "mg/L", "nutrient", "0.03", "0.10", 2, 80),
]


def create_parameters(apps, schema_editor):
    Parameter = apps.get_model("aquarium", "Parameter")
    for code, name, unit, group, min_v, max_v, decimals, order in PREDEFINED:
        Parameter.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "unit": unit,
                "group": group,
                "min_value": Decimal(min_v),
                "max_value": Decimal(max_v),
                "decimals": decimals,
                "order": order,
                "is_predefined": True,
            },
        )


def remove_parameters(apps, schema_editor):
    Parameter = apps.get_model("aquarium", "Parameter")
    Parameter.objects.filter(code__in=[p[0] for p in PREDEFINED], measurements__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("aquarium", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_parameters, remove_parameters),
    ]
