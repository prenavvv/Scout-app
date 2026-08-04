# IRCTC Attraction Scout

Internal lookup tool: enter a place name, get back attractions/temples/heritage
sites nearby, scored for how well they'd fit an IRCTC tour package, and
grouped into rough same-day clusters.

**Live lookup only** — nothing is stored in a database. Every search queries
OpenStreetMap and Wikipedia fresh (with short-term result caching, see below),
which keeps this compliant with both services' terms of use.

---

## 1. Run it locally (VS Code)

**Requirements:** Python 3.9+

```bash
# 1. Open this folder in VS Code

# 2. Create a virtual environment (recommended, keeps deps isolated)
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the app
streamlit run app.py
```

This opens automatically in your browser at `http://localhost:8501`. Try
searching "Kochi" first — that's what this was built and tested against.

Every time you save a file in VS Code, Streamlit will offer to auto-reload
the running app (or press `R` in the app).

---

## 2. How it works (quick tour of the code)

```
app.py                  <- the Streamlit UI, entry point
utils/
  geo.py               <- geocoding (place name -> lat/lon) + distance math
  osm_fetch.py         <- pulls candidate POIs from OpenStreetMap
  wiki_fetch.py        <- pulls nearby Wikipedia articles
  merge.py             <- cross-verifies OSM + Wikipedia results
  scoring.py           <- the "apt for IRCTC" score + clustering
  stations.py          <- hardcoded major railway station coordinates
```

**Pipeline for one search:**
1. Geocode the place name → coordinates (Nominatim/OSM)
2. Fetch OSM points of interest within the radius (temples, heritage,
   museums, viewpoints, natural sites)
3. Fetch nearby Wikipedia articles for the same area
4. Cross-verify: match OSM POIs to Wikipedia articles by proximity + name
   similarity — matched ones are marked "verified"
5. Score every attraction 0–100 using a weighted formula (category type,
   verification, popularity proxy, distance to nearest railway station)
6. Cluster nearby attractions into same-day groupings
7. Display, sorted and grouped, with a CSV export option

**The scoring weights live at the top of `utils/scoring.py`** — that's the
main thing you'll want to tune as you see real results. Currently weighted
toward temples/heritage sites and rail proximity, reflecting IRCTC's
pilgrimage-heavy package catalog.

---

## 3. Known limitations (v1)

- **Popularity signal is weak.** It's currently just "how long is the
  Wikipedia article," which loosely correlates with notability but isn't a
  real traveler-ratings signal. If you later get a Google Places API key
  (needs a billing account, but includes a $200/month free credit), that's
  the natural upgrade — swap in real ratings/review counts.
- **Railway stations list is a curated shortlist** (~50 major stations), not
  exhaustive. Add more to `utils/stations.py` as needed — it's a plain dict.
- **Clustering is a simple greedy radius grouping**, not a true optimal
  itinerary planner. It's meant to shortlist candidates for a human to
  refine, not auto-generate a final package.
- **Wikipedia's geosearch radius caps at 10km** even if you set a larger
  search radius in the sidebar — a Wikipedia API limitation, noted in
  `wiki_fetch.py`.

---

## 4. Deploying to Streamlit Community Cloud (same flow as your past project)

1. Push this folder to a GitHub repo (public is fine for this use case,
   since it's a single-user internal tool with no secrets committed).
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, click **New app**.
3. Select the repo, branch, and set the main file path to `app.py`.
4. Deploy. First load (and any load after a period of inactivity) may take
   10–30 seconds to "wake up" — this is normal for the free tier, not a bug.

**No API keys are needed for v1**, so there's nothing to add under
`Settings → Secrets`. If you later add a Google Places key, put it there
(never commit it to the repo) and read it in code via `st.secrets["GOOGLE_API_KEY"]`.

### If searches feel slow once deployed
The Overpass API (OpenStreetMap) is a shared public server and can be slower
under load than it was in local testing. If it becomes a recurring problem,
worth revisiting: a paid Overpass instance, a fallback mirror, or narrowing
the default search radius.
