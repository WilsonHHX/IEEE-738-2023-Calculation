from dataclasses import dataclass
import csv
from pathlib import Path

from .inputs import Conductor, WeatherCondition
from .model import Model738


ATMOSPHERE_CODES = {
    0: "Clear",
    1: "Industrial",
}


REQUIRED_VARIABLES = {
    "d_0",
    "d_core",
    "lat_deg",
    "z_l_deg",
    "elevation_m",
    "absorptivity",
    "emissivity",
    "r_low_ohm_per_km",
    "t_low_c",
    "r_high_ohm_per_km",
    "t_high_c",
    "mass_steel_kg_per_m",
    "mass_aluminum_kg_per_m",
    "t_a_c",
    "v_w_mps",
    "wind_angle_deg",
    "solar_time_hour",
    "day_of_year",
    "atmosphere_code",
    "max_surface_temp_c",
    "final_step_current_a",
    "transient_duration_s",
    "transient_dt_s",
    "kth_w_per_m_c",
}


OPTIONAL_BLANK_DEFAULTS = {
    "d_core": 0.0,
    "mass_steel_kg_per_m": 0.0,
    "mass_aluminum_kg_per_m": Conductor.__dataclass_fields__[
        "mass_aluminum_kg_per_m"
    ].default,
}


@dataclass
class CsvInput:
    values: dict[str, float]
    labels: dict[str, str]
    units: dict[str, str]


@dataclass
class CalculationConfig:
    model: Model738
    max_surface_temp_c: float
    final_step_current_a: float
    transient_duration_s: float
    transient_dt_s: float
    kth_w_per_m_c: float
    raw_input: CsvInput


def read_input_csv(path: str | Path) -> CsvInput:
    csv_path = Path(path)
    values: dict[str, float] = {}
    labels: dict[str, str] = {}
    units: dict[str, str] = {}

    with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        for row_number, row in enumerate(reader, start=1):
            if not row or all(not cell.strip() for cell in row):
                continue

            if row_number == 1 and row[0].strip().lower() in {"name", "名字"}:
                continue

            if len(row) != 4:
                raise ValueError(
                    f"CSV row {row_number} must have exactly 4 columns: "
                    "name, variable_name, value, unit."
                )

            name, variable_name, raw_value, unit = [cell.strip() for cell in row]

            if not variable_name:
                raise ValueError(f"CSV row {row_number} has an empty variable name.")

            if variable_name in values:
                raise ValueError(f"Duplicate variable in CSV: {variable_name}")

            if raw_value == "":
                if variable_name not in OPTIONAL_BLANK_DEFAULTS:
                    raise ValueError(
                        f"CSV row {row_number} value for {variable_name} is blank. "
                        "Only d_core, mass_steel_kg_per_m, and "
                        "mass_aluminum_kg_per_m may be blank."
                    )
                value = OPTIONAL_BLANK_DEFAULTS[variable_name]
            else:
                try:
                    value = float(raw_value)
                except ValueError as exc:
                    raise ValueError(
                        f"CSV row {row_number} value for {variable_name} must be numeric."
                    ) from exc

            labels[variable_name] = name
            values[variable_name] = value
            units[variable_name] = unit

    missing = sorted((REQUIRED_VARIABLES - set(values)) - set(OPTIONAL_BLANK_DEFAULTS))
    if missing:
        raise ValueError("CSV input is missing required variables: " + ", ".join(missing))

    for variable_name, default_value in OPTIONAL_BLANK_DEFAULTS.items():
        values.setdefault(variable_name, default_value)

    unknown = sorted(set(values) - REQUIRED_VARIABLES)
    if unknown:
        raise ValueError("CSV input has unknown variables: " + ", ".join(unknown))

    return CsvInput(values=values, labels=labels, units=units)


def build_config_from_csv(path: str | Path) -> CalculationConfig:
    raw_input = read_input_csv(path)
    values = raw_input.values

    atmosphere_code = int(values["atmosphere_code"])
    if atmosphere_code != values["atmosphere_code"]:
        raise ValueError("atmosphere_code must be an integer: 0 = Clear, 1 = Industrial.")

    if atmosphere_code not in ATMOSPHERE_CODES:
        raise ValueError("atmosphere_code must be 0 for Clear or 1 for Industrial.")

    conductor = Conductor(
        name="CSV Conductor",
        d_0=values["d_0"],
        d_core=values["d_core"],
        lat_deg=values["lat_deg"],
        z_l_deg=values["z_l_deg"],
        elevation_m=values["elevation_m"],
        absorptivity=values["absorptivity"],
        emissivity=values["emissivity"],
        r_low_ohm_per_km=values["r_low_ohm_per_km"],
        t_low_c=values["t_low_c"],
        r_high_ohm_per_km=values["r_high_ohm_per_km"],
        t_high_c=values["t_high_c"],
        mass_steel_kg_per_m=values["mass_steel_kg_per_m"],
        mass_aluminum_kg_per_m=values["mass_aluminum_kg_per_m"],
    )
    weather = WeatherCondition(
        t_a_c=values["t_a_c"],
        v_w_mps=values["v_w_mps"],
        wind_angle_deg=values["wind_angle_deg"],
        solar_time_hour=values["solar_time_hour"],
        day_of_year=int(values["day_of_year"]),
        atmosphere=ATMOSPHERE_CODES[atmosphere_code],
    )

    return CalculationConfig(
        model=Model738(conductor, weather),
        max_surface_temp_c=values["max_surface_temp_c"],
        final_step_current_a=values["final_step_current_a"],
        transient_duration_s=values["transient_duration_s"],
        transient_dt_s=values["transient_dt_s"],
        kth_w_per_m_c=values["kth_w_per_m_c"],
        raw_input=raw_input,
    )
