from math import sin, cos, tan, asin, acos, atan, radians, degrees

from .inputs import Conductor, WeatherCondition


class Model738:
    """
    Core IEEE 738 heat model.

    This class calculates:
        qs = solar heat gain, W/m
        qr = radiation heat loss, W/m
        qc = convection heat loss, W/m

    It also outputs intermediate workflow values to match your Excel table.
    """

    def __init__(self, conductor: Conductor, weather: WeatherCondition):
        self.c = conductor
        self.w = weather

    # ------------------------------------------------------------
    # Degree-based trig functions
    # ------------------------------------------------------------

    @staticmethod
    def sind(x_deg: float) -> float:
        return sin(radians(x_deg))

    @staticmethod
    def cosd(x_deg: float) -> float:
        return cos(radians(x_deg))

    @staticmethod
    def tand(x_deg: float) -> float:
        return tan(radians(x_deg))

    @staticmethod
    def asind(x: float) -> float:
        x = max(-1.0, min(1.0, x))
        return degrees(asin(x))

    @staticmethod
    def acosd(x: float) -> float:
        x = max(-1.0, min(1.0, x))
        return degrees(acos(x))

    @staticmethod
    def atand(x: float) -> float:
        return degrees(atan(x))

    # ------------------------------------------------------------
    # Solar geometry workflow
    # ------------------------------------------------------------

    def omega(self) -> float:
        """
        Hour angle:
            omega = (solar_time - 12) * 15
        """
        return (self.w.solar_time_hour - 12.0) * 15.0

    def delta(self) -> float:
        """
        Solar declination.

        Your Excel uses:
            delta = 23.45 * sin(((284.25 + N) / 365) * 360)
        """
        return 23.45 * self.sind(
            ((284.25 + self.w.day_of_year) / 365.0) * 360.0
        )

    def hc_raw(self) -> float:
        """
        Raw solar altitude before nighttime floor.
        """
        lat = self.c.lat_deg
        delta = self.delta()
        omega = self.omega()

        value = (
            self.cosd(lat) * self.cosd(delta) * self.cosd(omega)
            + self.sind(lat) * self.sind(delta)
        )

        return self.asind(value)

    def hc(self) -> float:
        """
        Solar altitude limited to non-negative.
        """
        return max(0.0, self.hc_raw())

    def chi(self) -> float:
        """
        Solar azimuth variable.
        """
        lat = self.c.lat_deg
        delta = self.delta()
        omega = self.omega()

        denominator = (
            self.sind(lat) * self.cosd(omega)
            - self.cosd(lat) * self.tand(delta)
        )

        if abs(denominator) < 1e-12:
            raise ZeroDivisionError("Solar azimuth denominator is too close to zero.")

        return self.sind(omega) / denominator

    def c_azimuth(self) -> float:
        """
        Solar azimuth quadrant correction constant.
        """
        omega = self.omega()
        chi = self.chi()

        if -180.0 <= omega < 0.0:
            return 0.0 if chi >= 0.0 else 180.0

        if 0.0 <= omega < 180.0:
            return 180.0 if chi >= 0.0 else 360.0

        raise ValueError("Hour angle omega is outside the expected range [-180, 180).")

    def zc(self) -> float:
        """
        Solar azimuth:
            Zc = C + atan(chi)
        """
        return self.c_azimuth() + self.atand(self.chi())

    def theta(self) -> float:
        """
        Effective angle of incidence:
            theta = acos[cos(Hc) * cos(Zc - Zl)]
        """
        return self.acosd(
            self.cosd(self.hc()) * self.cosd(self.zc() - self.c.z_l_deg)
        )

    # ------------------------------------------------------------
    # Solar heat gain
    # ------------------------------------------------------------

    def qs_sea(self) -> float:
        """
        Solar heat intensity at sea level, Qs.

        Qs = A + B*Hc + C*Hc^2 + ... + G*Hc^6
        """
        h = self.hc()

        if h <= 0:
            return 0.0

        coeffs = self.w.solar_coefficients()

        return (
            coeffs["A"]
            + coeffs["B"] * h
            + coeffs["C"] * h**2
            + coeffs["D"] * h**3
            + coeffs["E"] * h**4
            + coeffs["F"] * h**5
            + coeffs["G"] * h**6
        )

    def k_solar(self) -> float:
        """
        Solar elevation correction factor.
        """
        he = self.c.elevation_m
        return 1.0 + 1.148e-4 * he - 1.108e-8 * he**2

    def qse(self) -> float:
        """
        Solar heat intensity corrected for elevation.
        """
        return self.k_solar() * self.qs_sea()

    def a_prime(self) -> float:
        """
        Projected area per unit length.

        For round bare conductor:
            A' = D0
        """
        return self.c.d_0

    def qs(self) -> float:
        """
        Solar heat gain:
            qs = alpha * Qse * sin(theta) * A'
        """
        return (
            self.c.absorptivity
            * self.qse()
            * self.sind(self.theta())
            * self.a_prime()
        )

    # ------------------------------------------------------------
    # Radiation heat loss
    # ------------------------------------------------------------

    def qr(self, ts_c: float) -> float:
        """
        Radiated heat loss:
            qr = 17.8 * D0 * epsilon *
                 [((Ts+273)/100)^4 - ((Ta+273)/100)^4]
        """
        return 17.8 * self.c.d_0 * self.c.emissivity * (
            ((ts_c + 273.0) / 100.0) ** 4
            - ((self.w.t_a_c + 273.0) / 100.0) ** 4
        )

    # ------------------------------------------------------------
    # Convection heat loss
    # ------------------------------------------------------------

    def tfilm(self, ts_c: float) -> float:
        return (ts_c + self.w.t_a_c) / 2.0

    def mu_f(self, ts_c: float) -> float:
        """
        Dynamic viscosity of air.
        """
        t = self.tfilm(ts_c)
        return 1.458e-6 * (t + 273.0) ** 1.5 / (t + 383.4)

    def rho_f(self, ts_c: float) -> float:
        """
        Air density.
        """
        t = self.tfilm(ts_c)
        he = self.c.elevation_m

        return (
            1.293
            - 1.525e-4 * he
            + 6.379e-9 * he**2
        ) / (1.0 + 0.00367 * t)

    def k_f(self, ts_c: float) -> float:
        """
        Thermal conductivity of air.
        """
        t = self.tfilm(ts_c)
        return 2.424e-2 + 7.477e-5 * t - 4.407e-9 * t**2

    def n_re(self, ts_c: float) -> float:
        """
        Reynolds number.
        """
        return self.c.d_0 * self.rho_f(ts_c) * self.w.v_w_mps / self.mu_f(ts_c)

    def k_angle(self) -> float:
        """
        Wind direction factor.
        """
        phi = self.w.wind_angle_deg

        return (
            1.194
            - self.cosd(phi)
            + 0.194 * self.cosd(2.0 * phi)
            + 0.368 * self.sind(2.0 * phi)
        )

    def qcn(self, ts_c: float) -> float:
        """
        Natural convection heat loss.
        """
        delta_t = ts_c - self.w.t_a_c

        if delta_t <= 0:
            return 0.0

        return (
            3.645
            * self.rho_f(ts_c) ** 0.5
            * self.c.d_0 ** 0.75
            * delta_t ** 1.25
        )

    def qc1(self, ts_c: float) -> float:
        """
        Forced convection, low Reynolds estimate.
        """
        delta_t = ts_c - self.w.t_a_c

        if delta_t <= 0 or self.w.v_w_mps <= 0:
            return 0.0

        return (
            self.k_angle()
            * (1.01 + 1.35 * self.n_re(ts_c) ** 0.52)
            * self.k_f(ts_c)
            * delta_t
        )

    def qc2(self, ts_c: float) -> float:
        """
        Forced convection, high Reynolds estimate.
        """
        delta_t = ts_c - self.w.t_a_c

        if delta_t <= 0 or self.w.v_w_mps <= 0:
            return 0.0

        return (
            self.k_angle()
            * 0.754
            * self.n_re(ts_c) ** 0.6
            * self.k_f(ts_c)
            * delta_t
        )

    def qc(self, ts_c: float) -> float:
        """
        Selected convection heat loss:
            qc = max(qcn, qc1, qc2)
        """
        return max(self.qcn(ts_c), self.qc1(ts_c), self.qc2(ts_c))

    # ------------------------------------------------------------
    # Output dictionaries matching Excel workflow
    # ------------------------------------------------------------

    def terms(self, ts_c: float) -> dict[str, float]:
        """
        Return intermediate workflow values similar to your Excel table.
        """
        return {
            "omega_deg": self.omega(),
            "delta_deg": self.delta(),
            "Hc_raw_deg": self.hc_raw(),
            "Hc_deg": self.hc(),
            "chi": self.chi(),
            "C_deg": self.c_azimuth(),
            "Zc_deg": self.zc(),
            "theta_deg": self.theta(),
            "Q_s_W_per_m2": self.qs_sea(),
            "K_solar": self.k_solar(),
            "Q_se_W_per_m2": self.qse(),
            "A_prime_m2_per_m": self.a_prime(),
            "q_s_W_per_m": self.qs(),
            "q_r_W_per_m": self.qr(ts_c),
            "T_film_c": self.tfilm(ts_c),
            "mu_f_kg_per_m_s": self.mu_f(ts_c),
            "rho_f_kg_per_m3": self.rho_f(ts_c),
            "k_f_W_per_m_c": self.k_f(ts_c),
            "N_Re": self.n_re(ts_c),
            "K_angle": self.k_angle(),
            "q_cn_W_per_m": self.qcn(ts_c),
            "q_c1_W_per_m": self.qc1(ts_c),
            "q_c2_W_per_m": self.qc2(ts_c),
            "q_c_W_per_m": self.qc(ts_c),
        }

    def heat_terms(self, ts_c: float, tavg_c: float, current_a: float) -> dict[str, float]:
        """
        Main heat-balance terms.

        Heating:
            I^2 R(Tavg) + qs

        Cooling:
            qc + qr

        Net heat:
            heating - cooling
        """
        r_km = self.c.resistance_ohm_per_km(tavg_c)
        r_m = self.c.resistance_ohm_per_m(tavg_c)

        q_joule = current_a**2 * r_m
        q_solar = self.qs()
        q_radiation = self.qr(ts_c)
        q_convection = self.qc(ts_c)

        heating = q_joule + q_solar
        cooling = q_convection + q_radiation
        net_heat = heating - cooling

        return {
            "R_ohm_per_km": r_km,
            "R_ohm_per_m": r_m,
            "q_joule_W_per_m": q_joule,
            "q_s_W_per_m": q_solar,
            "q_r_W_per_m": q_radiation,
            "q_c_W_per_m": q_convection,
            "heating_W_per_m": heating,
            "cooling_W_per_m": cooling,
            "net_heat_W_per_m": net_heat,
        }