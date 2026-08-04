"""
Scoring: turns raw merged POIs into an "apt for an IRCTC package" score,
0-100. This is the main tunable knob for the whole tool -- weights are
named constants up top so they're easy to argue about and change later
without hunting through the logic.

Clustering: groups nearby scored attractions into day-trip-sized clusters,
since that's what actually saves a package planner time (vs. a flat list).
"""

from utils.geo import nearest_station
from utils.stations import STATIONS

# ---- Tunable weights (should sum to 1.0 across the four components) ----
WEIGHT_CATEGORY = 0.35
WEIGHT_VERIFICATION = 0.20
WEIGHT_POPULARITY = 0.20
WEIGHT_STATION_PROXIMITY = 0.25

# Base desirability per category, reflecting IRCTC's pilgrimage/heritage-
# heavy package mix (see project notes). 0-1 scale.
CATEGORY_WEIGHTS = {
    "temple_or_worship": 1.0,
    "historic_heritage": 0.9,
    "museum": 0.75,
    "attraction": 0.7,
    "natural_feature": 0.65,
    "viewpoint": 0.55,
    "artwork_landmark": 0.45,
    "wiki_only": 0.5,   # notable enough for Wikipedia, but untagged in OSM
    "other": 0.3,
}

# Beyond this distance from the nearest hardcoded station, proximity
# score bottoms out at 0 -- a 60km taxi transfer isn't "rail-adjacent"
# in any useful sense for package planning.
STATION_PROXIMITY_CUTOFF_KM = 60.0


def _popularity_score(description: str) -> float:
    """
    Rough, free popularity proxy: longer Wikipedia extracts correlate
    loosely with how well-documented / notable a place is. Capped and
    normalized to 0-1. Not a substitute for real traveler ratings --
    flagged in the README as a place to plug in a better signal later.
    """
    length = len(description or "")
    return min(length / 500.0, 1.0)


def _station_proximity_score(lat: float, lon: float):
    name, dist_km = nearest_station(lat, lon, STATIONS)
    score = max(0.0, 1.0 - (dist_km / STATION_PROXIMITY_CUTOFF_KM))
    return score, name, dist_km


def score_attractions(merged: list) -> list:
    scored = []
    for poi in merged:
        cat_score = CATEGORY_WEIGHTS.get(poi["category"], 0.3)
        verif_score = 1.0 if poi.get("verified") else 0.4
        pop_score = _popularity_score(poi.get("description", ""))
        station_score, station_name, station_dist = _station_proximity_score(
            poi["lat"], poi["lon"]
        )

        total = (
            WEIGHT_CATEGORY * cat_score
            + WEIGHT_VERIFICATION * verif_score
            + WEIGHT_POPULARITY * pop_score
            + WEIGHT_STATION_PROXIMITY * station_score
        )

        p = dict(poi)
        p["apt_score"] = round(total * 100, 1)
        p["nearest_station"] = station_name
        p["nearest_station_km"] = round(station_dist, 1)
        scored.append(p)

    scored.sort(key=lambda x: x["apt_score"], reverse=True)
    return scored


def cluster_attractions(scored: list, eps_km: float = 3.0):
    """
    Simple greedy radius-based clustering (no sklearn dependency needed):
    walk through attractions in score order, and either attach a point to
    an existing nearby cluster or start a new one. Good enough for
    "what's within a comfortable same-day loop", which is the actual
    package-planning need here.
    """
    from utils.geo import haversine_km

    clusters = []  # each: {"center": (lat, lon), "points": [...]}

    for poi in scored:
        placed = False
        for cluster in clusters:
            clat, clon = cluster["center"]
            if haversine_km(poi["lat"], poi["lon"], clat, clon) <= eps_km:
                cluster["points"].append(poi)
                # recompute a simple running centroid
                n = len(cluster["points"])
                cluster["center"] = (
                    clat + (poi["lat"] - clat) / n,
                    clon + (poi["lon"] - clon) / n,
                )
                placed = True
                break
        if not placed:
            clusters.append({"center": (poi["lat"], poi["lon"]), "points": [poi]})

    # Rank clusters by their best single attraction, and drop singleton
    # "clusters" of just one weak site unless it's a strong site on its own.
    clusters.sort(key=lambda c: max(p["apt_score"] for p in c["points"]), reverse=True)
    return clusters
