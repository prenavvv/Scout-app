"""
IRCTC Attraction Scout -- internal lookup tool for package planning.

Given a place name, this queries OpenStreetMap + Wikipedia live (no stored
database, per data-source ToS), cross-verifies results between the two,
scores each attraction for "how apt is this for an IRCTC package", and
groups nearby attractions into day-trip clusters.

Run locally:   streamlit run app.py
"""

import streamlit as st
import pandas as pd

from utils.geo import geocode_place
from utils.osm_fetch import fetch_osm_pois
from utils.wiki_fetch import fetch_wiki_nearby
from utils.merge import cross_verify
from utils.scoring import score_attractions, cluster_attractions

st.set_page_config(page_title="IRCTC Attraction Scout", page_icon="🚉", layout="wide")

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
    search_clicked = st.button("Search", type="primary")

    st.divider()
    st.caption(
        "Data sources: OpenStreetMap (Overpass) + Wikipedia geosearch, "
        "cross-verified against each other. No API key required."
    )

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

    with st.spinner("Cross-verifying and scoring..."):
        merged = cross_verify(osm_pois, wiki_articles)
        scored = score_attractions(merged)
        scored = [s for s in scored if s["apt_score"] >= min_score]
        clusters = cluster_attractions(scored, eps_km=cluster_eps_km)

    if not scored:
        st.warning(
            "No attractions cleared the minimum score. Try lowering the "
            "score threshold or widening the search radius."
        )
        st.stop()

    st.subheader(f"{len(scored)} attractions found, grouped into {len(clusters)} clusters")
    st.caption(
        "Clusters are rough same-day groupings by proximity — a starting "
        "point for chaining stops into a package, not a fixed itinerary."
    )

    for i, cluster in enumerate(clusters, start=1):
        points = sorted(cluster["points"], key=lambda x: x["apt_score"], reverse=True)
        top = points[0]
        with st.expander(
            f"Cluster {i}: near {top['name']}  ·  {len(points)} site(s)  ·  "
            f"top score {top['apt_score']}",
            expanded=(i <= 3),
        ):
            df = pd.DataFrame(
                [
                    {
                        "Name": p["name"],
                        "Category": p["category"].replace("_", " "),
                        "Apt score": p["apt_score"],
                        "Verified": "✅" if p["verified"] else "—",
                        "Nearest station": p["nearest_station"],
                        "Station dist (km)": p["nearest_station_km"],
                        "Description": (p["description"][:150] + "…") if p["description"] else "",
                    }
                    for p in points
                ]
            )
            st.dataframe(df, hide_index=True, use_container_width=True)

    with st.expander("Download full results as CSV"):
        all_rows = [
            {
                "Name": p["name"],
                "Category": p["category"],
                "Apt score": p["apt_score"],
                "Verified": p["verified"],
                "Latitude": p["lat"],
                "Longitude": p["lon"],
                "Nearest station": p["nearest_station"],
                "Station dist (km)": p["nearest_station_km"],
                "Description": p["description"],
            }
            for p in scored
        ]
        csv = pd.DataFrame(all_rows).to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", csv, file_name=f"{place}_attractions.csv", mime="text/csv")

else:
    st.info("Enter a place name in the sidebar and click **Search** to get started.")
