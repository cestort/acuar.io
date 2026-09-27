"""Gráficas pequeñas (sparklines) en SVG calculadas en el servidor, sin JavaScript."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Sparkline:
    width: int
    height: int
    points: str
    last_x: float
    last_y: float
    band_y: float | None
    band_height: float | None


def build_sparkline(
    values: list[Decimal],
    min_target: Decimal | None,
    max_target: Decimal | None,
    width: int = 120,
    height: int = 36,
    pad: int = 4,
) -> Sparkline | None:
    """Recibe los valores en orden cronológico. Devuelve None si hay menos de 2."""
    if len(values) < 2:
        return None

    floats = [float(v) for v in values]
    scale_values = floats + [float(v) for v in (min_target, max_target) if v is not None]
    lo, hi = min(scale_values), max(scale_values)
    if hi == lo:
        lo, hi = lo - 1, hi + 1

    def y(v: float) -> float:
        return round(pad + (hi - v) / (hi - lo) * (height - 2 * pad), 2)

    step = (width - 2 * pad) / (len(floats) - 1)
    coords = [(round(pad + i * step, 2), y(v)) for i, v in enumerate(floats)]

    band_y = band_height = None
    if min_target is not None and max_target is not None:
        top, bottom = y(float(max_target)), y(float(min_target))
        band_y, band_height = top, round(bottom - top, 2)

    return Sparkline(
        width=width,
        height=height,
        points=" ".join(f"{x},{yy}" for x, yy in coords),
        last_x=coords[-1][0],
        last_y=coords[-1][1],
        band_y=band_y,
        band_height=band_height,
    )
