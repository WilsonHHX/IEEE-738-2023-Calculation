from dataclasses import dataclass

from .constants import AtmosphereType, SOLAR_COEFFICIENTS_SI


@dataclass
class Conductor:
    """
    Input data for one conductor / line section.

    This implementation follows your Excel workbook convention:
        Rlow and Rhigh are entered in ohm/km.

    Internal Joule heat calculation converts resistance to ohm/m.
    """

    name: str

    # Geometry
    d_0: float       # Outside diameter, m
    d_core: float    # Core diameter, m

    # Line physical location
    lat_deg: float        # Latitude, deg, north positive
    z_l_deg: float        # Line azimuth, deg. N-S = 0, E-W = 90
    elevation_m: float    # Line elevation above sea level, m

    # Surface properties
    absorptivity: float   # alpha, solar absorptivity
    emissivity: float     # epsilon, radiation emissivity

    # Resistance-temperature data from Excel
    r_low_ohm_per_km: float
    t_low_c: float
    r_high_ohm_per_km: float
    t_high_c: float

    # Thermal capacity data, Drake/ACSR default from your Excel
    mass_steel_kg_per_m: float = 0.5126
    mass_aluminum_kg_per_m: float = 1.116

    cp_aluminum_j_per_kg_c: float = 955.0
    cp_steel_j_per_kg_c: float = 476.0

    def __post_init__(self):
        if self.d_0 <= 0:
            raise ValueError("d_0 must be positive.")

        if self.d_core < 0:
            raise ValueError("d_core cannot be negative.")

        if self.d_core >= self.d_0:
            raise ValueError("d_core must be smaller than d_0.")

        if not (0 < self.absorptivity <= 1):
            raise ValueError("absorptivity must be in the range 0 < absorptivity <= 1.")

        if not (0 < self.emissivity <= 1):
            raise ValueError("emissivity must be in the range 0 < emissivity <= 1.")

        if self.t_high_c == self.t_low_c:
            raise ValueError("t_high_c and t_low_c cannot be the same.")

        if self.mass_steel_kg_per_m < 0:
            raise ValueError("mass_steel_kg_per_m cannot be negative.")

        if self.mass_aluminum_kg_per_m < 0:
            raise ValueError("mass_aluminum_kg_per_m cannot be negative.")

        if self.heat_capacity() <= 0:
            raise ValueError(
                "Conductor heat capacity must be positive. Provide at least one "
                "positive mass value for transient calculations."
            )

    def resistance_ohm_per_km(self, temp_c: float) -> float:
        """
        Linear interpolation of conductor AC resistance.

        Excel convention:
            R is shown in ohm/km.

        Formula:
            R(T) = Rlow + slope * (T - Tlow)
        """
        slope = (
            (self.r_high_ohm_per_km - self.r_low_ohm_per_km)
            / (self.t_high_c - self.t_low_c)
        )

        return self.r_low_ohm_per_km + slope * (temp_c - self.t_low_c)

    def resistance_ohm_per_m(self, temp_c: float) -> float:
        """
        Convert interpolated resistance from ohm/km to ohm/m.

        Joule heating uses:
            I^2 * R

        Since heat terms are W/m, resistance must be ohm/m.
        """
        return self.resistance_ohm_per_km(temp_c) / 1000.0

    def heat_capacity(self) -> float:
        """
        Total conductor heat capacity per unit length.

        Formula:
            mCp = sum(mi * Cpi)

        Unit:
            J / (m * degC)
        """
        return (
            self.mass_aluminum_kg_per_m * self.cp_aluminum_j_per_kg_c
            + self.mass_steel_kg_per_m * self.cp_steel_j_per_kg_c
        )


@dataclass
class WeatherCondition:
    """
    Weather and solar input data.

    This follows your Excel workbook input section.
    """

    t_a_c: float             # Ambient air temperature, degC
    v_w_mps: float           # Wind speed, m/s
    wind_angle_deg: float    # Angle from conductor axis, 90 = perpendicular

    solar_time_hour: float   # Solar time hour, e.g. 11 = 11 a.m.
    day_of_year: int         # Day of year, e.g. 161

    atmosphere: AtmosphereType = "Clear"

    def __post_init__(self):
        if self.v_w_mps < 0:
            raise ValueError("v_w_mps cannot be negative.")

        if not (0 <= self.wind_angle_deg <= 90):
            raise ValueError("wind_angle_deg must be between 0 and 90 degrees.")

        if not (1 <= self.day_of_year <= 366):
            raise ValueError("day_of_year must be between 1 and 366.")

        if self.atmosphere not in SOLAR_COEFFICIENTS_SI:
            raise ValueError(
                f"Invalid atmosphere: {self.atmosphere}. "
                f"Must be one of {list(SOLAR_COEFFICIENTS_SI.keys())}."
            )

    def solar_coefficients(self) -> dict[str, float]:
        """
        Return solar polynomial coefficients based on atmosphere type.
        """
        return SOLAR_COEFFICIENTS_SI[self.atmosphere]
