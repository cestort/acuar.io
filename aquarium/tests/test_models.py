from decimal import Decimal

from django.test import TestCase

from aquarium.charts import build_sparkline
from aquarium.models import Measurement, Parameter


class PredefinedParametersTests(TestCase):
    def test_eight_predefined_parameters_exist(self):
        codes = set(Parameter.objects.filter(is_predefined=True).values_list("code", flat=True))
        self.assertEqual(codes, {"TEMP", "SAL", "PH", "KH", "CA", "MG", "NO3", "PO4"})


class ParameterStatusTests(TestCase):
    def setUp(self):
        self.kh = Parameter.objects.get(code="KH")  # 7.0 – 9.0

    def test_status(self):
        self.assertEqual(self.kh.status_for(Decimal("8.2")), "ok")
        self.assertEqual(self.kh.status_for(Decimal("7.0")), "ok")
        self.assertEqual(self.kh.status_for(Decimal("6.9")), "low")
        self.assertEqual(self.kh.status_for(Decimal("9.1")), "high")
        self.assertEqual(self.kh.status_for(None), "unknown")

    def test_status_without_range(self):
        p = Parameter.objects.create(code="K", name="Potasio", unit="mg/L")
        self.assertEqual(p.status_for(Decimal("400")), "unknown")

    def test_format_uses_decimals_and_comma(self):
        self.assertEqual(self.kh.format_value(Decimal("8.25")), "8,2")
        self.assertEqual(self.kh.range_display, "7,0 – 9,0")

    def test_measurement_default_source_is_manual(self):
        m = Measurement.objects.create(parameter=self.kh, value=Decimal("8.1"))
        self.assertEqual(m.source, Measurement.Source.MANUAL)
        self.assertEqual(m.status, "ok")


class SparklineTests(TestCase):
    def test_needs_two_points(self):
        self.assertIsNone(build_sparkline([Decimal("1")], None, None))

    def test_points_and_band(self):
        s = build_sparkline([Decimal("7"), Decimal("8"), Decimal("9")], Decimal("7"), Decimal("9"), width=100, height=40, pad=0)
        self.assertEqual(s.points, "0.0,40.0 50.0,20.0 100.0,0.0")
        self.assertEqual((s.band_y, s.band_height), (0.0, 40.0))

    def test_flat_series(self):
        s = build_sparkline([Decimal("5"), Decimal("5")], None, None)
        self.assertIsNotNone(s)
