from typing import Literal

AtmosphereType = Literal["Clear", "Industrial"]

SOLAR_COEFFICIENTS_SI = {
    "Clear": {
        "A": -42.2391,
        "B": 63.8044,
        "C": -1.9220,
        "D": 3.46921e-2,
        "E": -3.61118e-4,
        "F": 1.94318e-6,
        "G": -4.07608e-9,
    },
    "Industrial": {
        "A": 53.1821,
        "B": 14.2110,
        "C": 6.6138e-1,
        "D": -3.1658e-2,
        "E": 5.4654e-4,
        "F": -4.3446e-6,
        "G": 1.3236e-8,
    },
}