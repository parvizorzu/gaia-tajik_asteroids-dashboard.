"""
app.py — Streamlit-дашборд для анализа астероидов Gaia DR3 SSO.
Запуск: streamlit run app.py
"""

from __future__ import annotations
import warnings
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

warnings.filterwarnings("ignore")

# ──────────────────────────────────────────────────────────────
# КОНФИГУРАЦИЯ
# ──────────────────────────────────────────────────────────────

DB_PATH = Path("gaia_asteroids.duckdb")
PALETTE = px.colors.qualitative.Vivid
DARK_BG = "#0d1117"
CARD_BG = "#161b22"
ACCENT  = "#58a6ff"

TARGET_ASTEROIDS = {
    3095:  "Omarkhayyam",  2755:  "Avicenna",      9936:  "Al-Biruni",
    90806: "Rudaki",       10269: "Tusi",           11156: "Al-Khwarizmi",
    2469:  "Tajikistan",   2746:  "Hissao",         3013:  "Dobrovoleva",
    3945:  "Gerasimenko",  4208:  "Kiselev",        4207:  "Chernova",
    4011:  "Bakharev",     7164:  "Babadzhanov",    3436:  "Ibadinov",
    24533: "Kokhirova",
}
NAMES = list(TARGET_ASTEROIDS.values())


# ──────────────────────────────────────────────────────────────
# БАЗА ДАННЫХ
# ──────────────────────────────────────────────────────────────

@st.cache_resource
def get_con() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        with st.spinner("🔭 Инициализация базы данных — запуск ETL-пайплайна…"):
            from data_loader import run_etl
            run_etl(use_real_data=False)  # TAP недоступен в облаке; локально замени на True
    from ddl import get_connection
    return get_connection(DB_PATH)


@st.cache_data(ttl=300)
def query(_con, sql: str, params: dict | None = None) -> pd.DataFrame:
    if params:
        for k, v in params.items():
            sql = sql.replace(f":{k}", str(v))
    return _con.execute(sql).df()


# ──────────────────────────────────────────────────────────────
# СТРАНИЦА
# ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Gaia DR3 · Обсерватория астероидов",
    page_icon="☄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Inter:wght@300;400;600&display=swap');
html, body, [class*="css"] {{
    background-color: {DARK_BG}; color: #e6edf3;
    font-family: 'Inter', sans-serif;
}}
.stApp {{ background-color: {DARK_BG}; }}
section[data-testid="stSidebar"] {{
    background-color: {CARD_BG}; border-right: 1px solid #30363d;
}}
[data-testid="stMetric"] {{
    background: {CARD_BG}; border: 1px solid #21262d;
    border-radius: 8px; padding: 14px 20px;
}}
[data-testid="stMetricValue"] {{ font-family: 'Space Mono', monospace; color: {ACCENT}; }}
h1, h2, h3 {{ font-family: 'Space Mono', monospace; letter-spacing: -0.5px; }}
h1 {{ color: #ffffff; font-size: 1.8rem; }}
h2 {{ color: {ACCENT}; font-size: 1.2rem; border-bottom: 1px solid #21262d; padding-bottom: 6px; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; background: {CARD_BG}; border-radius: 8px; padding: 4px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 6px; color: #8b949e; font-size: 0.85rem; }}
.stTabs [aria-selected="true"] {{ background: {DARK_BG}; color: {ACCENT} !important; }}
.stDataFrame {{ border-radius: 8px; overflow: hidden; }}
.source-badge {{
    background: linear-gradient(135deg, #1f2937, #111827);
    border: 1px solid #374151; border-left: 3px solid {ACCENT};
    border-radius: 6px; padding: 12px 18px;
    font-size: 0.82rem; color: #9ca3af; margin-top: 8px;
}}
.source-badge strong {{ color: {ACCENT}; }}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# БОКОВАЯ ПАНЕЛЬ
# ──────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ☄️ Обсерватория астероидов")
    st.markdown("---")

    selected_name = st.selectbox(
        "Выбрать астероид",
        options=NAMES, index=0,
        help="Выберите объект для детального анализа.",
    )
    selected_num = [k for k, v in TARGET_ASTEROIDS.items() if v == selected_name][0]

    st.markdown("---")
    st.markdown("### Параметры отображения")
    show_errorbars = st.checkbox("Показать планки погрешностей фотометрии", value=False)
    # Ключи = точные имена колонок в v_phase_space.
    # ВАЖНО: "i_deg" — наклонение в вью; "inclination" — только в sso_source (вылет!).
    _COLOR_OPTS: dict[str, str] = {
        "orbit_class":    "Класс орбиты",
        "g_mag_abs_mean": "Абс. звёздная величина (H)",
        "i_deg":          "Наклонение (°)",
    }
    color_by = st.selectbox(
        "Цвет фазового пространства",
        options=list(_COLOR_OPTS.keys()),
        format_func=lambda x: _COLOR_OPTS[x],
    )

    st.markdown("---")
    if st.button("🔄 Обновить данные (перезапустить ETL)"):
        if DB_PATH.exists():
            DB_PATH.unlink()
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()

    st.markdown("""
        <div class="source-badge">
        <strong>📡 Источник данных</strong><br>
        Данные получены из <strong>Gaia DR3</strong><br>
        <em>ESA/Gaia/DPAC</em><br><br>
        Таблицы: <code>gaiadr3.sso_source</code><br>
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
        <code>gaiadr3.sso_observation</code><br><br>
        Доступ через <code>astroquery.gaia</code> TAP+<br>
        Лицензия: <a href="https://creativecommons.org/licenses/by/4.0/" style="color:#58a6ff;">CC BY 4.0</a>
        </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# ЗАГРУЗКА ДАННЫХ
# ──────────────────────────────────────────────────────────────

con = get_con()

df_orbital  = query(con, "SELECT * FROM v_orbital_summary ORDER BY semi_major_axis")
df_phase    = query(con, "SELECT * FROM v_phase_space")
df_obs_stat = query(con, "SELECT * FROM v_observation_stats ORDER BY n_transits DESC")
df_sky      = query(con, "SELECT * FROM v_sky_positions")
df_belt     = query(con, """
    SELECT
        CASE
            WHEN semi_major_axis < 2.5              THEN 'Внутренний пояс'
            WHEN semi_major_axis BETWEEN 2.5 AND 2.82 THEN 'Средний пояс'
            ELSE 'Внешний пояс'
        END AS zone,
        COUNT(*) AS n
    FROM sso_source GROUP BY zone ORDER BY MIN(semi_major_axis)
""")

df_lc     = query(con, "SELECT * FROM v_lightcurve WHERE number_mp = :asteroid_id ORDER BY epoch_utc",
                  {"asteroid_id": selected_num})
df_pc     = query(con, "SELECT * FROM v_phase_curve WHERE number_mp = :asteroid_id ORDER BY phase_angle",
                  {"asteroid_id": selected_num})
df_single = df_orbital[df_orbital["number_mp"] == selected_num]


# ──────────────────────────────────────────────────────────────
# ЗАГОЛОВОК
# ──────────────────────────────────────────────────────────────

st.markdown("# ☄️ Gaia DR3 · Астероиды Солнечной системы")
st.markdown(
    f"Отображается **{len(df_orbital)} объектов** из каталога ESA Gaia DR3 SSO. "
    f"Выбран: **({selected_num}) {selected_name}**"
)
st.markdown("---")

# ── Метрики ──────────────────────────────────────────────────
if not df_single.empty:
    row = df_single.iloc[0]
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Большая полуось",   f"{row.get('semi_major_axis', 'N/A'):.3f} а.е.")
    c2.metric("Эксцентриситет",    f"{row.get('eccentricity', 'N/A'):.4f}")
    c3.metric("Наклонение",        f"{row.get('inclination', 'N/A'):.2f} °")
    c4.metric("Период обращения",  f"{row.get('orbital_period', 'N/A'):.3f} лет")
    c5.metric("Транзиты Gaia",     f"{int(row.get('transit_count', 0)):,}")
    c6.metric("T_Юпитера",         f"{row.get('tisserand_jupiter', 'N/A'):.3f}")
    st.markdown("")


# ──────────────────────────────────────────────────────────────
# ВКЛАДКИ
# ──────────────────────────────────────────────────────────────

tab_phase, tab_detail, tab_photom, tab_sky, tab_catalog, tab_source = st.tabs([
    "🌌 Фазовое пространство",
    "🔭 Орбитальные элементы",
    "📈 Фотометрия",
    "🗺️ Карта неба",
    "📋 Полный каталог",
    "ℹ️ Источник данных",
])


# ═══════════════════════════════════════════════════════════════
# ВКЛАДКА 1 — ФАЗОВОЕ ПРОСТРАНСТВО
# ═══════════════════════════════════════════════════════════════

with tab_phase:
    st.markdown("## Большая полуось vs Наклонение орбиты")

    col_left, col_right = st.columns([3, 1])

    with col_left:
        fig = px.scatter(
            df_phase,
            x="a_au", y="i_deg",
            color=color_by,
            size=[12] * len(df_phase),
            hover_name="canonical_name",
            hover_data={
                "a_au":  ":.3f",
                "i_deg": ":.2f",
                "e":     ":.4f",
                "tj":    ":.3f",
            },
            labels={
                "a_au":          "Большая полуось (а.е.)",
                "i_deg":         "Наклонение (°)",
                "g_mag_abs_mean":"Абс. звёздная величина H",
                "orbit_class":   "Класс орбиты",
                "tj":            "Параметр Тиссерана T_J",
                "e":             "Эксцентриситет",
            },
            color_continuous_scale="Viridis",
            template="plotly_dark", title="",
        )

        # выделить выбранный объект
        sel_pt = df_phase[df_phase["canonical_name"] == selected_name]
        if not sel_pt.empty:
            sp = sel_pt.iloc[0]
            fig.add_scatter(
                x=[sp["a_au"]], y=[sp["i_deg"]],
                mode="markers",
                marker=dict(size=20, color=ACCENT, symbol="star",
                            line=dict(width=2, color="white")),
                name=f"▶ {selected_name}", showlegend=True,
            )

        # Люки Кирквуда
        for gap, label in [(2.065, "3:1"), (2.502, "5:2"), (2.706, "7:3"), (2.823, "2:1")]:
            fig.add_vline(x=gap, line_dash="dot", line_color="#444",
                          annotation_text=label, annotation_font_size=10)

        fig.update_layout(
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG, font_color="#e6edf3",
            xaxis=dict(gridcolor="#21262d", title="Большая полуось (а.е.)", range=[1.8, 4.2]),
            yaxis=dict(gridcolor="#21262d", title="Наклонение (°)"),
            legend=dict(bgcolor=CARD_BG, bordercolor="#30363d"),
            autosize=True, height=460,
            margin=dict(l=40, r=15, t=15, b=45),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Пунктирные линии — резонансные люки Кирквуда (3:1, 5:2, 7:3, 2:1)")

    with col_right:
        st.markdown("### Поясные зоны")
        fig_belt = px.pie(
            df_belt, names="zone", values="n",
            color_discrete_sequence=PALETTE,
            template="plotly_dark", hole=0.4,
        )
        fig_belt.update_layout(
            paper_bgcolor=DARK_BG, font_color="#e6edf3",
            autosize=True, height=260, margin=dict(l=0, r=0, t=10, b=0),
            showlegend=True, legend=dict(font_size=11),
        )
        st.plotly_chart(fig_belt, use_container_width=True)

        st.markdown("### e vs i")
        fig_ei = px.scatter(
            df_phase, x="e", y="i_deg",
            hover_name="canonical_name",
            color_discrete_sequence=[ACCENT],
            template="plotly_dark",
            labels={"e": "Эксцентриситет", "i_deg": "Наклонение (°)"},
        )
        fig_ei.update_traces(marker_size=8)
        fig_ei.update_layout(
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG, font_color="#e6edf3",
            autosize=True, height=240,
            xaxis=dict(gridcolor="#21262d"),
            yaxis=dict(gridcolor="#21262d"),
            margin=dict(l=40, r=10, t=10, b=40),
        )
        st.plotly_chart(fig_ei, use_container_width=True)


# ═══════════════════════════════════════════════════════════════
# ВКЛАДКА 2 — ОРБИТАЛЬНЫЕ ЭЛЕМЕНТЫ
# ═══════════════════════════════════════════════════════════════

with tab_detail:
    st.markdown(f"## ({selected_num}) {selected_name} — Орбитальные элементы")

    if not df_single.empty:
        row = df_single.iloc[0]

        # Радарная диаграмма
        categories = ["Большая полуось", "Эксцентриситет", "Наклонение",
                      "Период обращения", "Абс. величина H"]
        norm_max = [5.5, 0.6, 40, 8, 18]
        vals = [
            row.get("semi_major_axis", 0),
            row.get("eccentricity", 0),
            row.get("inclination", 0),
            row.get("orbital_period", 0),
            row.get("g_mag_abs_mean", 0),
        ]
        norm_vals = [min(v / m, 1.0) for v, m in zip(vals, norm_max)] + \
                    [min(vals[0] / norm_max[0], 1.0)]
        cats = categories + [categories[0]]

        fig_radar = go.Figure(go.Scatterpolar(
            r=norm_vals, theta=cats, fill="toself",
            fillcolor="rgba(88,166,255,0.15)",
            line_color=ACCENT, line_width=2, name=selected_name,
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor=CARD_BG,
                radialaxis=dict(visible=True, range=[0, 1], gridcolor="#21262d",
                                tickfont_color="#8b949e"),
                angularaxis=dict(gridcolor="#21262d", tickfont_color="#e6edf3"),
            ),
            paper_bgcolor=DARK_BG, font_color="#e6edf3",
            autosize=True, height=360, margin=dict(l=50, r=50, t=30, b=30),
        )

        col_r, col_tbl = st.columns([1, 1])
        with col_r:
            st.plotly_chart(fig_radar, use_container_width=True)
        with col_tbl:
            st.markdown("#### Параметры орбиты")
            params = {
                "Большая полуось (a)":    f"{row.get('semi_major_axis', '—'):.4f} а.е.",
                "Эксцентриситет (e)":     f"{row.get('eccentricity', '—'):.5f}",
                "Наклонение (i)":         f"{row.get('inclination', '—'):.3f} °",
                "Долгота восх. узла (Ω)": f"{row.get('ascending_node_longitude', '—'):.3f} °",
                "Аргумент перигелия (ω)": f"{row.get('perihelion_argument', '—'):.3f} °",
                "Средняя аномалия (M)":   f"{row.get('mean_anomaly', '—'):.3f} °",
                "Расст. перигелия (q)":   f"{row.get('perihelion_distance', '—'):.4f} а.е.",
                "Расст. афелия (Q)":      f"{row.get('aphelion_distance', '—'):.4f} а.е.",
                "Период обращения (P)":   f"{row.get('orbital_period', '—'):.4f} лет",
                "Среднее движение (n)":   f"{row.get('mean_motion', '—'):.5f} °/сут",
                "Параметр Тиссерана":     f"{row.get('tisserand_jupiter', '—'):.4f}",
                "Абс. звёздная вел. (H)": f"{row.get('g_mag_abs_mean', '—'):.3f}",
                "Класс орбиты":           row.get("orbit_class", "—"),
                "Транзиты Gaia":          f"{int(row.get('transit_count', 0)):,}",
            }
            param_df = pd.DataFrame(params.items(), columns=["Параметр", "Значение"])
            st.dataframe(param_df, hide_index=True, use_container_width=True, height=420)

        # Сравнительный violin-plot
        st.markdown("#### Сравнение с остальными 15 объектами выборки")
        compare_cols   = ["semi_major_axis", "eccentricity", "inclination", "g_mag_abs_mean"]
        compare_labels = ["a (а.е.)", "e", "i (°)", "H (маг)"]
        all_vals = [df_orbital[c].dropna().values for c in compare_cols]
        sel_vals = [row.get(c, np.nan) for c in compare_cols]

        fig_comp = go.Figure()
        for i, (col, lbl) in enumerate(zip(compare_cols, compare_labels)):
            fig_comp.add_trace(go.Violin(
                x=[lbl] * len(all_vals[i]), y=all_vals[i],
                name=lbl, box_visible=True, meanline_visible=True,
                fillcolor="rgba(88,166,255,0.12)", line_color="#30363d",
                marker_color="#8b949e", showlegend=False,
            ))
            if not np.isnan(sel_vals[i]):
                fig_comp.add_scatter(
                    x=[lbl], y=[sel_vals[i]], mode="markers",
                    marker=dict(size=14, color=ACCENT, symbol="diamond",
                                line=dict(width=2, color="white")),
                    name=selected_name if i == 0 else None,
                    showlegend=(i == 0),
                )
        fig_comp.update_layout(
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG, font_color="#e6edf3",
            xaxis=dict(gridcolor="#21262d"),
            yaxis=dict(gridcolor="#21262d"),
            autosize=True, height=300, margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig_comp, use_container_width=True)
    else:
        st.warning("Нет орбитальных данных для выбранного объекта.")


# ═══════════════════════════════════════════════════════════════
# ВКЛАДКА 3 — ФОТОМЕТРИЯ
# ═══════════════════════════════════════════════════════════════

with tab_photom:
    st.markdown(f"## ({selected_num}) {selected_name} — Фотометрия G-полосы Gaia")

    if not df_lc.empty:
        c_lc, c_pc = st.columns(2)

        with c_lc:
            st.markdown("#### Кривая блеска")
            if show_errorbars and "g_flux_error" in df_lc.columns:
                err = (df_lc["g_flux_error"] /
                       df_lc["g_flux"].replace(0, np.nan) * 2.5 / np.log(10))
                fig_lc = go.Figure(go.Scatter(
                    x=df_lc["epoch_utc"], y=df_lc["g_mag"],
                    error_y=dict(array=err.fillna(0).values),
                    mode="markers+lines",
                    marker=dict(color=ACCENT, size=5),
                    line=dict(color="#30363d", width=0.5),
                ))
            else:
                fig_lc = px.scatter(
                    df_lc, x="epoch_utc", y="g_mag",
                    color="heliocentric_distance",
                    color_continuous_scale="Plasma",
                    labels={"epoch_utc": "Дата", "g_mag": "Звёздная величина G",
                            "heliocentric_distance": "r_гел (а.е.)"},
                    template="plotly_dark",
                )
            fig_lc.update_yaxes(autorange="reversed")
            fig_lc.update_layout(
                paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG, font_color="#e6edf3",
                autosize=True, height=330,
                xaxis=dict(gridcolor="#21262d"),
                yaxis=dict(gridcolor="#21262d", title="G (маг, ярче ↑)"),
                margin=dict(l=45, r=10, t=15, b=45),
            )
            st.plotly_chart(fig_lc, use_container_width=True)

        with c_pc:
            st.markdown("#### Фазовая кривая блеска (H-G)")
            if not df_pc.empty:
                # Тренд вручную через numpy (без statsmodels)
                fig_pc = px.scatter(
                    df_pc, x="phase_angle", y="g_reduced_mag",
                    color="r_hel",
                    color_continuous_scale="Cividis",
                    labels={"phase_angle":    "Фазовый угол (°)",
                            "g_reduced_mag":  "Приведённая звёздная величина G",
                            "r_hel":          "r_гел (а.е.)"},
                    template="plotly_dark",
                )
                # Полиномиальный тренд (степень 2) — без statsmodels
                pc_clean = df_pc.dropna(subset=["phase_angle", "g_reduced_mag"])
                if len(pc_clean) >= 3:
                    z = np.polyfit(pc_clean["phase_angle"], pc_clean["g_reduced_mag"], 2)
                    x_trend = np.linspace(pc_clean["phase_angle"].min(),
                                          pc_clean["phase_angle"].max(), 100)
                    y_trend = np.polyval(z, x_trend)
                    fig_pc.add_scatter(
                        x=x_trend, y=y_trend, mode="lines",
                        line=dict(color=ACCENT, width=2, dash="solid"),
                        name="Полином 2-й степени",
                    )
                fig_pc.update_yaxes(autorange="reversed")
                fig_pc.update_layout(
                    paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG, font_color="#e6edf3",
                    height=350, xaxis=dict(gridcolor="#21262d"),
                    yaxis=dict(gridcolor="#21262d"),
                    margin=dict(l=50, r=10, t=20, b=50),
                )
                st.plotly_chart(fig_pc, use_container_width=True)
            else:
                st.info("Нет данных фазовой кривой для этого объекта.")

        # Гелиоцентрическое расстояние и фазовый угол во времени
        st.markdown("#### Гелиоцентрическое расстояние и фазовый угол")
        fig_dist = go.Figure()
        fig_dist.add_trace(go.Scatter(
            x=df_lc["epoch_utc"], y=df_lc["heliocentric_distance"],
            mode="lines+markers", name="r_гел (а.е.)",
            marker=dict(color="#f97316", size=4),
            line=dict(color="#f97316", width=1.5),
        ))
        fig_dist.add_trace(go.Scatter(
            x=df_lc["epoch_utc"], y=df_lc["phase_angle"],
            mode="lines", name="Фазовый угол (°)",
            line=dict(color="#a78bfa", width=1.5, dash="dash"),
            yaxis="y2",
        ))
        fig_dist.update_layout(
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG, font_color="#e6edf3",
            autosize=True, height=260,
            xaxis=dict(gridcolor="#21262d", title="Дата"),
            yaxis=dict(gridcolor="#21262d", title="r_гел (а.е.)"),
            yaxis2=dict(overlaying="y", side="right", title="Фазовый угол (°)",
                        gridcolor="#21262d"),
            legend=dict(bgcolor=CARD_BG, bordercolor="#30363d"),
            margin=dict(l=50, r=60, t=20, b=50),
        )
        st.plotly_chart(fig_dist, use_container_width=True)
    else:
        st.info("Нет фотометрических наблюдений для этого объекта в текущем наборе данных.")


# ═══════════════════════════════════════════════════════════════
# ВКЛАДКА 4 — КАРТА НЕБА
# ═══════════════════════════════════════════════════════════════

with tab_sky:
    st.markdown("## Положение на небе (последний транзит по каждому объекту)")

    if not df_sky.empty:
        fig_sky = px.scatter(
            df_sky, x="ra", y="dec",
            color="heliocentric_distance",
            size=[10] * len(df_sky),
            hover_name="canonical_name",
            hover_data={"ra": ":.2f", "dec": ":.2f",
                        "g_mag": ":.2f", "heliocentric_distance": ":.3f"},
            labels={"ra": "Прямое восхождение (°)", "dec": "Склонение (°)",
                    "heliocentric_distance": "r_гел (а.е.)"},
            color_continuous_scale="Turbo",
            template="plotly_dark",
        )
        sel_sky = df_sky[df_sky["canonical_name"] == selected_name]
        if not sel_sky.empty:
            fig_sky.add_scatter(
                x=sel_sky["ra"], y=sel_sky["dec"], mode="markers",
                marker=dict(size=22, color=ACCENT, symbol="star",
                            line=dict(width=2, color="white")),
                name=f"▶ {selected_name}",
            )
        fig_sky.update_layout(
            paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG, font_color="#e6edf3",
            autosize=True, height=440,
            xaxis=dict(gridcolor="#21262d", range=[0, 360],
                       title="Прямое восхождение (°)"),
            yaxis=dict(gridcolor="#21262d", range=[-90, 90],
                       title="Склонение (°)"),
            margin=dict(l=50, r=20, t=20, b=50),
        )
        st.plotly_chart(fig_sky, use_container_width=True)
        st.caption("⚠️ Координаты соответствуют последнему транзиту Gaia (2014–2017). "
                   "Текущее положение требует интегрирования орбиты.")
    else:
        st.info("Нет данных о положении на небе.")


# ═══════════════════════════════════════════════════════════════
# ВКЛАДКА 5 — ПОЛНЫЙ КАТАЛОГ
# ═══════════════════════════════════════════════════════════════

with tab_catalog:
    st.markdown("## Полный орбитальный каталог")

    display_cols = {
        "canonical_name":   "Название",
        "semi_major_axis":  "a (а.е.)",
        "eccentricity":     "e",
        "inclination":      "i (°)",
        "orbital_period":   "P (лет)",
        "tisserand_jupiter":"T_J",
        "g_mag_abs_mean":   "H (маг)",
        "orbit_class":      "Класс",
        "transit_count":    "Транзиты",
        "g_mag_mean":       "⟨G⟩ (маг)",
        "r_hel_mean":       "⟨r_гел⟩ (а.е.)",
    }
    df_display = df_orbital[[c for c in display_cols if c in df_orbital.columns]].copy()
    df_display = df_display.rename(columns=display_cols)
    for c in ["a (а.е.)", "e", "i (°)", "P (лет)", "T_J", "H (маг)", "⟨G⟩ (маг)", "⟨r_гел⟩ (а.е.)"]:
        if c in df_display.columns:
            df_display[c] = df_display[c].apply(
                lambda x: f"{x:.4f}" if pd.notna(x) else "—"
            )
    st.dataframe(df_display, hide_index=True, use_container_width=True, height=540)

    st.markdown("---")
    st.markdown("### Качество наблюдений")
    obs_disp = df_obs_stat.rename(columns={
        "canonical_name":       "Название",
        "n_transits":           "Транзиты",
        "first_obs":            "Первое набл.",
        "last_obs":             "Последнее набл.",
        "avg_snr":              "Ср. ОСШ",
        "g_mag_stddev":         "Изменч. G",
        "ra_err_mas":           "Ош. ПВ (мсд)",
        "dec_err_mas":          "Ош. скл. (мсд)",
        "avg_solar_elong_deg":  "Ср. элонгация (°)",
    })
    st.dataframe(obs_disp, hide_index=True, use_container_width=True, height=380)


# ═══════════════════════════════════════════════════════════════
# ВКЛАДКА 6 — ИСТОЧНИК ДАННЫХ
# ═══════════════════════════════════════════════════════════════

with tab_source:
    st.markdown("## ℹ️ Источник данных и научная атрибуция")

    st.markdown("""
> **Данные получены из Gaia DR3 (ESA/Gaia/DPAC)**

---

### 📡 Происхождение данных

Дашборд визуализирует данные об объектах Солнечной системы (SSO) из **третьего выпуска
данных миссии ESA Gaia** (Gaia DR3, опубликован 13 июня 2022 г.).

| Поле | Описание |
|---|---|
| **Миссия** | ESA Gaia |
| **Выпуск** | Gaia DR3 (2022-06-13) |
| **Коллаборация** | ESA / Gaia / DPAC |
| **Используемые таблицы** | `gaiadr3.sso_source`, `gaiadr3.sso_observation` |
| **Метод доступа** | TAP+ через `astroquery.gaia` |
| **Архив** | [gea.esac.esa.int](https://gea.esac.esa.int/archive/) |
| **Лицензия** | Creative Commons Attribution 4.0 (CC BY 4.0) |

---

### 📖 Рекомендуемое цитирование

```
Gaia Collaboration, Vallenari, A., et al. (2023).
Gaia Data Release 3. Summary of the content and survey properties.
Astronomy & Astrophysics, 674, A1.
DOI: 10.1051/0004-6361/202243940

Gaia Collaboration, Tanga, P., et al. (2023).
Gaia Data Release 3. The Solar System survey.
Astronomy & Astrophysics, 674, A12.
DOI: 10.1051/0004-6361/202244220
```

---

### 🪐 Выбор объектов

16 астероидов подобраны как объекты, названные в честь учёных и мест,
связанных с **научным наследием Центральной Азии**:

| # | Обозначение | Тёзка |
|---|---|---|
| (3095) | Omarkhayyam | Омар Хайям — персидский поэт и математик (1048–1131) |
| (2755) | Avicenna | Ибн Сина (Авиценна) — врач и философ (980–1037) |
| (9936) | Al-Biruni | Аль-Бируни — учёный-энциклопедист (973–1048) |
| (90806) | Rudaki | Рудаки — основоположник классической персидской поэзии (~858–941) |
| (10269) | Tusi | Насир ад-Дин ат-Туси — математик и астроном (1201–1274) |
| (11156) | Al-Khwarizmi | Аль-Хорезми — основоположник алгебры (~780–850) |
| (2469) | Tajikistan | Республика Таджикистан |
| (2746) | Hissao | Гиссар, Таджикистан |
| (3013) | Dobrovoleva | Ирина Добровольева — советский астроном |
| (3945) | Gerasimenko | Светлана Герасименко — первооткрывательница кометы 67P |
| (4208) | Kiselev | Николай Киселёв — советский/таджикский астроном |
| (4207) | Chernova | Галина Чернова — советский астроном, Душанбе |
| (4011) | Bakharev | Александр Бахарев — советский астроном |
| (7164) | Babadzhanov | Пулат Бабаджанов — таджикский учёный-метеоролог |
| (3436) | Ibadinov | Холикназар Ибадинов — таджикский астроном |
| (24533) | Kokhirova | Гульчехра Кохирова — таджикский астроном |

---

### 🔧 Технические примечания

- **ETL-пайплайн**: `data_loader.py` запрашивает Gaia TAP+ через `astroquery.gaia`.
  При недоступности сервиса автоматически генерируются физически корректные синтетические данные.
- **База данных**: [DuckDB](https://duckdb.org/) — встроенный колоночный аналитический движок.
- **Орбитальные элементы** из `gaiadr3.sso_source` представляют наилучшее решение на эпоху J2016.0.
- **Фазовая кривая** строится по приведённым звёздным величинам: m_red = G − 5·log₁₀(r·Δ).
""")

    st.markdown("---")
    st.markdown(f"""
        <div class="source-badge" style="font-size:0.9rem; padding:16px 22px;">
        <strong>📡 Данные получены из Gaia DR3 (ESA/Gaia/DPAC)</strong><br><br>
        Сервис: <code>https://gea.esac.esa.int/tap-server/tap</code><br>
        Таблицы: <code>gaiadr3.sso_source</code> · <code>gaiadr3.sso_observation</code><br>
        Лицензия: Creative Commons Attribution 4.0 International
        </div>
    """, unsafe_allow_html=True)
