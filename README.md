# ☄️ Gaia DR3 · Asteroid Observatory

Interactive Streamlit dashboard analysing **16 named asteroids** connected to
Central Asian scientific heritage, using data from the **ESA Gaia DR3** Solar
System Object catalogue.

> **Data source:** Данные получены из Gaia DR3 (ESA/Gaia/DPAC)

---

## Project structure

```
gaia_asteroids/
├── app.py              ← Streamlit dashboard (main entry point)
├── data_loader.py      ← ETL pipeline (Gaia TAP → DuckDB)
├── ddl.py              ← DuckDB schema: tables, views, indexes
├── requirements.txt
├── queries/
│   ├── 01_orbital_elements.sql
│   └── 02_07_queries.sql   ← phase space, lightcurve, phase curve,
│                               obs stats, sky positions, belt comparison
└── data/               ← auto-created; CSV cache of last fetch
```

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the dashboard
#    On first launch it will automatically fetch data from ESA Gaia
#    (requires internet). Falls back to synthetic data if unreachable.
streamlit run app.py

# ── Optional: pre-populate the database manually ──────────────

# Fetch real data from ESA Gaia TAP service
python data_loader.py

# Use synthetic fallback (offline / CI)
python data_loader.py --no-real-data

# (Re)create schema only
python ddl.py
```

---

## ETL pipeline (`data_loader.py`)

```
ESA Gaia TAP+
(astroquery.gaia)
       │
       ▼  ADQL queries
┌──────────────────┐    ┌──────────────────────┐
│  gaiadr3.        │    │  gaiadr3.            │
│  sso_source      │    │  sso_observation     │
│  (orbital elems) │    │  (per-transit phot.) │
└──────┬───────────┘    └──────────┬───────────┘
       │  clean_sso_source()       │  clean_sso_observation()
       ▼                           ▼
   DataFrame                   DataFrame
       │                           │
       └──────────┬────────────────┘
                  ▼
           DuckDB tables
    sso_source · sso_observation
    asteroid_catalog
                  │
                  ▼
           DuckDB views
    v_orbital_summary · v_phase_space
    v_lightcurve · v_phase_curve
    v_sky_positions · v_observation_stats
```

---

## Dashboard tabs

| Tab | Content |
|-----|---------|
| 🌌 Phase Space | a vs i scatter + belt pie + e vs i |
| 🔭 Orbital Detail | Radar chart + parameter table + violin comparison |
| 📈 Photometry | Light curve + phase curve + distance timeline |
| 🗺️ Sky Map | Latest RA/Dec positions for all 16 objects |
| 📋 Full Catalogue | Sortable orbital table + observation quality stats |
| ℹ️ Source Info | Attribution, citations, namesake biographies |

---

## Data attribution

```
Gaia Collaboration, Vallenari, A., et al. (2023).
Gaia Data Release 3. Summary of the content and survey properties.
A&A, 674, A1. DOI: 10.1051/0004-6361/202243940

Gaia Collaboration, Tanga, P., et al. (2023).
Gaia Data Release 3. The Solar System survey.
A&A, 674, A12. DOI: 10.1051/0004-6361/202244220
```

Licence: **Creative Commons Attribution 4.0 International (CC BY 4.0)**
