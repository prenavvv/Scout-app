"""
Pulls nearby Wikipedia articles (name + short description + coordinates)
around a point. Used two ways downstream:
  1. Cross-verification -- if an OSM POI has a matching nearby Wikipedia
     article, we trust it more.
  2. Popularity proxy -- having a substantial Wikipedia article at all is a
     weak-but-free signal that a place is genuinely notable, vs. a random
     shop tagged "attraction" in OSM.
"""

import requests
import streamlit as st

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "irctc-attraction-scout/1.0 (internal tool)"}


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def fetch_wiki_nearby(lat: float, lon: float, radius_m: int = 15000, limit: int = 50):
    """
    Returns a list of dicts: { title, lat, lon, extract, thumbnail_url }
    radius_m is capped at 10000 by Wikipedia's geosearch API.
    extract is a longer excerpt (up to ~10 sentences), not just the intro
    line, since the manager wants real detail (what it is, where, why it
    matters) -- not a one-line teaser.
    """
    radius_m = min(radius_m, 10000)

    geosearch_params = {
        "action": "query",
        "list": "geosearch",
        "gscoord": f"{lat}|{lon}",
        "gsradius": radius_m,
        "gslimit": limit,
        "format": "json",
    }
    try:
        resp = requests.get(WIKI_API, params=geosearch_params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"Couldn't reach Wikipedia's API: {e}")
        return []

    pages = resp.json().get("query", {}).get("geosearch", [])
    if not pages:
        return []

    titles = "|".join(p["title"] for p in pages)
    extract_params = {
        "action": "query",
        "prop": "extracts|pageimages",
        "exsentences": 10,       # longer excerpt, not just the intro teaser
        "explaintext": True,
        "piprop": "thumbnail",
        "pithumbsize": 400,
        "titles": titles,
        "format": "json",
    }
    try:
        resp2 = requests.get(WIKI_API, params=extract_params, headers=HEADERS, timeout=15)
        resp2.raise_for_status()
    except requests.exceptions.RequestException as e:
        st.error(f"Couldn't fetch Wikipedia article extracts: {e}")
        return []

    pages_by_title = resp2.json().get("query", {}).get("pages", {})
    extract_lookup = {}
    thumb_lookup = {}
    for p in pages_by_title.values():
        extract_lookup[p["title"]] = p.get("extract", "")
        thumb_lookup[p["title"]] = p.get("thumbnail", {}).get("source")

    results = []
    for p in pages:
        results.append(
            {
                "title": p["title"],
                "lat": p["lat"],
                "lon": p["lon"],
                "extract": extract_lookup.get(p["title"], ""),
                "thumbnail_url": thumb_lookup.get(p["title"]),
            }
        )
    return results


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def search_wiki_by_name(name: str, near_lat: float, near_lon: float, max_km: float = 5.0):
    """
    Fallback lookup for OSM POIs that didn't match anything via the
    proximity-based geosearch (e.g. their Wikipedia article exists but
    sits just outside the match radius, or geosearch simply didn't
    surface it in the top results). Searches Wikipedia by the place's own
    name instead, and only accepts a result if it has coordinates within
    max_km of the POI -- otherwise a same-named place elsewhere in India
    could get wrongly attached.

    Returns a dict like fetch_wiki_nearby's entries, or None if nothing
    close enough was found.
    """
    from utils.geo import haversine_km

    search_params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": 3,
        "format": "json",
    }
    try:
        resp = requests.get(WIKI_API, params=search_params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    candidates = resp.json().get("query", {}).get("search", [])
    if not candidates:
        return None

    titles = "|".join(c["title"] for c in candidates)
    detail_params = {
        "action": "query",
        "prop": "extracts|pageimages|coordinates",
        "exsentences": 10,
        "explaintext": True,
        "piprop": "thumbnail",
        "pithumbsize": 400,
        "titles": titles,
        "format": "json",
    }
    try:
        resp2 = requests.get(WIKI_API, params=detail_params, headers=HEADERS, timeout=10)
        resp2.raise_for_status()
    except requests.exceptions.RequestException:
        return None

    pages = resp2.json().get("query", {}).get("pages", {})
    best = None
    best_dist = max_km
    for p in pages.values():
        coords = p.get("coordinates")
        if not coords:
            continue
        plat, plon = coords[0]["lat"], coords[0]["lon"]
        dist = haversine_km(near_lat, near_lon, plat, plon)
        if dist <= best_dist:
            best_dist = dist
            best = {
                "title": p["title"],
                "lat": plat,
                "lon": plon,
                "extract": p.get("extract", ""),
                "thumbnail_url": p.get("thumbnail", {}).get("source"),
            }

    return best
