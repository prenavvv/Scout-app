"""
Cross-verifies OSM POIs against Wikipedia's nearby-articles list.

Matching logic (kept deliberately simple -- good enough for shortlisting,
not meant to be a bulletproof entity-resolution system):
  - Two records "match" if they're within MATCH_RADIUS_KM of each other
    AND their names are similar enough (fuzzy string match).
  - A matched OSM POI is marked verified=True and gets the Wikipedia
    extract attached as its description.
  - Wikipedia articles with no nearby OSM match are still included
    (some genuinely important sites are under-tagged in OSM), but flagged
    verified=False and given a lower base category weight.
"""

from difflib import SequenceMatcher
from utils.geo import haversine_km

MATCH_RADIUS_KM = 0.15  # 150 m
NAME_SIMILARITY_THRESHOLD = 0.55


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def cross_verify(osm_pois: list, wiki_articles: list) -> list:
    merged = []
    used_wiki_indices = set()

    for poi in osm_pois:
        poi = dict(poi)  # don't mutate the cached list
        poi["verified"] = False
        poi["description"] = ""

        best_idx, best_score = None, 0.0
        for i, w in enumerate(wiki_articles):
            if i in used_wiki_indices:
                continue
            dist = haversine_km(poi["lat"], poi["lon"], w["lat"], w["lon"])
            if dist > MATCH_RADIUS_KM:
                continue
            sim = _name_similarity(poi["name"], w["title"])
            if sim > best_score:
                best_idx, best_score = i, sim

        if best_idx is not None and best_score >= NAME_SIMILARITY_THRESHOLD:
            poi["verified"] = True
            poi["description"] = wiki_articles[best_idx]["extract"][:400]
            used_wiki_indices.add(best_idx)

        merged.append(poi)

    # Wikipedia articles that never matched anything in OSM --
    # still worth surfacing, just as a lower-confidence, "other" category
    # entry unless it's obviously a temple/heritage site by name.
    for i, w in enumerate(wiki_articles):
        if i in used_wiki_indices:
            continue
        merged.append(
            {
                "name": w["title"],
                "lat": w["lat"],
                "lon": w["lon"],
                "category": "wiki_only",
                "osm_tags": {},
                "verified": False,
                "description": w["extract"][:400],
            }
        )

    return merged
