"""
Cross-verifies OSM POIs against Wikipedia's nearby-articles list, and
filters out anything that isn't actually a temple, heritage/attraction
site, or activity -- Wikipedia's geosearch returns ANY nearby geotagged
article (bus stands, universities, hospitals, government offices), so
this filtering step is what keeps results relevant.

Matching logic (deliberately simple -- good enough for shortlisting,
not a bulletproof entity-resolution system):
  - Two records "match" if they're within MATCH_RADIUS_KM of each other
    AND their names are similar enough (fuzzy string match).
  - A matched OSM POI is marked verified=True and gets the Wikipedia
    extract + thumbnail attached.
  - Wikipedia articles with no nearby OSM match are only kept if their
    name/description clearly indicates one of our three categories --
    otherwise they're dropped as noise.
  - Everything (OSM-derived or Wikipedia-only) also passes through a
    blacklist and a minimum-description-length quality gate.
"""

from difflib import SequenceMatcher
from utils.geo import haversine_km

MATCH_RADIUS_KM = 0.15  # 150 m
NAME_SIMILARITY_THRESHOLD = 0.55

# Names containing any of these are dropped outright, regardless of
# category or source -- these are the "who would actually go there"
# results (transit infra, civic buildings, education, etc.).
BLACKLIST_KEYWORDS = [
    "university", "college", "school", "hospital", "clinic",
    "bus stand", "bus station", "bus depot", "bus terminal",
    "railway station", "metro station",
    "court", "constituency", "assembly", "collectorate", "taluk",
    "police station", "fire station", "secretariat", "municipal",
    "corporation office", "post office", "panchayat office",
    "electricity board", "water authority", "stadium", "ground",
]

# Used only to reclassify a Wikipedia-only article (no OSM match) into
# one of our three real categories. If nothing matches, the article is
# dropped rather than kept as a vague "other" bucket.
TEMPLE_KEYWORDS = [
    "temple", "church", "mosque", "synagogue", "shrine", "basilica",
    "cathedral", "mutt", "ashram", "gurudwara", "monastery",
]
HERITAGE_KEYWORDS = [
    "palace", "fort", "museum", "heritage", "monument", "memorial",
    "fortress", "tomb", "mausoleum", "archaeological", "ruins",
    "gate", "bastion", "haveli", "fossil",
]
ACTIVITY_KEYWORDS = [
    "beach", "waterfall", "park", "zoo", "garden", "backwater",
    "lake", "island", "sanctuary", "wildlife", "hill station",
    "viewpoint", "dam", "cave", "lighthouse", "theme park",
]

# Below this many characters of description, an entry is dropped --
# a one-line stub usually signals something too minor to be package-worthy.
MIN_DESCRIPTION_LENGTH = 150


def _is_blacklisted(name: str) -> bool:
    lname = name.lower()
    return any(kw in lname for kw in BLACKLIST_KEYWORDS)


def _reclassify_by_keywords(name: str, description: str):
    """Returns one of our 3 categories, or None if nothing matches."""
    text = f"{name} {description}".lower()
    if any(kw in text for kw in TEMPLE_KEYWORDS):
        return "temple"
    if any(kw in text for kw in HERITAGE_KEYWORDS):
        return "heritage_attraction"
    if any(kw in text for kw in ACTIVITY_KEYWORDS):
        return "activity"
    return None


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def cross_verify(osm_pois: list, wiki_articles: list) -> list:
    merged = []
    used_wiki_indices = set()

    for poi in osm_pois:
        if _is_blacklisted(poi["name"]):
            continue
        if poi["category"] not in ("temple", "heritage_attraction", "activity"):
            continue  # drop anything OSM tagged that didn't map cleanly

        poi = dict(poi)
        poi["verified"] = False
        poi["description"] = ""
        poi["thumbnail_url"] = None

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
            poi["description"] = wiki_articles[best_idx]["extract"]
            poi["thumbnail_url"] = wiki_articles[best_idx].get("thumbnail_url")
            used_wiki_indices.add(best_idx)

        merged.append(poi)

    # Wikipedia articles with no OSM match: only keep if we can confidently
    # reclassify them into one of our 3 categories via keywords, and they
    # pass the blacklist.
    for i, w in enumerate(wiki_articles):
        if i in used_wiki_indices:
            continue
        if _is_blacklisted(w["title"]):
            continue
        category = _reclassify_by_keywords(w["title"], w["extract"])
        if category is None:
            continue
        merged.append(
            {
                "name": w["title"],
                "lat": w["lat"],
                "lon": w["lon"],
                "category": category,
                "osm_tags": {},
                "verified": False,
                "description": w["extract"],
                "thumbnail_url": w.get("thumbnail_url"),
            }
        )

    # Quality gate: drop anything with too thin a description to be
    # package-worthy or genuinely useful to a planner.
    merged = [m for m in merged if len(m.get("description") or "") >= MIN_DESCRIPTION_LENGTH]

    return merged
