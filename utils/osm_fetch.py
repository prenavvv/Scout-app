"""
Pulls candidate attractions/temples/heritage sites around a point using
OpenStreetMap's Overpass API. Completely free, no API key.

We ask Overpass for several tag categories relevant to IRCTC-style
packages (temples & other places of worship, historic sites, museums,
viewpoints, notable natural features) within a radius of a center point.
"""

import requests
import streamlit as st

# Try the main instance first, fall back to a mirror if it's rate-limited
# or timing out -- the free public Overpass servers are shared infra and
# do occasionally throttle or hiccup under load.
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# category -> Overpass tag filter, used both for querying and later scoring.
# Keep this list editable -- it's the main "what counts as relevant" knob.
CATEGORY_FILTERS = {
    "temple_or_worship": '["amenity"="place_of_worship"]',
    "historic_heritage": '["historic"]',
    "museum": '["tourism"="museum"]',
    "attraction": '["tourism"="attraction"]',
    "viewpoint": '["tourism"="viewpoint"]',
    "natural_feature": '["natural"~"beach|waterfall|peak"]',
    "artwork_landmark": '["tourism"="artwork"]',
}


def _build_query(lat: float, lon: float, radius_m: int) -> str:
    around = f"(around:{radius_m},{lat},{lon})"
    clauses = []
    for filt in CATEGORY_FILTERS.values():
        clauses.append(f"node{filt}{around};")
        clauses.append(f"way{filt}{around};")
    body = "\n  ".join(clauses)
    return f"""
    [out:json][timeout:25];
    (
      {body}
    );
    out center tags;
    """


def _classify(tags: dict) -> str:
    """Map a POI's OSM tags back to one of our simple categories."""
    if tags.get("amenity") == "place_of_worship":
        return "temple_or_worship"
    if "historic" in tags:
        return "historic_heritage"
    if tags.get("tourism") == "museum":
        return "museum"
    if tags.get("tourism") == "attraction":
        return "attraction"
    if tags.get("tourism") == "viewpoint":
        return "viewpoint"
    if tags.get("tourism") == "artwork":
        return "artwork_landmark"
    if tags.get("natural") in ("beach", "waterfall", "peak"):
        return "natural_feature"
    return "other"


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_osm_pois(lat: float, lon: float, radius_m: int = 15000):
    """
    Returns a list of dicts:
    { name, lat, lon, category, osm_tags }
    Unnamed POIs are dropped -- an attraction with no name isn't usable
    for a package suggestion anyway.
    """
    query = _build_query(lat, lon, radius_m)

    last_error = None
    resp = None
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data={"data": query}, timeout=35)
            resp.raise_for_status()
            last_error = None
            break
        except requests.exceptions.RequestException as e:
            last_error = e
            resp = None
            continue

    if resp is None:
        # Surface something useful in the Streamlit UI instead of a raw
        # traceback -- rate limiting (429) and timeouts (504) are the
        # most common causes with the free public Overpass servers.
        st.error(
            "Couldn't reach OpenStreetMap's Overpass API (it may be "
            "rate-limited or temporarily down). Try again in a minute, "
            "or narrow the search radius. "
            f"Last error: {last_error}"
        )
        return []

    elements = resp.json().get("elements", [])

    results = []
    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        if el["type"] == "node":
            plat, plon = el.get("lat"), el.get("lon")
        else:  # way -> Overpass gives a computed center when we ask "out center"
            center = el.get("center", {})
            plat, plon = center.get("lat"), center.get("lon")

        if plat is None or plon is None:
            continue

        results.append(
            {
                "name": name,
                "lat": plat,
                "lon": plon,
                "category": _classify(tags),
                "osm_tags": tags,
            }
        )

    # de-duplicate by name (OSM sometimes has both a node and a way for the
    # same place) -- keep the first occurrence.
    seen = set()
    deduped = []
    for r in results:
        key = r["name"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    return deduped
