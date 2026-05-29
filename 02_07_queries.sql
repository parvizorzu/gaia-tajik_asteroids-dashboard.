-- queries/02_phase_space.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Semi-major axis vs inclination for the phase-space scatter plot.
-- Each point is one of our 16 target asteroids.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    number_mp,
    canonical_name,
    semi_major_axis    AS a_au,
    inclination        AS i_deg,
    eccentricity       AS e,
    tisserand_jupiter  AS T_J,
    g_mag_abs_mean     AS H,
    orbit_class,
    -- Approximate velocity dispersion proxy: e * sin(i)
    eccentricity * SIN(RADIANS(inclination)) AS e_sin_i
FROM v_phase_space
ORDER BY semi_major_axis;


-- queries/03_lightcurve.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Time-series G-band photometry for a single asteroid.
-- :asteroid_id is substituted at query time by the dashboard.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    epoch_utc,
    g_mag,
    g_flux,
    g_flux_error,
    g_snr,
    heliocentric_distance,
    phase_angle
FROM v_lightcurve
WHERE number_mp = :asteroid_id
ORDER BY epoch_utc;


-- queries/04_phase_curve.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Reduced magnitude vs phase angle (H-G phase function input).
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    phase_angle,
    g_reduced_mag,
    r_hel,
    delta,
    epoch_utc
FROM v_phase_curve
WHERE number_mp = :asteroid_id
ORDER BY phase_angle;


-- queries/05_observation_stats.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Summary statistics table shown in the "Observations" tab.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    canonical_name,
    n_transits,
    first_obs,
    last_obs,
    ROUND(avg_snr, 1)              AS avg_snr,
    ROUND(g_mag_stddev, 4)         AS g_mag_variability,
    ROUND(avg_ra_error_mas, 3)     AS ra_err_mas,
    ROUND(avg_dec_error_mas, 3)    AS dec_err_mas,
    ROUND(avg_solar_elong, 1)      AS avg_solar_elong_deg
FROM v_observation_stats
ORDER BY n_transits DESC;


-- queries/06_sky_positions.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Latest known RA/Dec for all targets (finder-chart data).
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    number_mp,
    canonical_name,
    epoch_utc          AS last_seen,
    ra,
    dec,
    g_mag,
    heliocentric_distance AS r_hel,
    solar_elongation
FROM v_sky_positions
ORDER BY canonical_name;


-- queries/07_comparison_belt.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Distribution of our 16 targets across main-belt zones
-- compared to expected background fractions.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    belt_zone,
    COUNT(*)                              AS n_targets,
    ROUND(AVG(a_au), 3)                   AS mean_a,
    ROUND(AVG(e), 4)                      AS mean_e,
    ROUND(AVG(i_deg), 2)                  AS mean_i,
    ROUND(AVG(H_G), 2)                    AS mean_H
FROM (
    SELECT
        canonical_name,
        semi_major_axis  AS a_au,
        eccentricity     AS e,
        inclination      AS i_deg,
        g_mag_abs_mean   AS H_G,
        CASE
            WHEN semi_major_axis < 2.5              THEN 'Inner Belt'
            WHEN semi_major_axis BETWEEN 2.5 AND 2.82 THEN 'Middle Belt'
            ELSE 'Outer Belt'
        END AS belt_zone
    FROM sso_source
) sub
GROUP BY belt_zone
ORDER BY mean_a;
