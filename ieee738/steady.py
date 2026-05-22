from dataclasses import dataclass
from math import sqrt

from .model import Model738
from .radial import solve_radial_gradient


@dataclass
class SteadyStateResult:
    surface_temp_c: float
    avg_temp_c: float
    current_a: float

    q_c_w_per_m: float
    q_r_w_per_m: float
    q_s_w_per_m: float
    q_joule_w_per_m: float

    heating_w_per_m: float
    cooling_w_per_m: float
    net_heat_w_per_m: float

    resistance_ohm_per_km: float


def steady_state_ampacity(
    model: Model738,
    ts_c: float,
    tavg_c: float | None = None,
    use_radial_gradient: bool = False,
    kth_w_per_m_c: float = 1.0,
    tolerance_a: float = 1e-6,
    max_iter: int = 50,
) -> float:
    """
    Given conductor surface temperature, calculate steady-state ampacity.

    Without radial gradient:
        Tavg = Ts

    With radial gradient:
        iterate current -> radial Tavg -> resistance -> current.
    """
    if tavg_c is None:
        tavg_c = ts_c

    numerator = model.qc(ts_c) + model.qr(ts_c) - model.qs()

    if numerator <= 0:
        raise ValueError("qc + qr - qs must be positive.")

    if not use_radial_gradient:
        return sqrt(numerator / model.c.resistance_ohm_per_m(tavg_c))

    current_a = sqrt(numerator / model.c.resistance_ohm_per_m(ts_c))

    for _ in range(max_iter):
        radial = solve_radial_gradient(
            model=model,
            surface_temp_c=ts_c,
            current_a=current_a,
            kth_w_per_m_c=kth_w_per_m_c,
        )

        new_current_a = sqrt(
            numerator / model.c.resistance_ohm_per_m(radial.avg_temp_c)
        )

        if abs(new_current_a - current_a) <= tolerance_a:
            return new_current_a

        current_a = new_current_a

    return current_a


def steady_state_report_from_temperature(
    model: Model738,
    ts_c: float,
    use_radial_gradient: bool = False,
    kth_w_per_m_c: float = 1.0,
) -> SteadyStateResult:
    """
    Given conductor surface temperature, return full steady-state report.
    """
    current_a = steady_state_ampacity(
        model=model,
        ts_c=ts_c,
        use_radial_gradient=use_radial_gradient,
        kth_w_per_m_c=kth_w_per_m_c,
    )

    tavg_c = ts_c

    if use_radial_gradient:
        radial = solve_radial_gradient(
            model=model,
            surface_temp_c=ts_c,
            current_a=current_a,
            kth_w_per_m_c=kth_w_per_m_c,
        )
        tavg_c = radial.avg_temp_c

    terms = model.heat_terms(
        ts_c=ts_c,
        tavg_c=tavg_c,
        current_a=current_a,
    )

    return SteadyStateResult(
        surface_temp_c=ts_c,
        avg_temp_c=tavg_c,
        current_a=current_a,

        q_c_w_per_m=terms["q_c_W_per_m"],
        q_r_w_per_m=terms["q_r_W_per_m"],
        q_s_w_per_m=terms["q_s_W_per_m"],
        q_joule_w_per_m=terms["q_joule_W_per_m"],

        heating_w_per_m=terms["heating_W_per_m"],
        cooling_w_per_m=terms["cooling_W_per_m"],
        net_heat_w_per_m=terms["net_heat_W_per_m"],

        resistance_ohm_per_km=terms["R_ohm_per_km"],
    )


def steady_state_residual(
    model: Model738,
    current_a: float,
    ts_c: float,
) -> float:
    """
    Residual for solving conductor temperature from current.

        residual = cooling - heating

    residual > 0:
        assumed temperature is too high

    residual < 0:
        assumed temperature is too low
    """
    terms = model.heat_terms(
        ts_c=ts_c,
        tavg_c=ts_c,
        current_a=current_a,
    )

    return terms["cooling_W_per_m"] - terms["heating_W_per_m"]


def solve_steady_state_temperature(
    model: Model738,
    current_a: float,
    low_c: float = -50.0,
    high_c: float = 300.0,
    tolerance_c: float = 1e-4,
    max_iter: int = 100,
) -> float:
    """
    Given current, solve steady-state conductor temperature.

    Uses bisection.
    """
    f_low = steady_state_residual(model, current_a, low_c)
    f_high = steady_state_residual(model, current_a, high_c)

    if f_low * f_high > 0:
        raise ValueError("Temperature range does not bracket the solution.")

    for _ in range(max_iter):
        mid_c = (low_c + high_c) / 2.0
        f_mid = steady_state_residual(model, current_a, mid_c)

        if abs(high_c - low_c) < tolerance_c or abs(f_mid) < 1e-8:
            return mid_c

        if f_low * f_mid <= 0:
            high_c = mid_c
            f_high = f_mid
        else:
            low_c = mid_c
            f_low = f_mid

    return (low_c + high_c) / 2.0


def steady_state_report_from_current(
    model: Model738,
    current_a: float,
    low_c: float = -50.0,
    high_c: float = 300.0,
) -> SteadyStateResult:
    """
    Given current, solve temperature and return full steady-state report.
    """
    ts_c = solve_steady_state_temperature(
        model=model,
        current_a=current_a,
        low_c=low_c,
        high_c=high_c,
    )

    terms = model.heat_terms(
        ts_c=ts_c,
        tavg_c=ts_c,
        current_a=current_a,
    )

    return SteadyStateResult(
        surface_temp_c=ts_c,
        avg_temp_c=ts_c,
        current_a=current_a,

        q_c_w_per_m=terms["q_c_W_per_m"],
        q_r_w_per_m=terms["q_r_W_per_m"],
        q_s_w_per_m=terms["q_s_W_per_m"],
        q_joule_w_per_m=terms["q_joule_W_per_m"],

        heating_w_per_m=terms["heating_W_per_m"],
        cooling_w_per_m=terms["cooling_W_per_m"],
        net_heat_w_per_m=terms["net_heat_W_per_m"],

        resistance_ohm_per_km=terms["R_ohm_per_km"],
    )