"""thirdtrail — elevation-corrected sun, moon, solar and tide data.

    from thirdtrail import Client

    tt = Client(api_key="tt_live_…")
    for day in tt.ephemerides(lat=53.3498, lon=-6.2603, elevation=20):
        print(day.date, day.sun.rise)

Keys are minted at https://thirdtrail.life/apis/keys/.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .client import Client
from .errors import (
    AuthenticationError,
    DataUnavailable,
    InvalidRequest,
    PermissionDenied,
    PlanLimitExceeded,
    RateLimited,
    ServerError,
    ThirdtrailError,
)
from .models import Day, GoldenBlueHour, Moon, MoonPhase, SolarSample, Sun, TideExtreme

__all__ = [
    "AuthenticationError",
    "Client",
    "DataUnavailable",
    "Day",
    "GoldenBlueHour",
    "InvalidRequest",
    "Moon",
    "MoonPhase",
    "PermissionDenied",
    "PlanLimitExceeded",
    "RateLimited",
    "ServerError",
    "SolarSample",
    "Sun",
    "ThirdtrailError",
    "TideExtreme",
    "__version__",
]
