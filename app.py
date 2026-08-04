"""
IRCTC Attraction Scout -- internal lookup tool for package planning.

Given a place name, this queries OpenStreetMap + Wikipedia live (no stored
database, per data-source ToS), cross-verifies results between the two,
filters out irrelevant results (bus stands, universities, etc.), scores
each attraction for "how apt is this for an IRCTC package", and groups
nearby attractions into day-trip clusters.

Run locally:   streamlit run app.py
"""

import io
import streamlit as st
import pandas as pd

from utils.geo import geocode_place
from utils.osm_fetch import fetch_osm_pois
from utils.wiki_fetch import fetch_wiki_nearby
from utils.merge import cross_verify
from utils.scoring import score_attractions, cluster_attractions

st.set_page_config(page_title="IRCTC Attraction Scout", page_icon="🚉", layout="wide")

CATEGORY_LABELS = {
    "temple": "Temple / Religious Site",
    "heritage_attraction": "Heritage & Attraction",
    "activity": "Activity / Recreation",
}

st.title("🚉 IRCTC Attraction Scout")
st.caption(
    "Look up attractions, temples, and heritage sites near a place to help "
    "shortlist candidates for new tour packages. Live lookup — nothing is "
    "stored between searches."
)

with st.sidebar:
    st.header("Search settings")
    place = st.text_input("Place name", placeholder="e.g. Kochi")
    radius_km = st.slider("Search radius (km)", min_value=5, max_value=30, value=15)
    cluster_eps_km = st.slider("Group attractions within (km)", min_value=1, max_value=8, value=3)
    min_score = st.slider("Minimum apt score to show", min_value=0, max_value=100, value=25)

    st.divider()
    st.subheader("Categories")
    show_temple = st.checkbox("Temple / Religious Site", value=True)
    show_heritage = st.checkbox("Heritage & Attraction", value=True)
    show_activity = st.checkbox("Activity / Recreation", value=True)

    st.divider()
    sort_by = st.selectbox(
        "Sort results by",
        ["Apt score (high to low)", "Alphabetical", "Distance from search center"],
    )

    search_clicked = st.button("Search", type="primary")

    st.divider()
    st.caption(
        "Data sources: OpenStreetMap (Overpass) + Wikipedia geosearch, "
        "cross-verified against each other. No API key required. "
        "Nearest-station distance is shown for info only — it does not "
        "affect scoring, since IRCTC packages often move tourists by bus "
        "between sites."
    )


def make_excel_download(rows: list, place: str) -> bytes:
    """
    Builds an .xlsx in memory. Keeps the sheet scannable: a short summary
    (not the full paragraph) plus a clickable photo link, rather than
    cramming full descriptions into cells.
    """
    df = pd.DataFrame(rows)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Attractions")
    return buffer.getvalue()


def short_summary(description: str, max_len: int = 200) -> str:
    if not description:
        return ""
    if len(description) <= max_len:
        return description
    # cut at the last full sentence within the limit, fall back to a hard cut
    cut = description[:max_len]
    last_period = cut.rfind(". ")
    if last_period > 60:
        return cut[: last_period + 1]
    return cut.rstrip() + "…"


if search_clicked:
    if not place.strip():
        st.warning("Enter a place name to search.")
        st.stop()

    with st.spinner(f"Locating '{place}'..."):
        geocoded = geocode_place(place)

    if geocoded is None:
        st.error(f"Couldn't find '{place}'. Try a more specific name (e.g. add the state).")
        st.stop()

    lat, lon, display_name = geocoded
    st.success(f"Searching around: {display_name}")

    radius_m = radius_km * 1000

    col1, col2 = st.columns(2)
    with col1:
        with st.spinner("Fetching OpenStreetMap points of interest..."):
            osm_pois = fetch_osm_pois(lat, lon, radius_m)
    with col2:
        with st.spinner("Fetching nearby Wikipedia articles..."):
            wiki_articles = fetch_wiki_nearby(lat, lon, radius_m)

    st.caption(f"Found {len(osm_pois)} OSM candidates and {len(wiki_articles)} Wikipedia articles nearby.")

    with st.spinner("Cross-verifying, filtering, and scoring..."):
        merged = cross_verify(osm_pois, wiki_articles)
        scored = score_attractions(merged, lat, lon)
        scored = [s for s in scored if s["apt_score"] >= min_score]

        allowed_categories = set()
        if show_temple:
            allowed_categories.add("temple")
        if show_heritage:
            allowed_categories.add("heritage_attraction")
        if show_activity:
            allowed_categories.add("activity")
        scored = [s for s in scored if s["category"] in allowed_categories]

        if sort_by == "Alphabetical":
            scored.sort(key=lambda x: x["name"])
        elif sort_by == "Distance from search center":
            scored.sort(key=lambda x: x["distance_from_center_km"])
        # else: already sorted by apt_score descending from score_attractions

        clusters = cluster_attractions(scored, eps_km=cluster_eps_km)

    if not scored:
        st.warning(
            "No attractions cleared the filters. Try lowering the score "
            "threshold, widening the radius, or enabling more categories."
        )
        st.stop()

    st.subheader(f"{len(scored)} attractions found, grouped into {len(clusters)} clusters")
    st.caption(
        "Clusters are rough same-day groupings by proximity — a starting "
        "point for chaining stops into a package, not a fixed itinerary. "
        "Intra-cluster distance shows how spread out the sites are within "
        "each group."
    )

    for i, cluster in enumerate(clusters, start=1):
        points = sorted(cluster["points"], key=lambda x: x["apt_score"], reverse=True) if sort_by == "Apt score (high to low)" else cluster["points"]
        top = points[0]
        spread_note = (
            f" · avg {cluster['avg_intra_km']} km / max {cluster['max_intra_km']} km apart"
            if len(points) > 1 else ""
        )
        with st.expander(
            f"Cluster {i}: near {top['name']}  ·  {len(points)} site(s){spread_note}",
            expanded=(i <= 2),
        ):
            for p in points:
                img_col, text_col = st.columns([1, 4])
                with img_col:
                    if p.get("thumbnail_url"):
                        st.image(p["thumbnail_url"], use_container_width=True)
                    else:
                        st.caption("No photo available")
                with text_col:
                    verified_tag = "✅ Verified" if p["verified"] else "— Unverified (single source)"
                    st.markdown(
                        f"**{p['name']}**  ·  {CATEGORY_LABELS.get(p['category'], p['category'])}  ·  "
                        f"Apt score: {p['apt_score']}  ·  {verified_tag}"
                    )
                    st.caption(
                        f"Typical visit: {p['visit_duration']}  ·  "
                        f"~{p['distance_from_center_km']} km from search center  ·  "
                        f"~{p['nearest_station_km']} km from {p['nearest_station']} "
                        f"(info only, not scored)"
                    )
                    st.write(p["description"] or "_No description available._")
                st.divider()

    with st.expander("Download results as Excel"):
        st.caption(
            "Includes a short summary and a photo link per row (full "
            "descriptions and inline images aren't practical in a "
            "spreadsheet — view those in the app above)."
        )
        rows = [
            {
                "Name": p["name"],
                "Category": CATEGORY_LABELS.get(p["category"], p["category"]),
                "Apt score": p["apt_score"],
                "Verified": "Yes" if p["verified"] else "No",
                "Visit duration": p["visit_duration"],
                "Latitude": p["lat"],
                "Longitude": p["lon"],
                "Distance from search center (km)": p["distance_from_center_km"],
                "Nearest station": p["nearest_station"],
                "Nearest station (km)": p["nearest_station_km"],
                "Summary": short_summary(p["description"]),
                "Photo URL": p.get("thumbnail_url") or "",
            }
            for p in scored
        ]
        excel_bytes = make_excel_download(rows, place)
        st.download_button(
            "Download Excel (.xlsx)",
            excel_bytes,
            file_name=f"{place}_attractions.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

else:
    st.info("Enter a place name in the sidebar and click **Search** to get started.")
