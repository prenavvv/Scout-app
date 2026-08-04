"""
Scoring: turns raw merged POIs into an "apt for an IRCTC package" score,
0-100. Weights are named constants up top so they're easy to tune.

Note: nearest-railway-station distance is intentionally NOT part of the
score -- IRCTC packages often move tourists by bus between attractions
within a city/region, so rail proximity doesn't determine desirability.
It's still calculated and displayed as info, just not scored.

Clustering: groups nearby scored attractions into day-trip-sized clusters,
and reports the spread within each cluster (avg/max distance between
sites) so a planner can judge whether a cluster is a comfortable loop or
a stretch.
"""

from utils.geo import nearest_station, haversine_km
from utils.stations import STATIONS

# ---- Tunable weights (should sum to 1.0) ----
WEIGHT_CATEGORY = 0.45
WEIGHT_VERIFICATION = 0.25
WEIGHT_POPULARITY = 0.30

# Base desirability per category, reflecting IRCTC's pilgrimage/heritage-
# heavy package mix.
CATEGORY_WEIGHTS = {
    "temple": 1.0,
    "heritage_attraction": 0.9,
    "activity": 0.8,
}

# Rough visit-duration heuristic by category -- a planning aid, not a
# precise estimate. Refined slightly using OSM sub-tags where available.
DEFAULT_VISIT_DURATION = {
    "temple": "Quick stop (30-45 min)",
    "heritage_attraction": "Half-day (2-4 hrs)",
    "activity": "Half-day+ (3+ hrs)",
}
QUICK_STOP_HISTORIC_TAGS = {"monument", "memorial", "wayside_cross", "milestone"}


def _popularity_score(description: str) -> float:
    """
    Rough, free popularity proxy: longer Wikipedia extracts correlate
    loosely with how well-documented / notable a place is. Capped and
    normalized to 0-1.
    """
    length = len(description or "")
    return min(length / 800.0, 1.0)


def _estimate_visit_duration(poi: dict) -> str:
    tags = poi.get("osm_tags", {})
    if tags.get("tourism") == "viewpoint":
        return "Quick stop (15-30 min)"
    if tags.get("historic") in QUICK_STOP_HISTORIC_TAGS:
        return "Quick stop (20-30 min)"
    if tags.get("tourism") == "museum":
        return "Half-day (2-3 hrs)"
    return DEFAULT_VISIT_DURATION.get(poi["category"], "Half-day (2-3 hrs)")


def score_attractions(merged: list, center_lat: float, center_lon: float) -> list:
    scored = []
    for poi in merged:
        cat_score = CATEGORY_WEIGHTS.get(poi["category"], 0.5)
        verif_score = 1.0 if poi.get("verified") else 0.4
        pop_score = _popularity_score(poi.get("description", ""))

        total = (
            WEIGHT_CATEGORY * cat_score
            + WEIGHT_VERIFICATION * verif_score
            + WEIGHT_POPULARITY * pop_score
        )

        station_name, station_dist = nearest_station(poi["lat"], poi["lon"], STATIONS)
        dist_from_center = haversine_km(poi["lat"], poi["lon"], center_lat, center_lon)

        p = dict(poi)
        p["apt_score"] = round(total * 100, 1)
        p["nearest_station"] = station_name
        p["nearest_station_km"] = round(station_dist, 1)
        p["distance_from_center_km"] = round(dist_from_center, 1)
        p["visit_duration"] = _estimate_visit_duration(poi)
        scored.append(p)

    scored.sort(key=lambda x: x["apt_score"], reverse=True)
    return scored


def cluster_attractions(scored: list, eps_km: float = 3.0):
    """
    Simple greedy radius-based clustering: walk through attractions in
    score order, and either attach a point to an existing nearby cluster
    or start a new one. Also computes avg/max intra-cluster distance so
    a planner can see whether a cluster is a tight, walkable loop or a
    longer bus hop between spread-out sites.
    """
    clusters = []  # each: {"center": (lat, lon), "points": [...]}

    for poi in scored:
        placed = False
        for cluster in clusters:
            clat, clon = cluster["center"]
            if haversine_km(poi["lat"], poi["lon"], clat, clon) <= eps_km:
                cluster["points"].append(poi)
                n = len(cluster["points"])
                cluster["center"] = (
                    clat + (poi["lat"] - clat) / n,
                    clon + (poi["lon"] - clon) / n,
                )
                placed = True
                break
        if not placed:
            clusters.append({"center": (poi["lat"], poi["lon"]), "points": [poi]})

    for cluster in clusters:
        points = cluster["points"]
        if len(points) <= 1:
            cluster["avg_intra_km"] = 0.0
            cluster["max_intra_km"] = 0.0
            continue
        dists = []
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                dists.append(
                    haversine_km(points[i]["lat"], points[i]["lon"], points[j]["lat"], points[j]["lon"])
                )
        cluster["avg_intra_km"] = round(sum(dists) / len(dists), 1)
        cluster["max_intra_km"] = round(max(dists), 1)

    clusters.sort(key=lambda c: max(p["apt_score"] for p in c["points"]), reverse=True)
    return clusters
