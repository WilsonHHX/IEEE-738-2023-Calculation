from dataclasses import dataclass

from .model import Model738
from .radial import radial_temperatures_from_avg


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
    initial_current_a: float | None = None,
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

    if use_radial_gradient:
        tavg_c = initial_temp_c
        state_current_a = current_a if initial_current_a is None else initial_current_a
        radial = radial_temperatures_from_avg(
            model=model,
            current_a=state_current_a,
            avg_temp_c=tavg_c,
            kth_w_per_m_c=kth_w_per_m_c,
        )
        ts_c = radial.surface_temp_c
        core_temp_c = radial.core_temp_c
    else:
        ts_c = initial_temp_c
        tavg_c = ts_c
        core_temp_c = None

    states.append(
        ThermalState(
            time_s=time_s,
            surface_temp_c=ts_c,
            avg_temp_c=tavg_c,
            core_temp_c=core_temp_c,
            net_heat_w_per_m=0.0,
            delta_temp_c=0.0,
        )
    )

    while time_s < duration_s - 1e-12:
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

        if use_radial_gradient:
            tavg_c += delta_temp_c
            radial = radial_temperatures_from_avg(
                model=model,
                current_a=current_a,
                avg_temp_c=tavg_c,
                kth_w_per_m_c=kth_w_per_m_c,
            )
            ts_c = radial.surface_temp_c
            core_temp_c = radial.core_temp_c
        else:
            ts_c += delta_temp_c
            tavg_c = ts_c
            core_temp_c = None

        time_s += dt_s

        states.append(
            ThermalState(
                time_s=time_s,
                surface_temp_c=ts_c,
                avg_temp_c=tavg_c,
                core_temp_c=core_temp_c,
                net_heat_w_per_m=terms["net_heat_W_per_m"],
                delta_temp_c=delta_temp_c,
            )
        )

    return states
