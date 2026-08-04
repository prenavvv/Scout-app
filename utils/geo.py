"""
Small geo helpers: geocoding a place name, and haversine distance.

Uses Nominatim (OpenStreetMap's free geocoder) for turning "Kochi" into
coordinates. Nominatim asks that you set a real User-Agent and not hammer
it -- we respect both (single request per search, cached).
"""

import math
import requests
import streamlit as st

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim's usage policy requires a descriptive User-Agent identifying
# the app -- not optional, requests without one get blocked.
HEADERS = {"User-Agent": "irctc-attraction-scout/1.0 (internal tool)"}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocode_place(place_name: str, country_bias: str = "India"):
    """
    Turn a place name into (lat, lon, display_name).
    Returns None if nothing was found.
    """
    params = {
        "q": f"{place_name}, {country_bias}",
        "format": "json",
        "limit": 1,
    }
    resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    top = results[0]
    return float(top["lat"]), float(top["lon"]), top.get("display_name", place_name)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points, in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearest_station(lat, lon, stations: dict):
    """
    Given a point and a {name: (lat, lon)} dict of stations,
    return (station_name, distance_km) for the closest one.
    """
    best_name, best_dist = None, float("inf")
    for name, (slat, slon) in stations.items():
        d = haversine_km(lat, lon, slat, slon)
        if d < best_dist:
            best_name, best_dist = name, d
    return best_name, best_dist
