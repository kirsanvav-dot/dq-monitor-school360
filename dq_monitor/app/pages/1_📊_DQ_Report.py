import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# --- НАСТРОЙКА ПУТЕЙ ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.profiler import DataProfiler
from src.dq_scorer import compute_dq_score
from src.viz import plot_dq_score_radar, plot_issues_breakdown

st.set_page_config(page_title="Отчет DQ", layout="wide")

# --- ПРОДВИНУТАЯ ТИПОГРАФИКА И ЦЕНТРИРОВАНИЕ ---
st.markdown("""
<style>
    /* Основной текст */
    html, body, [class*="css"], p, div, span, label, li {
        font-family: 'Arial', sans-serif !important;
        font-size: 15px !important;
        color: #334155;
    }
    /* Заголовки разного уровня */
    h1 { font-size: 28px !important; font-weight: 700 !important; color: #0f172a !important; margin-bottom: 0.5rem !important; }
    h2 { font-size: 22px !important; font-weight: 600 !important; color: #1e293b !important; margin-top: 1rem !important; }
    h3 { font-size: 18px !important; font-weight: 600 !important; color: #1e293b !important; }

    /* Метрики (Стильные крупные цифры) */
    [data-testid="stMetricValue"] { font-size: 28px !important; font-weight: 700 !important; color: #0f172a !important; }
    [data-testid="stMetricLabel"] p { font-size: 15px !important; color: #64748b !important; font-weight: 600 !important; }

    /* Таблицы (Центрирование и стиль) */
    [data-testid="stTable"] th { font-size: 15px !important; font-weight: 600 !important; text-align: center !important; background-color: #f8fafc !important; }
    [data-testid="stTable"] td { font-size: 14px !important; text-align: center !important; vertical-align: middle !important; }
</style>
""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ ---
@st.cache_data(show_spinner="Анализ качества данных...")
def get_cached_report(df):
    profiler = DataProfiler()
    return profiler.profile(df)


if "df_dirty" not in st.session_state:
    st.warning("Пожалуйста, сначала загрузите датасет на главной странице.")
    st.stop()

df = st.session_state["df_dirty"]
st.title("📊 Отчет по качеству данных (DQ Report)")

# Реальный расчет
report = get_cached_report(df)
score = compute_dq_score(df, report)

# Сохраняем Score для страницы Cleaning
st.session_state["dq_score_before"] = score.total * 100

# --- БЛОК 1: МЕТРИКИ (АНГЛИЙСКИЙ ЯЗЫК ПО ЗАПРОСУ) ---
cols = st.columns(5)
cols[0].metric("Total DQ Score", f"{score.total:.3f}")
cols[1].metric("Completeness", f"{score.completeness:.3f}")
cols[2].metric("Validity", f"{score.validity:.3f}")
cols[3].metric("Consistency", f"{score.consistency:.3f}")
cols[4].metric("Uniqueness", f"{score.uniqueness:.3f}")

st.divider()

# --- БЛОК 2: ГРАФИКИ ---
col_left, col_right = st.columns(2)
with col_left:
    st.plotly_chart(plot_dq_score_radar(score.to_dict()), use_container_width=True)
with col_right:
    st.plotly_chart(plot_issues_breakdown(report.to_dataframe()), use_container_width=True)

st.divider()

# --- БЛОК 3: ТАБЛИЦА ---
st.subheader("📋 Детальный список найденных проблем")
rep_df = report.to_dataframe()

if not rep_df.empty:
    display_df = rep_df.drop(columns=['issue_type', 'column']).rename(columns={
        'dimension': 'Измерение',
        'description': 'Описание проблемы',
        'rows_affected': 'Затронуто строк',
        'percent_affected': '%'
    })

    # Нумерация с 1
    display_df.index = range(1, len(display_df) + 1)

    # Вывод таблицы (центрирование применится через CSS)
    st.table(display_df)
else:
    st.success("🎉 Проблем не обнаружено! Данные идеальны.")