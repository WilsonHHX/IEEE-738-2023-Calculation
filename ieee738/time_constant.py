from dataclasses import dataclass
from math import exp

from .model import Model738


@dataclass
class TimeConstantResult:
    initial_current_a: float
    final_current_a: float
    initial_temp_c: float
    final_temp_c: float
    avg_temp_c: float
    resistance_ohm_per_m: float
    heat_capacity_j_per_m_c: float
    tau_s: float

    @property
    def tau_min(self) -> float:
        return self.tau_s / 60.0


@dataclass
class TimeConstantPoint:
    tau_multiple: float
    time_s: float
    temperature_c: float

    @property
    def time_min(self) -> float:
        return self.time_s / 60.0


def calculate_time_constant(
    model: Model738,
    initial_current_a: float,
    final_current_a: float,
    initial_temp_c: float,
    final_temp_c: float,
) -> TimeConstantResult:
    """
    IEEE 738 Annex D thermal time constant estimate.

    The conductor resistance is evaluated at the average of initial and
    final steady-state conductor temperatures.
    """
    current_square_delta = final_current_a**2 - initial_current_a**2
    temp_delta_c = final_temp_c - initial_temp_c

    if abs(current_square_delta) < 1e-12:
        raise ValueError("initial_current_a and final_current_a cannot be equal.")

    if abs(temp_delta_c) < 1e-12:
        raise ValueError("initial_temp_c and final_temp_c cannot be equal.")

    avg_temp_c = (initial_temp_c + final_temp_c) / 2.0
    resistance_ohm_per_m = model.c.resistance_ohm_per_m(avg_temp_c)
    heat_capacity_j_per_m_c = model.c.heat_capacity()
    tau_s = (
        temp_delta_c
        * heat_capacity_j_per_m_c
        / (resistance_ohm_per_m * current_square_delta)
    )

    if tau_s <= 0:
        raise ValueError("Calculated time constant must be positive.")

    return TimeConstantResult(
        initial_current_a=initial_current_a,
        final_current_a=final_current_a,
        initial_temp_c=initial_temp_c,
        final_temp_c=final_temp_c,
        avg_temp_c=avg_temp_c,
        resistance_ohm_per_m=resistance_ohm_per_m,
        heat_capacity_j_per_m_c=heat_capacity_j_per_m_c,
        tau_s=tau_s,
    )


def time_constant_temperature(
    result: TimeConstantResult,
    time_s: float,
) -> float:
    if time_s < 0:
        raise ValueError("time_s cannot be negative.")

    return result.initial_temp_c + (
        result.final_temp_c - result.initial_temp_c
    ) * (1.0 - exp(-time_s / result.tau_s))


def time_constant_curve(
    result: TimeConstantResult,
    duration_s: float,
    dt_s: float = 10.0,
) -> list[TimeConstantPoint]:
    if duration_s < 0:
        raise ValueError("duration_s cannot be negative.")

    if dt_s <= 0:
        raise ValueError("dt_s must be positive.")

    points = []
    time_s = 0.0

    while time_s < duration_s - 1e-12:
        points.append(
            TimeConstantPoint(
                tau_multiple=time_s / result.tau_s,
                time_s=time_s,
                temperature_c=time_constant_temperature(result, time_s),
            )
        )
        time_s += dt_s

    points.append(
        TimeConstantPoint(
            tau_multiple=duration_s / result.tau_s,
            time_s=duration_s,
            temperature_c=time_constant_temperature(result, duration_s),
        )
    )

    return points


def tau_marker_points(
    result: TimeConstantResult,
    max_multiple: int = 3,
) -> list[TimeConstantPoint]:
    if max_multiple < 1:
        raise ValueError("max_multiple must be at least 1.")

    return [
        TimeConstantPoint(
            tau_multiple=float(multiple),
            time_s=multiple * result.tau_s,
            temperature_c=time_constant_temperature(result, multiple * result.tau_s),
        )
        for multiple in range(1, max_multiple + 1)
    ]
