from dataclasses import dataclass
from math import log, pi

from .model import Model738


@dataclass
class RadialGradientResult:
    surface_temp_c: float
    core_temp_c: float
    avg_temp_c: float
    delta_core_surface_c: float
    resistance_ohm_per_km: float
    iterations: int


def radial_temperatures_from_avg(
    model: Model738,
    current_a: float,
    avg_temp_c: float,
    kth_w_per_m_c: float = 1.0,
) -> RadialGradientResult:
    """
    Resolve Ts and Tcore from a known Tavg using IEEE Std 738-2023
    Annex C Equation C.3.
    """
    delta_c = radial_delta_acsr(
        model=model,
        current_a=current_a,
        avg_temp_c=avg_temp_c,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    surface_temp_c = avg_temp_c - delta_c / 2.0
    core_temp_c = avg_temp_c + delta_c / 2.0

    return RadialGradientResult(
        surface_temp_c=surface_temp_c,
        core_temp_c=core_temp_c,
        avg_temp_c=avg_temp_c,
        delta_core_surface_c=delta_c,
        resistance_ohm_per_km=model.c.resistance_ohm_per_km(avg_temp_c),
        iterations=1,
    )


def radial_delta_acsr(
    model: Model738,
    current_a: float,
    avg_temp_c: float,
    kth_w_per_m_c: float = 1.0,
) -> float:
    """
    Radial temperature difference for a round conductor.

    IEEE Std 738-2023 Annex C:
        - Equation C.1 is used when a core diameter is provided.
        - Equation C.2 is used for all-aluminum / homogeneous conductors
          where d_core = 0.
        - Equation C.3 defines Tavg = (Tcore + Ts) / 2 in the iteration.

    Returns:
        Tcore - Ts, degC
    """
    if kth_w_per_m_c <= 0:
        raise ValueError("kth_w_per_m_c must be positive.")

    d0 = model.c.d_0
    dcore = model.c.d_core

    if dcore == 0:
        bracket = 0.5
    else:
        bracket = (
            0.5
            - (dcore**2 / (d0**2 - dcore**2)) * log(d0 / dcore)
        )

    return (
        current_a**2
        * model.c.resistance_ohm_per_m(avg_temp_c)
        / (2.0 * pi * kth_w_per_m_c)
        * bracket
    )


def solve_radial_gradient(
    model: Model738,
    surface_temp_c: float,
    current_a: float,
    kth_w_per_m_c: float = 1.0,
    tolerance_c: float = 1e-6,
    max_iter: int = 50,
) -> RadialGradientResult:
    """
    Iteratively solve:
        Ts -> Tcore -> Tavg

    Workflow:
        1. Start Tavg = Ts
        2. Calculate R(Tavg)
        3. Calculate Tcore - Ts
        4. Tcore = Ts + delta
        5. Tavg_new = (Ts + Tcore) / 2
        6. Repeat until convergence
    """
    avg_temp_c = surface_temp_c
    delta_c = 0.0

    for iteration in range(1, max_iter + 1):
        delta_c = radial_delta_acsr(
            model=model,
            current_a=current_a,
            avg_temp_c=avg_temp_c,
            kth_w_per_m_c=kth_w_per_m_c,
        )

        core_temp_c = surface_temp_c + delta_c
        new_avg_temp_c = (surface_temp_c + core_temp_c) / 2.0

        if abs(new_avg_temp_c - avg_temp_c) <= tolerance_c:
            return RadialGradientResult(
                surface_temp_c=surface_temp_c,
                core_temp_c=core_temp_c,
                avg_temp_c=new_avg_temp_c,
                delta_core_surface_c=delta_c,
                resistance_ohm_per_km=model.c.resistance_ohm_per_km(new_avg_temp_c),
                iterations=iteration,
            )

        avg_temp_c = new_avg_temp_c

    core_temp_c = surface_temp_c + delta_c

    return RadialGradientResult(
        surface_temp_c=surface_temp_c,
        core_temp_c=core_temp_c,
        avg_temp_c=avg_temp_c,
        delta_core_surface_c=delta_c,
        resistance_ohm_per_km=model.c.resistance_ohm_per_km(avg_temp_c),
        iterations=max_iter,
    )
