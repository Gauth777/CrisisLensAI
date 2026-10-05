from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..schemas import EnvironmentalData, PilotLocation


@dataclass(frozen=True)
class LocationPoint:
    latitude: float
    longitude: float


# Representative coordinates for each pilot locality. These are used only to
# request gridded weather data; they are not exact incident coordinates.
PILOT_COORDINATES: dict[PilotLocation, LocationPoint] = {
    "Tambaram": LocationPoint(latitude=12.9300, longitude=80.1100),
    "Chromepet": LocationPoint(latitude=12.9516, longitude=80.1401),
    "Velachery": LocationPoint(latitude=12.9807, longitude=80.2189),
}


class EnvironmentalDataError(RuntimeError):
    pass


class OpenMeteoWeatherClient:
    """Fetch non-authoritative gridded weather context for a pilot location.

    Open-Meteo is intentionally treated as a fallback/prototyping source.
    Official Chennai/IMD observations should take precedence when machine-
    readable access is available.
    """

    endpoint = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, location: PilotLocation) -> EnvironmentalData:
        point = PILOT_COORDINATES[location]

        params = {
            "latitude": point.latitude,
            "longitude": point.longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "wind_speed_10m",
                    "wind_direction_10m",
                ]
            ),
            "hourly": "precipitation",
            "past_days": 1,
            "forecast_days": 1,
            "timezone": "Asia/Kolkata",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }

        request = Request(
            f"{self.endpoint}?{urlencode(params)}",
            headers={"User-Agent": "CrisisLensAI/0.2"},
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise EnvironmentalDataError(
                f"Unable to retrieve Open-Meteo weather data for {location}."
            ) from exc

        return self._parse(payload)

    @staticmethod
    def _parse(payload: dict[str, Any]) -> EnvironmentalData:
        current = payload.get("current") or {}
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        precipitation = hourly.get("precipitation") or []

        current_time_raw = current.get("time")
        rainfall_1h: float | None = None
        rainfall_24h: float | None = None

        if current_time_raw and times and len(times) == len(precipitation):
            try:
                current_dt = datetime.fromisoformat(current_time_raw)
                hourly_dts = [datetime.fromisoformat(value) for value in times]

                eligible = [
                    (dt, value)
                    for dt, value in zip(hourly_dts, precipitation)
                    if dt <= current_dt and value is not None
                ]

                if eligible:
                    rainfall_1h = float(eligible[-1][1])
                    rainfall_24h = float(
                        sum(float(value) for _, value in eligible[-24:])
                    )
            except (TypeError, ValueError):
                rainfall_1h = None
                rainfall_24h = None

        return EnvironmentalData(
            rainfall_1h_mm=rainfall_1h,
            rainfall_24h_mm=rainfall_24h,
            temperature_c=_as_float(current.get("temperature_2m")),
            humidity_percent=_as_float(current.get("relative_humidity_2m")),
            wind_speed_kmph=_as_float(current.get("wind_speed_10m")),
            wind_direction_deg=_as_float(current.get("wind_direction_10m")),
            water_level_m=None,
            observed_at=current_time_raw,
            source_name="Open-Meteo Forecast API",
            source_kind="gridded_weather_fallback",
        )


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
