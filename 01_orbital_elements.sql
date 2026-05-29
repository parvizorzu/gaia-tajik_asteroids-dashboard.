-- queries/01_orbital_elements.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Full orbital elements for all 16 target asteroids, with derived columns.
-- Used by the "Orbital Parameters" tab of the dashboard.
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    number_mp,
    canonical_name,
    semi_major_axis                                                AS a_au,
    eccentricity                                                   AS e,
    inclination                                                    AS i_deg,
    ascending_node_longitude                                       AS omega_deg,
    perihelion_argument                                            AS w_deg,
    mean_anomaly                                                   AS M_deg,
    perihelion_distance                                            AS q_au,
    aphelion_distance                                              AS Q_au,
    orbital_period                                                 AS P_yr,
    mean_motion                                                    AS n_deg_day,
    tisserand_jupiter                                              AS T_J,
    g_mag_abs_mean                                                 AS H_G,
    orbit_class,
    num_of_obs,
    -- Belt zone classification by semi-major axis
    CASE
        WHEN semi_major_axis < 2.0              THEN 'Inner Belt (a < 2.0 AU)'
        WHEN semi_major_axis BETWEEN 2.0 AND 2.5 THEN 'Inner Belt (2.0–2.5 AU)'
        WHEN semi_major_axis BETWEEN 2.5 AND 2.82 THEN 'Middle Belt (2.5–2.82 AU)'
        WHEN semi_major_axis BETWEEN 2.82 AND 3.28 THEN 'Outer Belt (2.82–3.28 AU)'
        WHEN semi_major_axis > 3.28             THEN 'Outer Belt / Hilda region'
        ELSE 'Unknown'
    END                                                            AS belt_zone
FROM sso_source
ORDER BY semi_major_axis;
