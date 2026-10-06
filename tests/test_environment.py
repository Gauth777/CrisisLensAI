from __future__ import annotations

from crisislens.data.environment import OpenMeteoWeatherClient


def test_open_meteo_parser_builds_24h_rainfall_and_provenance() -> None:
    times = [f"2026-10-05T{hour:02d}:00" for hour in range(24)]
    payload = {
        "current": {
            "time": "2026-10-05T23:00",
            "temperature_2m": 27.4,
            "relative_humidity_2m": 91,
            "wind_speed_10m": 31,
            "wind_direction_10m": 140,
        },
        "hourly": {
            "time": times,
            "precipitation": [1.0] * 24,
        },
    }

    result = OpenMeteoWeatherClient._parse(payload)

    assert result.rainfall_1h_mm == 1.0
    assert result.rainfall_24h_mm == 24.0
    assert result.temperature_c == 27.4
    assert result.humidity_percent == 91.0
    assert result.wind_speed_kmph == 31.0
    assert result.wind_direction_deg == 140.0
    assert result.water_level_m is None
    assert result.source_kind == "gridded_weather_fallback"


def test_open_meteo_parser_tolerates_missing_rainfall_series() -> None:
    payload = {
        "current": {
            "time": "2026-10-05T23:00",
            "temperature_2m": 28.0,
        },
        "hourly": {},
    }

    result = OpenMeteoWeatherClient._parse(payload)

    assert result.rainfall_1h_mm is None
    assert result.rainfall_24h_mm is None
    assert result.temperature_c == 28.0


def test_partial_or_gapped_series_does_not_claim_24h_total() -> None:
    payload = {
        "current": {"time": "2026-10-05T23:15"},
        "hourly": {"time": ["2026-10-05T22:00", "2026-10-05T23:00"], "precipitation": [2.0, 3.0]},
    }
    result = OpenMeteoWeatherClient._parse(payload)
    assert result.rainfall_1h_mm == 3.0
    assert result.rainfall_24h_mm is None
    payload["hourly"]["precipitation"][-1] = None
    assert OpenMeteoWeatherClient._parse(payload).rainfall_1h_mm is None
