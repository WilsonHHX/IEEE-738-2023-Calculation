from pathlib import Path
import sys
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ieee738 import (
    Conductor,
    WeatherCondition,
    Model738,
    steady_state_report_from_temperature,
    steady_state_report_from_current,
    solve_radial_gradient,
    transient_temperature_curve,
    calculate_time_constant,
    time_constant_curve,
    tau_marker_points,
    build_config_from_csv,
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_MAX_SURFACE_TEMP_C = 100.0
DEFAULT_FINAL_STEP_CURRENT_A = 1200.0
DEFAULT_TRANSIENT_DURATION_S = 3600.0
DEFAULT_TRANSIENT_DT_S = 10.0
DEFAULT_KTH_W_PER_M_C = 1.0


def build_drake_model() -> Model738:
    # ------------------------------------------------------------
    # Data input from your Excel table
    # ------------------------------------------------------------
    drake = Conductor(
        name="Drake ACSR",

        d_0=0.02814,
        d_core=0.0104,

        lat_deg=30.0,
        z_l_deg=90.0,
        elevation_m=0.0,

        absorptivity=0.8,
        emissivity=0.8,

        r_low_ohm_per_km=0.07283,
        t_low_c=25.0,
        r_high_ohm_per_km=0.08688,
        t_high_c=75.0,

        mass_steel_kg_per_m=0.5126,
        mass_aluminum_kg_per_m=1.116,
    )

    weather = WeatherCondition(
        t_a_c=40.0,
        v_w_mps=0.61,
        wind_angle_deg=90.0,

        solar_time_hour=11.0,
        day_of_year=161,
        atmosphere="Clear",
    )

    return Model738(drake, weather)


def surface_temperature_points(
    model: Model738,
    max_surface_temp_c: float,
    point_count: int = 140,
) -> list[float]:
    start_temp_c = model.w.t_a_c
    step_c = (max_surface_temp_c - start_temp_c) / (point_count - 1)

    temperatures = []
    for index in range(point_count):
        ts_c = start_temp_c + step_c * index
        numerator = model.qc(ts_c) + model.qr(ts_c) - model.qs()
        if numerator > 0:
            temperatures.append(ts_c)

    if not temperatures:
        raise ValueError("No positive-current points found up to max_surface_temp_c.")

    return temperatures


def save_current_temperature_curve(
    model: Model738,
    max_surface_temp_c: float,
    kth_w_per_m_c: float = 1.0,
) -> Path:
    import matplotlib.pyplot as plt

    temperatures_c = surface_temperature_points(
        model=model,
        max_surface_temp_c=max_surface_temp_c,
    )

    current_radial_a = []
    core_temperatures_c = []

    for ts_c in temperatures_c:
        current_radial_a.append(
            steady_state_report_from_temperature(
                model=model,
                ts_c=ts_c,
                use_radial_gradient=True,
                kth_w_per_m_c=kth_w_per_m_c,
            ).current_a
        )
        radial = solve_radial_gradient(
            model=model,
            surface_temp_c=ts_c,
            current_a=current_radial_a[-1],
            kth_w_per_m_c=kth_w_per_m_c,
        )
        core_temperatures_c.append(radial.core_temp_c)

    max_radial_a = current_radial_a[-1]
    max_core_temp_c = core_temperatures_c[-1]

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "current_temperature_curve.png"

    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=150)
    ax.plot(
        current_radial_a,
        temperatures_c,
        label="Surface temperature",
        color="tab:red",
        linewidth=2.2,
    )
    ax.plot(
        current_radial_a,
        core_temperatures_c,
        label="Core/center temperature",
        color="tab:red",
        linestyle=":",
        linewidth=2.2,
    )
    ax.axhline(
        max_surface_temp_c,
        color="0.35",
        linestyle="--",
        linewidth=1.2,
    )
    ax.scatter(
        [max_radial_a],
        [max_surface_temp_c],
        s=52,
        zorder=3,
    )
    ax.scatter(
        [max_radial_a],
        [max_core_temp_c],
        s=52,
        zorder=3,
        color="tab:red",
    )
    ax.annotate(
        f"Surface: {max_radial_a:.1f} A @ {max_surface_temp_c:.1f} C",
        xy=(max_radial_a, max_surface_temp_c),
        xytext=(-120, -36),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "linewidth": 1.0},
    )
    ax.annotate(
        f"Core/center: {max_core_temp_c:.1f} C",
        xy=(max_radial_a, max_core_temp_c),
        xytext=(-120, 28),
        textcoords="offset points",
        arrowprops={"arrowstyle": "->", "linewidth": 1.0},
    )

    ax.set_title("Static Rating Current-Temperature Curve With Radial Gradient")
    ax.set_xlabel("Current, A")
    ax.set_ylabel("Conductor temperature, C")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return output_path


def save_transient_step_curve(
    model: Model738,
    initial_surface_temp_c: float,
    final_current_a: float,
    duration_s: float,
    dt_s: float = 10.0,
    kth_w_per_m_c: float = 1.0,
) -> Path:
    import matplotlib.pyplot as plt

    initial_state = steady_state_report_from_temperature(
        model=model,
        ts_c=initial_surface_temp_c,
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    final_state = steady_state_report_from_current(
        model=model,
        current_a=final_current_a,
        low_c=model.w.t_a_c,
        high_c=max(initial_surface_temp_c, model.w.t_a_c + 10.0),
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
    )

    curve = transient_temperature_curve(
        model=model,
        initial_temp_c=initial_state.avg_temp_c,
        current_a=final_current_a,
        duration_s=duration_s,
        dt_s=dt_s,
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
        initial_current_a=initial_state.current_a,
    )

    time_s = [state.time_s for state in curve]
    surface_temperature_c = [state.surface_temp_c for state in curve]
    core_temperature_c = [
        state.core_temp_c if state.core_temp_c is not None else state.surface_temp_c
        for state in curve
    ]
    final_radial = solve_radial_gradient(
        model=model,
        surface_temp_c=final_state.surface_temp_c,
        current_a=final_current_a,
        kth_w_per_m_c=kth_w_per_m_c,
    )

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "transient_step_curve.png"

    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=150)
    ax.plot(
        time_s,
        surface_temperature_c,
        label="Transient surface temperature",
        color="tab:red",
        linewidth=2.2,
    )
    ax.plot(
        time_s,
        core_temperature_c,
        label="Transient core/center temperature",
        color="tab:red",
        linestyle=":",
        linewidth=2.2,
    )
    ax.axhline(
        initial_state.surface_temp_c,
        color="0.35",
        linestyle="--",
        linewidth=1.2,
        label=f"Initial surface steady state: {initial_state.current_a:.1f} A",
    )
    ax.axhline(
        final_state.surface_temp_c,
        color="0.15",
        linestyle=":",
        linewidth=1.5,
        label=f"Final surface steady state: {final_current_a:.1f} A",
    )
    ax.axhline(
        final_radial.core_temp_c,
        color="0.25",
        linestyle="-.",
        linewidth=1.3,
        label=f"Final core/center steady state: {final_current_a:.1f} A",
    )

    ax.set_title(
        f"Transient Temperature After Current Step "
        f"({initial_state.current_a:.1f} A to {final_current_a:.1f} A)"
    )
    ax.set_xlabel("Time, s")
    ax.set_ylabel("Conductor temperature, C")
    ax.grid(True, alpha=0.3)

    ax_current = ax.twinx()
    current_step_a = [initial_state.current_a] + [final_current_a] * (len(time_s) - 1)
    ax_current.step(
        time_s,
        current_step_a,
        where="post",
        color="tab:red",
        linewidth=1.8,
        label="Current step",
    )
    ax_current.set_ylabel("Current, A")

    temp_low_c, temp_high_c = ax.get_ylim()
    initial_temp_fraction = (
        (initial_state.surface_temp_c - temp_low_c) / (temp_high_c - temp_low_c)
    )
    current_delta_a = final_current_a - initial_state.current_a
    current_padding_a = max(abs(current_delta_a) * 0.15, 1.0)

    if abs(current_delta_a) < 1e-12:
        current_low_a = initial_state.current_a - current_padding_a
        current_high_a = initial_state.current_a + current_padding_a
    elif current_delta_a > 0:
        current_high_a = final_current_a + current_padding_a
        current_low_a = (
            initial_state.current_a - initial_temp_fraction * current_high_a
        ) / (1.0 - initial_temp_fraction)
    else:
        current_low_a = final_current_a - current_padding_a
        current_high_a = (
            initial_state.current_a
            - (1.0 - initial_temp_fraction) * current_low_a
        ) / initial_temp_fraction

    ax_current.set_ylim(current_low_a, current_high_a)

    temperature_lines, temperature_labels = ax.get_legend_handles_labels()
    current_lines, current_labels = ax_current.get_legend_handles_labels()
    ax.legend(
        temperature_lines + current_lines,
        temperature_labels + current_labels,
        loc="best",
    )
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return output_path


def save_time_constant_curve(
    model: Model738,
    initial_surface_temp_c: float,
    final_current_a: float,
    duration_s: float | None = None,
    dt_s: float = 10.0,
    kth_w_per_m_c: float = 1.0,
):
    import matplotlib.pyplot as plt

    initial_state = steady_state_report_from_temperature(
        model=model,
        ts_c=initial_surface_temp_c,
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    final_state = steady_state_report_from_current(
        model=model,
        current_a=final_current_a,
        low_c=model.w.t_a_c,
        high_c=max(initial_surface_temp_c, model.w.t_a_c + 10.0),
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    time_constant = calculate_time_constant(
        model=model,
        initial_current_a=initial_state.current_a,
        final_current_a=final_current_a,
        initial_temp_c=initial_state.surface_temp_c,
        final_temp_c=final_state.surface_temp_c,
    )

    if duration_s is None:
        duration_s = 3.5 * time_constant.tau_s

    curve = time_constant_curve(
        result=time_constant,
        duration_s=duration_s,
        dt_s=dt_s,
    )
    markers = tau_marker_points(time_constant, max_multiple=3)

    time_min = [point.time_min for point in curve]
    temperature_c = [point.temperature_c for point in curve]

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "time_constant_curve.png"

    fig, ax = plt.subplots(figsize=(8.5, 5.2), dpi=150)
    ax.plot(
        time_min,
        temperature_c,
        label="Annex D exponential approximation",
        linewidth=2.2,
    )
    ax.axhline(
        time_constant.final_temp_c,
        color="0.25",
        linestyle=":",
        linewidth=1.3,
        label=f"Final steady state: {time_constant.final_temp_c:.1f} C",
    )

    for marker in markers:
        ax.axvline(
            marker.time_min,
            color="0.55",
            linestyle="--",
            linewidth=1.0,
        )
        ax.scatter(
            [marker.time_min],
            [marker.temperature_c],
            s=52,
            zorder=3,
        )
        ax.annotate(
            f"{marker.tau_multiple:.0f} tau\n"
            f"{marker.time_min:.2f} min, {marker.temperature_c:.2f} C",
            xy=(marker.time_min, marker.temperature_c),
            xytext=(10, -26),
            textcoords="offset points",
            arrowprops={"arrowstyle": "->", "linewidth": 0.9},
        )

    ax.set_title(
        f"Thermal Time Constant Approximation "
        f"(tau = {time_constant.tau_min:.2f} min)"
    )
    ax.set_xlabel("Time, min")
    ax.set_ylabel("Conductor surface temperature, C")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)

    return output_path, time_constant, markers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run IEEE 738 Drake example calculations and save figures."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        help="Optional 4-column CSV: name, variable_name, value, unit.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.input_csv:
        config = build_config_from_csv(args.input_csv)
        model738 = config.model
        max_surface_temp_c = config.max_surface_temp_c
        final_step_current_a = config.final_step_current_a
        transient_duration_s = config.transient_duration_s
        transient_dt_s = config.transient_dt_s
        kth_w_per_m_c = config.kth_w_per_m_c
        print(f"=== Loaded input CSV: {args.input_csv} ===")
    else:
        model738 = build_drake_model()
        max_surface_temp_c = DEFAULT_MAX_SURFACE_TEMP_C
        final_step_current_a = DEFAULT_FINAL_STEP_CURRENT_A
        transient_duration_s = DEFAULT_TRANSIENT_DURATION_S
        transient_dt_s = DEFAULT_TRANSIENT_DT_S
        kth_w_per_m_c = DEFAULT_KTH_W_PER_M_C

    drake = model738.c

    # ------------------------------------------------------------
    # Match Excel workflow table
    # ------------------------------------------------------------
    print(f"=== Calculation workflow values at Ts = {max_surface_temp_c:g} C ===")
    workflow = model738.terms(ts_c=max_surface_temp_c)

    for key, value in workflow.items():
        print(f"{key:25s}: {value:.10f}")

    # ------------------------------------------------------------
    # Steady-state ampacity with radial gradient
    # ------------------------------------------------------------
    print("\n=== Steady-state ampacity with radial thermal gradient ===")
    result_radial = steady_state_report_from_temperature(
        model=model738,
        ts_c=max_surface_temp_c,
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    radial = solve_radial_gradient(
        model=model738,
        surface_temp_c=max_surface_temp_c,
        current_a=result_radial.current_a,
        kth_w_per_m_c=kth_w_per_m_c,
    )

    print(f"Ts            = {result_radial.surface_temp_c:.10f} C")
    print(f"Tcore         = {radial.core_temp_c:.10f} C")
    print(f"Tavg          = {result_radial.avg_temp_c:.10f} C")
    print(f"Tcore - Ts    = {radial.delta_core_surface_c:.10f} C")
    print(f"R(Tavg)       = {result_radial.resistance_ohm_per_km:.10f} ohm/km")
    print(f"qc + qr - qs  = {result_radial.cooling_w_per_m - result_radial.q_s_w_per_m:.10f} W/m")
    print(f"I             = {result_radial.current_a:.10f} A")
    print(f"qc            = {result_radial.q_c_w_per_m:.10f} W/m")
    print(f"qr            = {result_radial.q_r_w_per_m:.10f} W/m")
    print(f"qs            = {result_radial.q_s_w_per_m:.10f} W/m")
    print(f"qj            = {result_radial.q_joule_w_per_m:.10f} W/m")
    print(f"net heat      = {result_radial.net_heat_w_per_m:.12f} W/m")
    print(f"iterations    = {radial.iterations}")

    # ------------------------------------------------------------
    # Given current, solve steady-state temperature
    # ------------------------------------------------------------
    print(
        f"\n=== Steady-state temperature from given current, "
        f"I = {final_step_current_a:g} A ==="
    )
    result_current = steady_state_report_from_current(
        model=model738,
        current_a=final_step_current_a,
        low_c=model738.w.t_a_c,
        high_c=max(max_surface_temp_c, model738.w.t_a_c + 10.0),
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    radial_current = solve_radial_gradient(
        model=model738,
        surface_temp_c=result_current.surface_temp_c,
        current_a=final_step_current_a,
        kth_w_per_m_c=kth_w_per_m_c,
    )

    print(f"I             = {result_current.current_a:.10f} A")
    print(f"Ts            = {result_current.surface_temp_c:.10f} C")
    print(f"Tcore         = {radial_current.core_temp_c:.10f} C")
    print(f"Tavg          = {result_current.avg_temp_c:.10f} C")
    print(f"Tcore - Ts    = {radial_current.delta_core_surface_c:.10f} C")
    print(f"R(Tavg)       = {result_current.resistance_ohm_per_km:.10f} ohm/km")
    print(f"qc            = {result_current.q_c_w_per_m:.10f} W/m")
    print(f"qr            = {result_current.q_r_w_per_m:.10f} W/m")
    print(f"qs            = {result_current.q_s_w_per_m:.10f} W/m")
    print(f"qj            = {result_current.q_joule_w_per_m:.10f} W/m")
    print(f"net heat      = {result_current.net_heat_w_per_m:.12f} W/m")

    # ------------------------------------------------------------
    # Transient calculation, same as Excel first 10 s logic
    # ------------------------------------------------------------
    print(f"\n=== Transient calculation, If = {final_step_current_a:g} A ===")
    print(f"mCp           = {drake.heat_capacity():.10f} J/(m*C)")

    curve = transient_temperature_curve(
        model=model738,
        initial_temp_c=result_radial.avg_temp_c,
        current_a=final_step_current_a,
        duration_s=60.0,
        dt_s=10.0,
        use_radial_gradient=True,
        kth_w_per_m_c=kth_w_per_m_c,
        initial_current_a=result_radial.current_a,
    )

    for state in curve:
        core_temp_text = (
            f"{state.core_temp_c:10.6f}"
            if state.core_temp_c is not None
            else "      n/a "
        )
        print(
            f"t = {state.time_s:6.1f} s, "
            f"Ts = {state.surface_temp_c:10.6f} C, "
            f"Tcore = {core_temp_text} C, "
            f"dTavg = {state.delta_temp_c:10.6f} C, "
            f"net_heat = {state.net_heat_w_per_m:12.6f} W/m"
        )

    # ------------------------------------------------------------
    # Figure output
    # ------------------------------------------------------------
    current_temperature_path = save_current_temperature_curve(
        model=model738,
        max_surface_temp_c=max_surface_temp_c,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    transient_path = save_transient_step_curve(
        model=model738,
        initial_surface_temp_c=max_surface_temp_c,
        final_current_a=final_step_current_a,
        duration_s=transient_duration_s,
        dt_s=transient_dt_s,
        kth_w_per_m_c=kth_w_per_m_c,
    )
    time_constant_path, time_constant, tau_markers = save_time_constant_curve(
        model=model738,
        initial_surface_temp_c=max_surface_temp_c,
        final_current_a=final_step_current_a,
        dt_s=transient_dt_s,
        kth_w_per_m_c=kth_w_per_m_c,
    )

    print("\n=== Figure output ===")
    print(f"Current-temperature curve: {current_temperature_path}")
    print(f"Transient step curve     : {transient_path}")
    print(f"Time constant curve      : {time_constant_path}")

    print("\n=== Annex D time constant approximation ===")
    print(f"tau           = {time_constant.tau_s:.3f} s = {time_constant.tau_min:.3f} min")
    print(f"Initial state = {time_constant.initial_current_a:.3f} A, {time_constant.initial_temp_c:.3f} C")
    print(f"Final state   = {time_constant.final_current_a:.3f} A, {time_constant.final_temp_c:.3f} C")
    print(f"R(Tavg)       = {time_constant.resistance_ohm_per_m:.10f} ohm/m")
    print("Tau markers:")
    for marker in tau_markers:
        print(
            f"{marker.tau_multiple:.0f} tau: "
            f"t = {marker.time_s:.3f} s ({marker.time_min:.3f} min), "
            f"T = {marker.temperature_c:.3f} C"
        )


if __name__ == "__main__":
    main()
