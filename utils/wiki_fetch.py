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
    Returns a list of dicts: { title, lat, lon, extract }
    radius_m is capped at 10000 by Wikipedia's geosearch API.
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
    resp = requests.get(WIKI_API, params=geosearch_params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    pages = resp.json().get("query", {}).get("geosearch", [])
    if not pages:
        return []

    titles = "|".join(p["title"] for p in pages)
    extract_params = {
        "action": "query",
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "titles": titles,
        "format": "json",
    }
    resp2 = requests.get(WIKI_API, params=extract_params, headers=HEADERS, timeout=10)
    resp2.raise_for_status()
    pages_by_title = resp2.json().get("query", {}).get("pages", {})
    extract_lookup = {p["title"]: p.get("extract", "") for p in pages_by_title.values()}

    results = []
    for p in pages:
        results.append(
            {
                "title": p["title"],
                "lat": p["lat"],
                "lon": p["lon"],
                "extract": extract_lookup.get(p["title"], ""),
            }
        )
    return results
