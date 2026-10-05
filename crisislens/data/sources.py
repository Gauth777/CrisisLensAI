from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSource:
    name: str
    purpose: str
    authority: str
    machine_access: str
    priority: int


DATA_SOURCES = [
    DataSource(
        name="Chennai Flood Monitor / RTFF & SDSS",
        purpose="Chennai rainfall, AWS weather and water-level context",
        authority="Government of Tamil Nadu / Chennai flood monitoring system",
        machine_access="Preferred official source; connector/API integration pending verification",
        priority=1,
    ),
    DataSource(
        name="India Meteorological Department AWS/ARG",
        purpose="Official weather-station observations",
        authority="India Meteorological Department",
        machine_access="Documented API exists; production access requires public-IP whitelisting",
        priority=2,
    ),
    DataSource(
        name="Open-Meteo",
        purpose="Gridded weather fallback for development and model testing",
        authority="Third-party weather API using numerical weather/reanalysis products",
        machine_access="Public JSON API",
        priority=3,
    ),
]


def describe_source_policy() -> str:
    ordered = sorted(DATA_SOURCES, key=lambda item: item.priority)
    return "\n".join(
        f"{item.priority}. {item.name}: {item.purpose}. {item.machine_access}."
        for item in ordered
    )
