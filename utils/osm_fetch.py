"""
Pulls candidate attractions/temples/heritage sites around a point using
OpenStreetMap's Overpass API. Completely free, no API key.

We ask Overpass for several tag categories relevant to IRCTC-style
packages (temples & other places of worship, historic sites, museums,
viewpoints, notable natural features) within a radius of a center point.
"""

import time
import requests
import streamlit as st

# Try the main instance first, fall back to a mirror if it's rate-limited
# or timing out -- the free public Overpass servers are shared infra and
# do occasionally throttle or hiccup under load, especially on repeated
# searches in a short window (per-IP rate limiting).
OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# category -> Overpass tag filter. Narrowed down to three buckets that
# actually matter for IRCTC package planning: temples/worship sites,
# heritage & attractions, and activities/recreation. (Dropped generic
# "artwork" and folded viewpoints into activities -- neither warranted
# being its own category.)
CATEGORY_FILTERS = {
    "temple": '["amenity"="place_of_worship"]',
    "heritage_attraction": '["historic"]',
    "heritage_attraction_2": '["tourism"="museum"]',
    "heritage_attraction_3": '["tourism"="attraction"]',
    "activity": '["tourism"="viewpoint"]',
    "activity_2": '["tourism"="zoo"]',
    "activity_3": '["tourism"="theme_park"]',
    "activity_4": '["leisure"="park"]',
    "activity_5": '["leisure"="water_park"]',
    "activity_6": '["natural"~"beach|waterfall"]',
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
    """Map a POI's OSM tags back to one of our three categories."""
    if tags.get("amenity") == "place_of_worship":
        return "temple"
    if "historic" in tags:
        return "heritage_attraction"
    if tags.get("tourism") in ("museum", "attraction"):
        return "heritage_attraction"
    if tags.get("tourism") in ("viewpoint", "zoo", "theme_park"):
        return "activity"
    if tags.get("leisure") in ("park", "water_park"):
        return "activity"
    if tags.get("natural") in ("beach", "waterfall"):
        return "activity"
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
        for attempt in range(2):  # one retry per mirror, with a short backoff
            try:
                resp = requests.post(url, data={"data": query}, timeout=35)
                resp.raise_for_status()
                last_error = None
                break
            except requests.exceptions.RequestException as e:
                last_error = e
                resp = None
                if attempt == 0:
                    time.sleep(3)  # brief pause before retrying, helps with 429s
                continue
        if resp is not None:
            break

    if resp is None:
        # Don't hard-fail the whole search over this -- OSM is one of two
        # data sources, and Wikipedia-derived results can still be useful
        # on their own. Downgrade to a warning, not a blocking error.
        st.warning(
            "OpenStreetMap's Overpass API is rate-limited or temporarily "
            "unavailable right now, so results below are Wikipedia-only "
            "for this search (no cross-verification). This is usually "
            "temporary -- wait a minute between searches and try again "
            f"for the full picture. (Last error: {last_error})"
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
