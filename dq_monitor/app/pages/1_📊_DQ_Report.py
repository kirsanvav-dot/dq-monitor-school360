import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# --- ИСПРАВЛЕНИЕ ПУТЕЙ ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.profiler import DataProfiler
from src.dq_scorer import compute_dq_score
from src.viz import plot_dq_score_radar, plot_issues_breakdown

st.set_page_config(page_title="Отчет DQ", layout="wide")

# --- ГЛОБАЛЬНЫЕ СТИЛИ: Arial + Центрирование ячеек ---
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; font-weight: bold !important; }

    /* Центрирование текста во всех таблицах приложения */
    [data-testid="stTable"] td, [data-testid="stTable"] th { 
        text-align: center !important; 
        vertical-align: middle !important; 
    }
    .stMetric label { font-size: 15px !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Анализ качества данных...")
def get_cached_report(df):
    profiler = DataProfiler()
    return profiler.profile(df)


if "df_dirty" not in st.session_state:
    st.warning("Загрузите данные на главной странице.")
    st.stop()

df = st.session_state["df_dirty"]
st.title("📊 Отчет по качеству данных (DQ Report)")

report = get_cached_report(df)
score = compute_dq_score(df, report)

# Сохраняем Score для страницы Cleaning
st.session_state["dq_score_before"] = score.total * 100

# --- БЛОК 1: Метрики (На русском) ---
st.subheader("📈 Ключевые показатели качества")
cols = st.columns(5)
cols[0].metric("Итоговый DQ Score", f"{score.total:.3f}")
cols[1].metric("Полнота", f"{score.completeness:.3f}")
cols[2].metric("Валидность", f"{score.validity:.3f}")
cols[3].metric("Согласованность", f"{score.consistency:.3f}")
cols[4].metric("Уникальность", f"{score.uniqueness:.3f}")

st.divider()

# --- БЛОК 2: Графики ---
col_left, col_right = st.columns(2)
with col_left:
    # Радар (английские оси зашиты в viz.py)
    st.plotly_chart(plot_dq_score_radar(score.to_dict()), use_container_width=True)
with col_right:
    # Бар-чарт (английские категории зашиты в viz.py)
    st.plotly_chart(plot_issues_breakdown(report.to_dataframe()), use_container_width=True)

st.divider()

# --- БЛОК 3: Таблица (С центрированием и английскими строками) ---
st.subheader("📋 Детальный список найденных проблем")
rep_df = report.to_dataframe()

if not rep_df.empty:
    # 1. Удаляем колонку 'column' (Затронутые столбцы) по требованию
    # 2. Переименовываем заголовки, оставляя содержимое dimension на английском
    display_df = rep_df.drop(columns=['issue_type', 'column']).rename(columns={
        'dimension': 'Измерение',
        'description': 'Описание проблемы',
        'rows_affected': 'Затронуто строк',
        'percent_affected': '%'
    })
    display_df.index = range(1, len(display_df) + 1)
    # Используем st.table для идеального центрирования через CSS
    st.table(display_df)
else:
    st.success("🎉 Проблем не обнаружено!")