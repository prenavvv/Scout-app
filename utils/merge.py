"""
Cross-verifies OSM POIs against Wikipedia's nearby-articles list, and
filters out obvious non-tourism noise (bus stands, universities,
hospitals, government offices) via a keyword blacklist.

Deliberately permissive beyond that -- prioritizes giving the manager
plenty of candidates to eyeball over perfect precision. Matching logic:
  - Two records "match" if they're within MATCH_RADIUS_KM of each other
    AND their names are similar enough (fuzzy string match).
  - A matched OSM POI is marked verified=True and gets the Wikipedia
    extract + thumbnail attached.
  - Unmatched OSM POIs get a second-chance name-based Wikipedia search.
  - Wikipedia articles with no OSM match are kept and best-effort
    categorized by keyword, rather than dropped.
  - Anything without a real description gets a generic fallback label
    instead of being excluded.
"""

from difflib import SequenceMatcher
from utils.geo import haversine_km
from utils.wiki_fetch import search_wiki_by_name

MATCH_RADIUS_KM = 0.3  # 300 m -- loosened from 150m, way-tagged complexes
                        # often have a centroid offset from their wiki coords
NAME_SIMILARITY_THRESHOLD = 0.45

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
# one of our three real categories.
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

CATEGORY_FALLBACK_LABEL = {
    "temple": "a temple / religious site",
    "heritage_attraction": "a heritage site or attraction",
    "activity": "an activity / recreation spot",
}

# Below this many characters, treat the description as effectively
# missing (used for a fallback label, not to drop the result).
MIN_DESCRIPTION_LENGTH = 20


def _is_blacklisted(name: str) -> bool:
    lname = name.lower()
    return any(kw in lname for kw in BLACKLIST_KEYWORDS)


def _reclassify_by_keywords(name: str, description: str):
    """
    Returns one of our 3 categories based on keyword match. Falls back to
    'heritage_attraction' (the broadest "worth a look" bucket) rather than
    dropping the entry -- volume matters more than perfect categorization
    here, the manager can eyeball and discard irrelevant ones manually.
    """
    text = f"{name} {description}".lower()
    if any(kw in text for kw in TEMPLE_KEYWORDS):
        return "temple"
    if any(kw in text for kw in ACTIVITY_KEYWORDS):
        return "activity"
    if any(kw in text for kw in HERITAGE_KEYWORDS):
        return "heritage_attraction"
    return "heritage_attraction"


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
        else:
            # Didn't match anything via nearby-article geosearch -- try a
            # direct name-based search before giving up on this POI. This
            # recovers real places whose Wikipedia article exists but sits
            # just outside the proximity match, or wasn't in the top
            # geosearch results at all.
            fallback = search_wiki_by_name(poi["name"], poi["lat"], poi["lon"])
            if fallback:
                poi["verified"] = True
                poi["description"] = fallback["extract"]
                poi["thumbnail_url"] = fallback.get("thumbnail_url")

        merged.append(poi)

    # Wikipedia articles with no OSM match: keep them all (after blacklist),
    # reclassified into whichever of our 3 categories fits best.
    for i, w in enumerate(wiki_articles):
        if i in used_wiki_indices:
            continue
        if _is_blacklisted(w["title"]):
            continue
        category = _reclassify_by_keywords(w["title"], w["extract"])
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

    # Fill in a light fallback label for anything that still has no
    # description at all (rather than dropping it) -- keeps volume up,
    # manager can still tell at a glance it's a thin/unverified entry.
    for m in merged:
        if len(m.get("description") or "") < MIN_DESCRIPTION_LENGTH:
            label = CATEGORY_FALLBACK_LABEL.get(m["category"], "a point of interest")
            m["description"] = (
                f"Listed as {label} in OpenStreetMap/Wikipedia data; "
                f"no detailed description available yet. Worth a manual check."
            )

    return merged
