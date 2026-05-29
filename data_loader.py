"""
data_loader.py — ETL pipeline for Gaia DR3 SSO asteroid data.

Fetches Solar System Object (SSO) observations from ESA Gaia Archive
for a curated list of named minor planets, cleans the data,
and loads it into a local DuckDB database.

Data source: ESA Gaia DR3 / gaiadr3.sso_source + gaiadr3.sso_observation
Attribution: ESA/Gaia/DPAC
"""

import warnings
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import duckdb

warnings.filterwarnings("ignore")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# TARGET ASTEROID CATALOGUE
# ──────────────────────────────────────────────────────────────
TARGET_ASTEROIDS = {
    3095:  "Omarkhayyam",
    2755:  "Avicenna",
    9936:  "Al-Biruni",
    90806: "Rudaki",
    10269: "Tusi",
    11156: "Al-Khwarizmi",
    2469:  "Tajikistan",
    2746:  "Hissao",
    3013:  "Dobrovoleva",
    3945:  "Gerasimenko",
    4208:  "Kiselev",
    4207:  "Chernova",
    4011:  "Bakharev",
    7164:  "Babadzhanov",
    3436:  "Ibadinov",
    24533: "Kokhirova",
}

DB_PATH   = Path("gaia_asteroids.duckdb")
DATA_DIR  = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# ──────────────────────────────────────────────────────────────
# ADQL QUERIES
# ──────────────────────────────────────────────────────────────

def _sso_source_query(number_ids: list[int]) -> str:
    """ADQL query against gaiadr3.sso_source for orbital/physical parameters."""
    ids = ", ".join(str(i) for i in number_ids)
    return f"""
SELECT
    number_mp,
    denomination,
    num_of_obs,
    epoch_utc,
    semi_major_axis,
    eccentricity,
    inclination,
    ascending_node_longitude,
    perihelion_argument,
    mean_anomaly,
    perihelion_distance,
    aphelion_distance,
    orbital_period,
    mean_motion,
    tisserand_jupiter,
    g_mag_abs_mean,
    g_flux_mean,
    g_flux_mean_error
FROM gaiadr3.sso_source
WHERE number_mp IN ({ids})
ORDER BY number_mp
""".strip()


def _sso_observation_query(number_ids: list[int]) -> str:
    """ADQL query against gaiadr3.sso_observation for per-transit photometry."""
    ids = ", ".join(str(i) for i in number_ids)
    return f"""
SELECT
    number_mp,
    denomination,
    transit_id,
    epoch_utc,
    epoch_err,
    ra,
    dec,
    ra_error,
    dec_error,
    x_gaia_geocentric,
    y_gaia_geocentric,
    z_gaia_geocentric,
    vx_gaia_geocentric,
    vy_gaia_geocentric,
    vz_gaia_geocentric,
    g_mag,
    g_flux,
    g_flux_error,
    solar_elongation,
    phase_angle,
    heliocentric_distance,
    topocentric_distance
FROM gaiadr3.sso_observation
WHERE number_mp IN ({ids})
ORDER BY number_mp, epoch_utc
""".strip()


# ──────────────────────────────────────────────────────────────
# FETCHING
# ──────────────────────────────────────────────────────────────

def fetch_from_gaia(query: str, table_label: str) -> Optional[pd.DataFrame]:
    """
    Submit an ADQL query to ESA Gaia TAP service via astroquery.gaia.
    Returns a pandas DataFrame or None on failure.
    """
    try:
        from astroquery.gaia import Gaia  # type: ignore
        Gaia.ROW_LIMIT = -1  # no row cap
        log.info("Querying Gaia TAP — table: %s", table_label)
        job = Gaia.launch_job_async(query, verbose=False)
        result = job.get_results()
        df = result.to_pandas()
        log.info("  ✓ %d rows retrieved for %s", len(df), table_label)
        return df
    except Exception as exc:
        log.error("Gaia query failed for %s: %s", table_label, exc)
        return None


# ──────────────────────────────────────────────────────────────
# CLEANING
# ──────────────────────────────────────────────────────────────

def _coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def clean_sso_source(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise and validate sso_source DataFrame."""
    if df is None or df.empty:
        return pd.DataFrame()

    numeric_cols = [
        "semi_major_axis", "eccentricity", "inclination",
        "ascending_node_longitude", "perihelion_argument", "mean_anomaly",
        "perihelion_distance", "aphelion_distance", "orbital_period",
        "mean_motion", "tisserand_jupiter",
        "g_mag_abs_mean", "g_flux_mean", "g_flux_mean_error",
        "num_of_obs",
    ]
    df = _coerce_numeric(df, numeric_cols)

    # eccentricity must be [0, 1)
    df = df[(df["eccentricity"].isna()) | (df["eccentricity"].between(0, 0.99))]

    # inject friendly name column (canonical spelling)
    df["canonical_name"] = df["number_mp"].map(TARGET_ASTEROIDS).fillna(
        df.get("denomination", "Unknown")
    )

    # orbital classification (simplified Tisserand criterion)
    def classify(row):
        tj = row.get("tisserand_jupiter", np.nan)
        a  = row.get("semi_major_axis", np.nan)
        if pd.isna(tj) or pd.isna(a):
            return "Unknown"
        if tj > 3.0:
            return "Main-Belt"
        if 2.0 < tj <= 3.0:
            return "Jupiter-Family Comet"
        return "Halley-Type / Other"

    df["orbit_class"] = df.apply(classify, axis=1)

    log.info("  ✓ sso_source cleaned: %d records, %d columns", len(df), len(df.columns))
    return df.reset_index(drop=True)


def clean_sso_observation(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise and validate sso_observation DataFrame."""
    if df is None or df.empty:
        return pd.DataFrame()

    numeric_cols = [
        "ra", "dec", "ra_error", "dec_error",
        "g_mag", "g_flux", "g_flux_error",
        "solar_elongation", "phase_angle",
        "heliocentric_distance", "topocentric_distance",
        "x_gaia_geocentric", "y_gaia_geocentric", "z_gaia_geocentric",
        "vx_gaia_geocentric", "vy_gaia_geocentric", "vz_gaia_geocentric",
    ]
    df = _coerce_numeric(df, numeric_cols)

    # drop rows with no sky position
    df = df.dropna(subset=["ra", "dec"])

    # parse epoch
    if "epoch_utc" in df.columns:
        df["epoch_utc"] = pd.to_datetime(df["epoch_utc"], errors="coerce")

    df["canonical_name"] = df["number_mp"].map(TARGET_ASTEROIDS).fillna(
        df.get("denomination", "Unknown")
    )

    # signal-to-noise for brightness
    if "g_flux" in df.columns and "g_flux_error" in df.columns:
        df["g_snr"] = df["g_flux"] / df["g_flux_error"].replace(0, np.nan)

    log.info(
        "  ✓ sso_observation cleaned: %d records, %d columns", len(df), len(df.columns)
    )
    return df.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────
# FALLBACK — synthetic-but-realistic data
# ──────────────────────────────────────────────────────────────

def _generate_fallback_source() -> pd.DataFrame:
    """
    Generate physically consistent synthetic orbital elements when
    the Gaia TAP service is unreachable (e.g. offline / CI environment).
    Values are seeded from published MPC orbital solutions.
    """
    log.warning("Using FALLBACK synthetic data for sso_source.")
    rng = np.random.default_rng(42)
    rows = []
    # Reference semi-major axes (AU) from MPC for each object
    ref_a = {
        3095: 3.193, 2755: 2.367, 9936: 2.855, 90806: 2.444,
        10269: 3.129, 11156: 2.627, 2469: 2.248, 2746: 3.072,
        3013: 2.398, 3945: 3.461, 4208: 2.633, 4207: 2.418,
        4011: 2.386, 7164: 2.283, 3436: 2.774, 24533: 3.155,
    }
    for num, name in TARGET_ASTEROIDS.items():
        a   = ref_a.get(num, 2.5) + rng.normal(0, 0.01)
        ecc = abs(rng.normal(0.12, 0.05))
        inc = abs(rng.normal(8, 5))
        rows.append({
            "number_mp": num,
            "denomination": name,
            "canonical_name": name,
            "num_of_obs": int(rng.integers(50, 600)),
            "epoch_utc": "2016-01-01T00:00:00",
            "semi_major_axis": round(a, 4),
            "eccentricity": round(min(ecc, 0.95), 4),
            "inclination": round(inc, 4),
            "ascending_node_longitude": round(rng.uniform(0, 360), 4),
            "perihelion_argument": round(rng.uniform(0, 360), 4),
            "mean_anomaly": round(rng.uniform(0, 360), 4),
            "perihelion_distance": round(a * (1 - ecc), 4),
            "aphelion_distance": round(a * (1 + ecc), 4),
            "orbital_period": round(a ** 1.5, 4),
            "mean_motion": round(360 / (a ** 1.5), 6),
            "tisserand_jupiter": round(5.204 / a + 2 * np.sqrt(a / 5.204 * (1 - ecc**2)) * np.cos(np.radians(inc)), 4),
            "g_mag_abs_mean": round(rng.uniform(9, 16), 3),
            "g_flux_mean": round(abs(rng.normal(1e5, 2e4)), 2),
            "g_flux_mean_error": round(abs(rng.normal(500, 100)), 2),
            "orbit_class": "Main-Belt",
        })
    return pd.DataFrame(rows)


def _generate_fallback_observation() -> pd.DataFrame:
    """Generate synthetic per-transit photometry for fallback mode."""
    log.warning("Using FALLBACK synthetic data for sso_observation.")
    rng = np.random.default_rng(99)
    rows = []
    for num, name in TARGET_ASTEROIDS.items():
        n_obs = int(rng.integers(20, 150))
        base_epoch = pd.Timestamp("2014-07-25")
        for i in range(n_obs):
            epoch = base_epoch + pd.Timedelta(days=int(rng.integers(0, 1500)))
            r_hel = rng.uniform(1.8, 4.5)
            rows.append({
                "number_mp": num,
                "denomination": name,
                "canonical_name": name,
                "transit_id": f"{num}_{i:04d}",
                "epoch_utc": epoch,
                "epoch_err": rng.uniform(1e-5, 1e-4),
                "ra": rng.uniform(0, 360),
                "dec": rng.uniform(-90, 90),
                "ra_error": rng.uniform(0.1, 2.0),
                "dec_error": rng.uniform(0.1, 2.0),
                "g_mag": round(rng.uniform(14, 22), 3),
                "g_flux": round(abs(rng.normal(5e4, 1e4)), 2),
                "g_flux_error": round(abs(rng.normal(300, 80)), 2),
                "g_snr": round(rng.uniform(5, 200), 2),
                "solar_elongation": round(rng.uniform(60, 170), 3),
                "phase_angle": round(rng.uniform(0, 30), 3),
                "heliocentric_distance": round(r_hel, 5),
                "topocentric_distance": round(r_hel + rng.normal(0, 0.3), 5),
                "x_gaia_geocentric": round(rng.normal(0, 3), 5),
                "y_gaia_geocentric": round(rng.normal(0, 3), 5),
                "z_gaia_geocentric": round(rng.normal(0, 3), 5),
                "vx_gaia_geocentric": round(rng.normal(0, 20), 5),
                "vy_gaia_geocentric": round(rng.normal(0, 20), 5),
                "vz_gaia_geocentric": round(rng.normal(0, 20), 5),
            })
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────
# DATABASE LAYER
# ──────────────────────────────────────────────────────────────

DDL_SSO_SOURCE = """
CREATE OR REPLACE TABLE sso_source (
    number_mp                INTEGER,
    denomination             VARCHAR,
    canonical_name           VARCHAR,
    num_of_obs               INTEGER,
    epoch_utc                VARCHAR,
    semi_major_axis          DOUBLE,
    eccentricity             DOUBLE,
    inclination              DOUBLE,
    ascending_node_longitude DOUBLE,
    perihelion_argument      DOUBLE,
    mean_anomaly             DOUBLE,
    perihelion_distance      DOUBLE,
    aphelion_distance        DOUBLE,
    orbital_period           DOUBLE,
    mean_motion              DOUBLE,
    tisserand_jupiter        DOUBLE,
    g_mag_abs_mean           DOUBLE,
    g_flux_mean              DOUBLE,
    g_flux_mean_error        DOUBLE,
    orbit_class              VARCHAR
);
"""

DDL_SSO_OBSERVATION = """
CREATE OR REPLACE TABLE sso_observation (
    number_mp              INTEGER,
    denomination           VARCHAR,
    canonical_name         VARCHAR,
    transit_id             VARCHAR,
    epoch_utc              TIMESTAMP,
    epoch_err              DOUBLE,
    ra                     DOUBLE,
    dec                    DOUBLE,
    ra_error               DOUBLE,
    dec_error              DOUBLE,
    g_mag                  DOUBLE,
    g_flux                 DOUBLE,
    g_flux_error           DOUBLE,
    g_snr                  DOUBLE,
    solar_elongation       DOUBLE,
    phase_angle            DOUBLE,
    heliocentric_distance  DOUBLE,
    topocentric_distance   DOUBLE,
    x_gaia_geocentric      DOUBLE,
    y_gaia_geocentric      DOUBLE,
    z_gaia_geocentric      DOUBLE,
    vx_gaia_geocentric     DOUBLE,
    vy_gaia_geocentric     DOUBLE,
    vz_gaia_geocentric     DOUBLE
);
"""

DDL_CATALOG = """
CREATE OR REPLACE TABLE asteroid_catalog (
    number_mp     INTEGER PRIMARY KEY,
    canonical_name VARCHAR,
    notes          VARCHAR
);
"""


def init_db(con: duckdb.DuckDBPyConnection) -> None:
    """Create tables if they don't exist."""
    con.execute(DDL_SSO_SOURCE)
    con.execute(DDL_SSO_OBSERVATION)
    con.execute(DDL_CATALOG)
    # Populate static catalog
    rows = [(n, name, "") for n, name in TARGET_ASTEROIDS.items()]
    con.executemany(
        "INSERT OR REPLACE INTO asteroid_catalog VALUES (?, ?, ?)", rows
    )
    log.info("Database schema initialised.")


def load_to_db(
    con: duckdb.DuckDBPyConnection,
    df: pd.DataFrame,
    table: str,
) -> None:
    if df is None or df.empty:
        log.warning("Skipping empty DataFrame for table '%s'.", table)
        return
    # align columns to what the table expects
    existing = con.execute(f"DESCRIBE {table}").df()["column_name"].tolist()
    df = df[[c for c in existing if c in df.columns]]
    con.execute(f"DELETE FROM {table}")
    con.register("_tmp_df", df)
    con.execute(f"INSERT INTO {table} SELECT * FROM _tmp_df")
    con.unregister("_tmp_df")
    log.info("  ✓ Loaded %d rows → %s", len(df), table)


# ──────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ──────────────────────────────────────────────────────────────

def run_etl(use_real_data: bool = True) -> None:
    """
    Full ETL pipeline.

    Parameters
    ----------
    use_real_data : bool
        If True, attempts to query ESA Gaia TAP service.
        Falls back to synthetic data automatically on failure.
    """
    number_ids = list(TARGET_ASTEROIDS.keys())

    # ── EXTRACT ──────────────────────────────────────────────
    if use_real_data:
        df_source = fetch_from_gaia(
            _sso_source_query(number_ids), "sso_source"
        )
        time.sleep(1)  # polite delay between TAP queries
        df_obs = fetch_from_gaia(
            _sso_observation_query(number_ids), "sso_observation"
        )
    else:
        df_source = None
        df_obs = None

    # ── TRANSFORM ────────────────────────────────────────────
    if df_source is None or df_source.empty:
        df_source = _generate_fallback_source()
    else:
        df_source = clean_sso_source(df_source)

    if df_obs is None or df_obs.empty:
        df_obs = _generate_fallback_observation()
    else:
        df_obs = clean_sso_observation(df_obs)

    # cache CSVs for reproducibility / offline use
    df_source.to_csv(DATA_DIR / "sso_source.csv", index=False)
    df_obs.to_csv(DATA_DIR / "sso_observation.csv", index=False)
    log.info("Raw CSVs cached to %s/", DATA_DIR)

    # ── LOAD ─────────────────────────────────────────────────
    con = duckdb.connect(str(DB_PATH))
    init_db(con)
    load_to_db(con, df_source, "sso_source")
    load_to_db(con, df_obs, "sso_observation")
    con.close()
    log.info("ETL complete. Database: %s", DB_PATH.resolve())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gaia DR3 SSO ETL pipeline")
    parser.add_argument(
        "--no-real-data",
        action="store_true",
        help="Skip live Gaia TAP query; use synthetic fallback data.",
    )
    args = parser.parse_args()
    run_etl(use_real_data=not args.no_real_data)
