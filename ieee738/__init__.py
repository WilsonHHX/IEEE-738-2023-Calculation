from .inputs import Conductor, WeatherCondition
from .model import Model738

from .steady import (
    SteadyStateResult,
    steady_state_ampacity,
    steady_state_report_from_temperature,
    steady_state_residual,
    solve_steady_state_temperature,
    steady_state_report_from_current,
)

from .radial import (
    RadialGradientResult,
    solve_radial_gradient,
)

from .transient import (
    ThermalState,
    transient_temperature_curve,
)

from .time_constant import (
    TimeConstantResult,
    TimeConstantPoint,
    calculate_time_constant,
    time_constant_temperature,
    time_constant_curve,
    tau_marker_points,
)

from .csv_input import (
    CsvInput,
    CalculationConfig,
    read_input_csv,
    build_config_from_csv,
)
