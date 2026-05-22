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

# Глобальные стили Arial 15/22
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; font-weight: bold !important; }
    .stMetric label { font-size: 15px !important; }
</style>
""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ ВЫЧИСЛЕНИЙ ---
@st.cache_data(show_spinner="Анализ качества данных (профилирование)...")
def get_cached_report(df):
    """Кешируем поиск проблем в датасете."""
    profiler = DataProfiler()
    return profiler.profile(df)


@st.cache_data(show_spinner="Расчет DQ-метрик...")
def get_cached_score(_df, _report):
    """Кешируем расчет финальных скоров."""
    return compute_dq_score(_df, _report)


if "df_dirty" not in st.session_state:
    st.warning("Загрузите данные на главной странице.")
    st.stop()

df = st.session_state["df_dirty"]
st.title("📊 Отчет по качеству данных (DQ Report)")

# Вызов кешированных функций
report = get_cached_report(df)
score = get_cached_score(df, report)

# Сохраняем Score до очистки (для страницы Cleaning)
st.session_state["dq_score_before"] = score.total * 100

# --- БЛОК 1: Метрики (Согласованность) ---
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
    # Радар (английские оси внутри viz.py)
    st.plotly_chart(plot_dq_score_radar(score.to_dict()), use_container_width=True)
with col_right:
    # Распределение типов ошибок
    st.plotly_chart(plot_issues_breakdown(report.to_dataframe()), use_container_width=True)

st.divider()

# --- БЛОК 3: Таблица ---
st.subheader("📋 Детальный список найденных проблем")
rep_df = report.to_dataframe()

if not rep_df.empty:
    # Перевод измерений для таблицы
    dim_ru = {
        "Completeness": "Полнота",
        "Validity": "Валидность",
        "Consistency": "Согласованность",
        "Uniqueness": "Уникальность"
    }
    rep_df["dimension"] = rep_df["dimension"].replace(dim_ru)

    # Оформление колонок
    display_df = rep_df.drop(columns=['issue_type']).rename(columns={
        'dimension': 'Измерение',
        'column': 'Столбцы',
        'description': 'Описание проблемы',
        'rows_affected': 'Затронуто строк',
        'percent_affected': '%'
    })

    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.success("🎉 Проблем не обнаружено! Данные соответствуют всем проверкам.")