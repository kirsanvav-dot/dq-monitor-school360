import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# --- ИСПРАВЛЕНИЕ ПУТЕЙ ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.cleaner import DataCleaner, CleaningConfig
from src.profiler import DataProfiler
from src.dq_scorer import compute_dq_score
from src.constant_issue import DQDimension, IssueType
from src.viz import plot_dq_score_comparison, show_full_cleaning_report

st.set_page_config(page_title="Очистка данных", layout="wide")

# --- ГЛОБАЛЬНЫЕ СТИЛИ: Arial + Центрирование ---
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; font-weight: bold !important; }
    h2, h3 { font-size: 18px !important; font-weight: bold !important; }

    /* Принудительное центрирование контента в таблицах */
    [data-testid="stTable"] td, [data-testid="stTable"] th { 
        text-align: center !important; 
        vertical-align: middle !important; 
    }
</style>
""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ ОЧИСТКИ ---
@st.cache_data(show_spinner="Выполнение очистки и пересчет DQ-метрик...")
def run_cached_cleaning(df, selected_issue_names):
    """Применяет правила и пересчитывает Score."""
    issues_to_clean = [it for it in IssueType if it.name in selected_issue_names]
    config = CleaningConfig(enabled_issues=set(issues_to_clean))

    cleaner = DataCleaner()
    df_clean_obj, log_obj = cleaner.clean(df, config)

    profiler = DataProfiler()
    report_after = profiler.profile(df_clean_obj)
    score_after_obj = compute_dq_score(df_clean_obj, report_after)

    return df_clean_obj, log_obj, score_after_obj.total * 100


st.title("🧹 Инструменты очистки данных")

if "df_dirty" not in st.session_state:
    st.warning("Пожалуйста, сначала загрузите датасет на главной странице.")
    st.stop()

df_dirty = st.session_state["df_dirty"]

# --- БЛОК 1: НАСТРОЙКА ПРАВИЛ ---
st.subheader("⚙️ Настройка правил очистки")

selected_issue_names = []
cols = st.columns(4)

# Группируем чекбоксы по английским названиям измерений
for i, dim_enum in enumerate(DQDimension):
    with cols[i]:
        # Отображаем название измерения на английском (Completeness, Validity...)
        st.markdown(f"**{dim_enum.value}**")

        issues_in_dim = [it for it in IssueType if it.dimension == dim_enum.value]
        for issue in issues_in_dim:
            # Чекбокс с русским описанием проблемы
            if st.checkbox(issue.description, value=True, key=f"cb_{issue.name}"):
                selected_issue_names.append(issue.name)

st.divider()

# --- БЛОК 2: ЗАПУСК ---
if st.button("🚀 Запустить очистку выбранных пунктов"):
    if not selected_issue_names:
        st.error("Выберите хотя бы одно правило!")
    else:
        df_clean, cleaning_log, score_after = run_cached_cleaning(df_dirty, selected_issue_names)

        st.session_state.df_clean = df_clean
        st.session_state.cleaning_log = cleaning_log
        st.session_state.dq_score_after = score_after
        st.success("✅ Очистка завершена!")

# --- БЛОК 3: РЕЗУЛЬТАТЫ ---
if "cleaning_log" in st.session_state:
    st.subheader("📈 Динамика качества данных")

    plot_dq_score_comparison(
        st.session_state.get("dq_score_before", 0),
        st.session_state.dq_score_after
    )

    st.divider()

    # Визуализация лога (внутри viz.py теперь тоже центрирование и удаление столбца)
    show_full_cleaning_report(
        st.session_state.cleaning_log.to_dataframe(),
        st.session_state.cleaning_log.total_rows_before,
        st.session_state.cleaning_log.total_rows_after
    )

    st.divider()
    csv = st.session_state.df_clean.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="💾 Скачать очищенный датасет (CSV)",
        data=csv,
        file_name="cleaned_events.csv",
        mime="text/csv",
    )