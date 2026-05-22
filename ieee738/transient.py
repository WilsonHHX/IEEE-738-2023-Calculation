from dataclasses import dataclass

from .model import Model738
from .radial import solve_radial_gradient


@dataclass
class ThermalState:
    time_s: float
    surface_temp_c: float
    avg_temp_c: float
    core_temp_c: float | None
    net_heat_w_per_m: float
    delta_temp_c: float


def transient_temperature_curve(
    model: Model738,
    initial_temp_c: float,
    current_a: float,
    duration_s: float,
    dt_s: float = 10.0,
    use_radial_gradient: bool = False,
    kth_w_per_m_c: float = 1.0,
) -> list[ThermalState]:
    """
    IEEE 738 non-steady-state heat balance:

        dT = net_heat * dt / mCp

    First version:
        Ts = Tavg

    Optional radial version:
        Ts controls qc and qr
        Tavg controls R(Tavg)
    """
    if dt_s <= 0:
        raise ValueError("dt_s must be positive.")

    states: list[ThermalState] = []

    time_s = 0.0
    ts_c = initial_temp_c

    states.append(
        ThermalState(
            time_s=time_s,
            surface_temp_c=ts_c,
            avg_temp_c=ts_c,
            core_temp_c=None,
            net_heat_w_per_m=0.0,
            delta_temp_c=0.0,
        )
    )

    while time_s < duration_s - 1e-12:
        tavg_c = ts_c
        core_temp_c = None

        if use_radial_gradient:
            radial = solve_radial_gradient(
                model=model,
                surface_temp_c=ts_c,
                current_a=current_a,
                kth_w_per_m_c=kth_w_per_m_c,
            )
            tavg_c = radial.avg_temp_c
            core_temp_c = radial.core_temp_c

        terms = model.heat_terms(
            ts_c=ts_c,
            tavg_c=tavg_c,
            current_a=current_a,
        )

        delta_temp_c = (
            terms["net_heat_W_per_m"]
            * dt_s
            / model.c.heat_capacity()
        )

        ts_c += delta_temp_c
        time_s += dt_s

        states.append(
            ThermalState(
                time_s=time_s,
                surface_temp_c=ts_c,
                avg_temp_c=ts_c,
                core_temp_c=core_temp_c,
                net_heat_w_per_m=terms["net_heat_W_per_m"],
                delta_temp_c=delta_temp_c,
            )
        )

    return states