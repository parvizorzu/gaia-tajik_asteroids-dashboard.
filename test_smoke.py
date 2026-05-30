"""
tests/test_smoke.py
────────────────────────────────────────────────────────────────
Дымовые тесты (smoke tests) для Gaia DR3 Asteroid Dashboard.

Проверяют что:
  1. ETL-пайплайн запускается без ошибок (синтетический режим)
  2. Все SQL-вью возвращают данные
  3. Критические колонки присутствуют в датафреймах
  4. color_by-опции соответствуют реальным именам колонок v_phase_space
  5. Физические ограничения данных соблюдены

Запуск:
    pytest tests/ -v
"""

import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TEST_DB = ROOT / "_test_smoke.duckdb"


# ──────────────────────────────────────────────────────────────
# ФИКСТУРЫ
# ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_con():
    """Создаёт тестовую БД один раз на сессию, удаляет после."""
    TEST_DB.unlink(missing_ok=True)

    import data_loader as dl
    original = dl.DB_PATH
    dl.DB_PATH = TEST_DB
    try:
        dl.run_etl(use_real_data=False)
    finally:
        dl.DB_PATH = original

    from ddl import apply_schema
    con = duckdb.connect(str(TEST_DB))
    apply_schema(con)
    yield con
    con.close()
    TEST_DB.unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────
# 1. Импорты модулей
# ──────────────────────────────────────────────────────────────

def test_imports():
    import data_loader  # noqa: F401
    import ddl          # noqa: F401


# ──────────────────────────────────────────────────────────────
# 2. ETL — все 16 астероидов загружены
# ──────────────────────────────────────────────────────────────

def test_all_asteroids_present(db_con):
    from data_loader import TARGET_ASTEROIDS
    count = db_con.execute("SELECT COUNT(*) FROM sso_source").fetchone()[0]
    assert count == len(TARGET_ASTEROIDS) == 16


# ──────────────────────────────────────────────────────────────
# 3. Основные таблицы не пустые
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("table", [
    "sso_source", "sso_observation", "asteroid_catalog"
])
def test_tables_populated(db_con, table):
    n = db_con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    assert n > 0, f"Таблица {table} пустая"


# ──────────────────────────────────────────────────────────────
# 4. SQL-вью работают
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("view", [
    "v_orbital_summary",
    "v_phase_space",
    "v_lightcurve",
    "v_phase_curve",
    "v_sky_positions",
    "v_observation_stats",
])
def test_views_return_data(db_con, view):
    df = db_con.execute(f"SELECT * FROM {view} LIMIT 5").df()
    assert len(df) > 0, f"Вью {view} пустой"


# ──────────────────────────────────────────────────────────────
# 5. КРИТИЧЕСКИЙ — защита от регрессии бага color_by
#    Баг: selectbox передавал "inclination", но вью содержит "i_deg"
# ──────────────────────────────────────────────────────────────

def test_phase_space_color_by_columns_exist(db_con):
    """color_by ключи из сайдбара должны быть колонками v_phase_space."""
    COLOR_OPTIONS = {"orbit_class", "g_mag_abs_mean", "i_deg"}  # из app.py
    df = db_con.execute("SELECT * FROM v_phase_space LIMIT 1").df()
    missing = COLOR_OPTIONS - set(df.columns)
    assert not missing, (
        f"Колонки {missing} отсутствуют в v_phase_space.\n"
        f"Доступные: {sorted(df.columns)}\n"
        f"Подсказка: используй 'i_deg', а не 'inclination'."
    )


def test_inclination_column_name_in_phase_space(db_con):
    """'inclination' НЕ должна быть колонкой в v_phase_space — там 'i_deg'."""
    df = db_con.execute("SELECT * FROM v_phase_space LIMIT 1").df()
    assert "inclination" not in df.columns, (
        "v_phase_space содержит 'inclination' — проверь DDL вью"
    )
    assert "i_deg" in df.columns


# ──────────────────────────────────────────────────────────────
# 6. Обязательные колонки в ключевых вью
# ──────────────────────────────────────────────────────────────

def test_orbital_summary_columns(db_con):
    df = db_con.execute("SELECT * FROM v_orbital_summary LIMIT 1").df()
    required = {"number_mp", "canonical_name", "semi_major_axis",
                "eccentricity", "inclination", "orbital_period",
                "tisserand_jupiter", "transit_count"}
    assert not (required - set(df.columns))


def test_phase_space_columns(db_con):
    df = db_con.execute("SELECT * FROM v_phase_space LIMIT 1").df()
    required = {"a_au", "i_deg", "e", "tj", "orbit_class", "g_mag_abs_mean"}
    assert not (required - set(df.columns))


# ──────────────────────────────────────────────────────────────
# 7. Физические ограничения данных
# ──────────────────────────────────────────────────────────────

def test_eccentricity_range(db_con):
    bad = db_con.execute(
        "SELECT COUNT(*) FROM sso_source WHERE eccentricity < 0 OR eccentricity >= 1"
    ).fetchone()[0]
    assert bad == 0, f"{bad} строк с невалидным эксцентриситетом"


def test_semi_major_axis_positive(db_con):
    bad = db_con.execute(
        "SELECT COUNT(*) FROM sso_source WHERE semi_major_axis <= 0"
    ).fetchone()[0]
    assert bad == 0


def test_inclination_range(db_con):
    bad = db_con.execute(
        "SELECT COUNT(*) FROM sso_source WHERE inclination < 0 OR inclination > 180"
    ).fetchone()[0]
    assert bad == 0


# ──────────────────────────────────────────────────────────────
# 8. Синтетические данные корректны
# ──────────────────────────────────────────────────────────────

def test_fallback_source():
    from data_loader import _generate_fallback_source, TARGET_ASTEROIDS
    df = _generate_fallback_source()
    assert len(df) == len(TARGET_ASTEROIDS)
    assert (df["eccentricity"].between(0, 1)).all()
    assert (df["semi_major_axis"] > 0).all()


def test_fallback_observation():
    from data_loader import _generate_fallback_observation
    df = _generate_fallback_observation()
    assert len(df) > 0
    assert df["ra"].between(0, 360).all()
    assert df["dec"].between(-90, 90).all()


# ──────────────────────────────────────────────────────────────
# 9. DDL идемпотентна
# ──────────────────────────────────────────────────────────────

def test_schema_idempotent(db_con):
    from ddl import apply_schema
    apply_schema(db_con)  # второй вызов не должен падать
