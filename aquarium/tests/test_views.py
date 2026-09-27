from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from aquarium.models import MaintenanceEntry, Measurement, Parameter


class HealthTests(TestCase):
    def test_health(self):
        response = self.client.get("/health/")
        self.assertEqual(response.json(), {"status": "ok"})


class DashboardTests(TestCase):
    def test_empty_dashboard(self):
        response = self.client.get(reverse("aquarium:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin datos")

    def test_out_of_range_banner(self):
        kh = Parameter.objects.get(code="KH")
        Measurement.objects.create(parameter=kh, value=Decimal("6.0"))
        Measurement.objects.create(parameter=kh, value=Decimal("6.5"))
        response = self.client.get(reverse("aquarium:dashboard"))
        self.assertContains(response, "1 fuera de rango")
        self.assertContains(response, "6,5")
        self.assertContains(response, "<polyline", html=False)

    def test_inactive_parameters_hidden(self):
        Parameter.objects.filter(code="PO4").update(is_active=False)
        response = self.client.get(reverse("aquarium:dashboard"))
        self.assertNotContains(response, "Fosfato")


class MeasurementBatchTests(TestCase):
    def setUp(self):
        self.kh = Parameter.objects.get(code="KH")
        self.ca = Parameter.objects.get(code="CA")
        self.url = reverse("aquarium:measurement_add")

    def test_saves_only_filled_values_with_comma_or_dot(self):
        response = self.client.post(
            self.url,
            {
                "measured_at": "2026-09-27T20:30",
                f"value_{self.kh.pk}": "8,2",
                f"value_{self.ca.pk}": "430.5",
                "notes": "Salifert",
            },
        )
        self.assertRedirects(response, reverse("aquarium:dashboard"))
        values = dict(Measurement.objects.values_list("parameter__code", "value"))
        self.assertEqual(values, {"KH": Decimal("8.2"), "CA": Decimal("430.5")})
        self.assertTrue(all(m.notes == "Salifert" for m in Measurement.objects.all()))

    def test_requires_at_least_one_value(self):
        response = self.client.post(self.url, {"measured_at": "2026-09-27T20:30"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Introduce al menos un valor.")
        self.assertEqual(Measurement.objects.count(), 0)

    def test_out_of_range_warning(self):
        response = self.client.post(
            self.url, {"measured_at": "2026-09-27T20:30", f"value_{self.kh.pk}": "10"}, follow=True
        )
        self.assertContains(response, "Fuera de rango: KH (alcalinidad).")

    def test_single_parameter_mode(self):
        response = self.client.get(self.url, {"parameter": self.kh.pk})
        self.assertContains(response, f'name="value_{self.kh.pk}"')
        self.assertNotContains(response, f'name="value_{self.ca.pk}"')


class ParameterViewsTests(TestCase):
    def test_detail_with_history(self):
        kh = Parameter.objects.get(code="KH")
        for v in ("7.5", "8.0", "8.4"):
            Measurement.objects.create(parameter=kh, value=Decimal(v), notes="nota")
        response = self.client.get(reverse("aquarium:parameter_detail", args=[kh.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "8,4")
        self.assertContains(response, "spark--large")

    def test_create_custom_parameter(self):
        response = self.client.post(
            reverse("aquarium:parameter_create"),
            {"code": "k", "name": "Potasio", "unit": "mg/L", "group": "custom",
             "min_value": "380", "max_value": "420", "decimals": "0", "order": "90", "is_active": "on"},
        )
        self.assertRedirects(response, reverse("aquarium:parameter_list"))
        p = Parameter.objects.get(code="K")
        self.assertFalse(p.is_predefined)

    def test_min_greater_than_max_rejected(self):
        response = self.client.post(
            reverse("aquarium:parameter_create"),
            {"code": "X", "name": "X", "group": "custom", "min_value": "5", "max_value": "1",
             "decimals": "1", "order": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Parameter.objects.filter(code="X").exists())

    def test_edit_and_delete_measurement(self):
        kh = Parameter.objects.get(code="KH")
        m = Measurement.objects.create(parameter=kh, value=Decimal("8"))
        self.client.post(
            reverse("aquarium:measurement_edit", args=[m.pk]),
            {"value": "8,5", "measured_at": "2026-09-27T10:00", "notes": ""},
        )
        m.refresh_from_db()
        self.assertEqual(m.value, Decimal("8.5"))
        self.assertEqual(self.client.get(reverse("aquarium:measurement_delete", args=[m.pk])).status_code, 405)
        self.client.post(reverse("aquarium:measurement_delete", args=[m.pk]))
        self.assertFalse(Measurement.objects.exists())


class MaintenanceViewsTests(TestCase):
    def test_create_list_delete(self):
        self.client.post(
            reverse("aquarium:maintenance_create"),
            {"occurred_at": "2026-09-20T11:00", "category": "water_change", "title": "Cambio de 20 L"},
        )
        entry = MaintenanceEntry.objects.get()
        response = self.client.get(reverse("aquarium:maintenance_list"))
        self.assertContains(response, "Cambio de 20 L")
        self.client.post(reverse("aquarium:maintenance_delete", args=[entry.pk]))
        self.assertFalse(MaintenanceEntry.objects.exists())
