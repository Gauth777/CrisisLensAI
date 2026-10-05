from __future__ import annotations

from ..schemas import PilotLocation

LOCATION_CONTEXT: dict[PilotLocation, str] = {
    "Tambaram": (
        "Tambaram is one of the three Chennai-region pilot locations for CrisisLens. "
        "Do not assume current flooding, rainfall, road closures, shelter status, or infrastructure damage unless supplied in the inference input."
    ),
    "Chromepet": (
        "Chromepet is one of the three Chennai-region pilot locations for CrisisLens. "
        "Do not assume current flooding, rainfall, road closures, shelter status, or infrastructure damage unless supplied in the inference input."
    ),
    "Velachery": (
        "Velachery is one of the three Chennai pilot locations for CrisisLens. "
        "Do not infer current flood conditions from general location knowledge; current conditions must be supported by the supplied report or environmental data."
    ),
}

def get_location_context(location: PilotLocation) -> str:
    return LOCATION_CONTEXT[location]
