"""
ddl.py — DuckDB schema definitions and analytical views
for the Gaia DR3 SSO Asteroid Dashboard.

Run directly to (re)initialise the database:
    python ddl.py [--db path/to/file.duckdb]
"""

import argparse
import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

DEFAULT_DB = Path("gaia_asteroids.duckdb")

# ──────────────────────────────────────────────────────────────
# CORE TABLES  (also defined in data_loader.py — kept in sync)
# ──────────────────────────────────────────────────────────────

TABLES = {
    "asteroid_catalog": """
        CREATE TABLE IF NOT EXISTS asteroid_catalog (
            number_mp      INTEGER PRIMARY KEY,
            canonical_name VARCHAR NOT NULL,
            notes          VARCHAR DEFAULT ''
        );
    """,

    "sso_source": """
        CREATE TABLE IF NOT EXISTS sso_source (
            number_mp                INTEGER,
            denomination             VARCHAR,
            canonical_name           VARCHAR,
            num_of_obs               INTEGER,
            epoch_utc                VARCHAR,
            semi_major_axis          DOUBLE,   -- AU
            eccentricity             DOUBLE,   -- dimensionless
            inclination              DOUBLE,   -- degrees
            ascending_node_longitude DOUBLE,   -- degrees
            perihelion_argument      DOUBLE,   -- degrees
            mean_anomaly             DOUBLE,   -- degrees
            perihelion_distance      DOUBLE,   -- AU
            aphelion_distance        DOUBLE,   -- AU
            orbital_period           DOUBLE,   -- years
            mean_motion              DOUBLE,   -- deg/day
            tisserand_jupiter        DOUBLE,   -- dimensionless
            g_mag_abs_mean           DOUBLE,   -- Gaia G band absolute mag
            g_flux_mean              DOUBLE,   -- e-/s
            g_flux_mean_error        DOUBLE,
            orbit_class              VARCHAR
        );
    """,

    "sso_observation": """
        CREATE TABLE IF NOT EXISTS sso_observation (
            number_mp              INTEGER,
            denomination           VARCHAR,
            canonical_name         VARCHAR,
            transit_id             VARCHAR,
            epoch_utc              TIMESTAMP,
            epoch_err              DOUBLE,
            ra                     DOUBLE,   -- degrees
            dec                    DOUBLE,   -- degrees
            ra_error               DOUBLE,   -- mas
            dec_error              DOUBLE,   -- mas
            g_mag                  DOUBLE,
            g_flux                 DOUBLE,
            g_flux_error           DOUBLE,
            g_snr                  DOUBLE,
            solar_elongation       DOUBLE,   -- degrees
            phase_angle            DOUBLE,   -- degrees
            heliocentric_distance  DOUBLE,   -- AU
            topocentric_distance   DOUBLE,   -- AU
            x_gaia_geocentric      DOUBLE,   -- AU
            y_gaia_geocentric      DOUBLE,
            z_gaia_geocentric      DOUBLE,
            vx_gaia_geocentric     DOUBLE,   -- AU/day
            vy_gaia_geocentric     DOUBLE,
            vz_gaia_geocentric     DOUBLE
        );
    """,
}

# ──────────────────────────────────────────────────────────────
# ANALYTICAL VIEWS
# ──────────────────────────────────────────────────────────────

VIEWS = {

    "v_orbital_summary": """
        -- One row per asteroid: orbital elements + observation stats
        CREATE OR REPLACE VIEW v_orbital_summary AS
        SELECT
            s.number_mp,
            s.canonical_name,
            s.num_of_obs,
            s.semi_major_axis,
            s.eccentricity,
            s.inclination,
            s.ascending_node_longitude,
            s.perihelion_argument,
            s.mean_anomaly,
            s.perihelion_distance,
            s.aphelion_distance,
            s.orbital_period,
            s.mean_motion,
            s.tisserand_jupiter,
            s.g_mag_abs_mean,
            s.orbit_class,
            COUNT(o.transit_id)                          AS transit_count,
            MIN(o.g_mag)                                 AS g_mag_min,
            MAX(o.g_mag)                                 AS g_mag_max,
            AVG(o.g_mag)                                 AS g_mag_mean,
            AVG(o.heliocentric_distance)                 AS r_hel_mean,
            AVG(o.phase_angle)                           AS phase_angle_mean
        FROM sso_source s
        LEFT JOIN sso_observation o USING (number_mp)
        GROUP BY ALL
        ORDER BY s.number_mp
    """,

    "v_phase_curve": """
        -- Reduced magnitude vs phase angle per transit (for H-G fitting)
        CREATE OR REPLACE VIEW v_phase_curve AS
        SELECT
            o.number_mp,
            o.canonical_name,
            o.transit_id,
            o.epoch_utc,
            o.phase_angle,
            o.heliocentric_distance                             AS r_hel,
            o.topocentric_distance                              AS delta,
            -- Reduced magnitude: removes distance effects
            o.g_mag - 5 * LOG10(o.heliocentric_distance * o.topocentric_distance) AS g_reduced_mag
        FROM sso_observation o
        WHERE o.phase_angle IS NOT NULL
          AND o.heliocentric_distance > 0
          AND o.topocentric_distance  > 0
        ORDER BY o.number_mp, o.phase_angle
    """,

    "v_sky_positions": """
        -- Most recent sky position per asteroid (for finder chart)
        CREATE OR REPLACE VIEW v_sky_positions AS
        SELECT DISTINCT ON (number_mp)
            number_mp,
            canonical_name,
            epoch_utc,
            ra,
            dec,
            g_mag,
            heliocentric_distance,
            solar_elongation
        FROM sso_observation
        WHERE ra IS NOT NULL AND dec IS NOT NULL
        ORDER BY number_mp, epoch_utc DESC
    """,

    "v_lightcurve": """
        -- Time-series brightness per asteroid
        CREATE OR REPLACE VIEW v_lightcurve AS
        SELECT
            number_mp,
            canonical_name,
            epoch_utc,
            g_mag,
            g_flux,
            g_flux_error,
            g_snr,
            heliocentric_distance,
            phase_angle
        FROM sso_observation
        WHERE g_mag IS NOT NULL
        ORDER BY number_mp, epoch_utc
    """,

    "v_phase_space": """
        -- Semi-major axis vs inclination scatter (Phase Space plot)
        CREATE OR REPLACE VIEW v_phase_space AS
        SELECT
            number_mp,
            canonical_name,
            semi_major_axis                 AS a_au,
            eccentricity                    AS e,
            inclination                     AS i_deg,
            tisserand_jupiter               AS tj,
            orbit_class,
            g_mag_abs_mean,
            -- Derived: Hill sphere radius (approximate, in AU)
            semi_major_axis * POWER(eccentricity / 3.0, 1.0/3.0) AS r_hill_approx
        FROM sso_source
        WHERE semi_major_axis IS NOT NULL
          AND inclination      IS NOT NULL
        ORDER BY semi_major_axis
    """,

    "v_observation_stats": """
        -- Per-asteroid observation quality metrics
        CREATE OR REPLACE VIEW v_observation_stats AS
        SELECT
            number_mp,
            canonical_name,
            COUNT(*)                         AS n_transits,
            MIN(epoch_utc)                   AS first_obs,
            MAX(epoch_utc)                   AS last_obs,
            AVG(g_snr)                       AS avg_snr,
            STDDEV(g_mag)                    AS g_mag_stddev,
            AVG(ra_error)                    AS avg_ra_error_mas,
            AVG(dec_error)                   AS avg_dec_error_mas,
            AVG(solar_elongation)            AS avg_solar_elong
        FROM sso_observation
        GROUP BY number_mp, canonical_name
        ORDER BY n_transits DESC
    """,
}

# ──────────────────────────────────────────────────────────────
# INDEXES
# ──────────────────────────────────────────────────────────────

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_src_num  ON sso_source(number_mp)",
    "CREATE INDEX IF NOT EXISTS idx_obs_num  ON sso_observation(number_mp)",
    "CREATE INDEX IF NOT EXISTS idx_obs_name ON sso_observation(canonical_name)",
    "CREATE INDEX IF NOT EXISTS idx_obs_ep   ON sso_observation(epoch_utc)",
]


# ──────────────────────────────────────────────────────────────
# PUBLIC API
# ──────────────────────────────────────────────────────────────

def apply_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create all tables, views and indexes on an open connection."""
    for name, ddl in TABLES.items():
        con.execute(ddl)
        log.info("  ✓ table  %s", name)

    for name, ddl in VIEWS.items():
        con.execute(ddl)
        log.info("  ✓ view   %s", name)

    for ddl in INDEXES:
        con.execute(ddl)

    log.info("Schema applied successfully.")


def get_connection(db_path: Path = DEFAULT_DB) -> duckdb.DuckDBPyConnection:
    """Return an open DuckDB connection with schema guaranteed."""
    con = duckdb.connect(str(db_path))
    apply_schema(con)
    return con


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialise Gaia SSO DuckDB schema")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="DuckDB file path")
    args = parser.parse_args()
    con = duckdb.connect(args.db)
    apply_schema(con)
    con.close()
    print(f"Schema ready: {args.db}")
