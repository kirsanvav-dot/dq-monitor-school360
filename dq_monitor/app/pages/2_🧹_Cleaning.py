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

# Глобальные стили Arial 15/22
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; font-weight: bold !important; }
    h2, h3 { font-size: 18px !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ ПРОЦЕССА ОЧИСТКИ ---
@st.cache_data(show_spinner="Выполнение очистки и пересчет DQ-метрик...")
def run_cached_cleaning(df, selected_issue_names):
    """
    Применяет правила и сразу пересчитывает Score для чистого датасета.
    selected_issue_names — список имен (строк) IssueType.
    """
    # 1. Превращаем имена обратно в объекты IssueType
    issues_to_clean = [it for it in IssueType if it.name in selected_issue_names]
    config = CleaningConfig(enabled_issues=set(issues_to_clean))

    # 2. Очистка
    cleaner = DataCleaner()
    df_clean_obj, log_obj = cleaner.clean(df, config)

    # 3. Реальный профилинг чистого датасета для оценки прогресса
    profiler = DataProfiler()
    report_after = profiler.profile(df_clean_obj)
    score_after_obj = compute_dq_score(df_clean_obj, report_after)

    return df_clean_obj, log_obj, score_after_obj.total * 100


st.title("🧹 Инструменты очистки данных")

if "df_dirty" not in st.session_state:
    st.warning("Пожалуйста, загрузите датасет на главной странице.")
    st.stop()

df_dirty = st.session_state["df_dirty"]

# --- БЛОК 1: НАСТРОЙКА ПРАВИЛ ---
st.subheader("⚙️ Настройка правил очистки")
st.write("Выберите типы проблем, которые необходимо исправить:")

# Маппинг для заголовков групп
dim_names_ru = {
    "Completeness": "Полнота",
    "Validity": "Валидность",
    "Consistency": "Согласованность",
    "Uniqueness": "Уникальность"
}

selected_issue_names = []
cols = st.columns(4)

# Группируем чекбоксы по измерениям
for i, dim_enum in enumerate(DQDimension):
    with cols[i]:
        rus_dim_name = dim_names_ru.get(dim_enum.value, dim_enum.value)
        st.markdown(f"**{rus_dim_name}**")

        # Получаем все правила, относящиеся к этому измерению
        issues_in_dim = [it for it in IssueType if it.dimension == dim_enum.value]

        for issue in issues_in_dim:
            # Чекбокс для каждого правила
            if st.checkbox(issue.description, value=True, key=f"cb_{issue.name}"):
                selected_issue_names.append(issue.name)

st.divider()

# --- БЛОК 2: ЗАПУСК ---
if st.button("🚀 Запустить очистку выбранных пунктов"):
    if not selected_issue_names:
        st.error("Выберите хотя бы одно правило!")
    else:
        # Вызов кешированной функции (если параметры те же, результат вернется мгновенно)
        df_clean, cleaning_log, score_after = run_cached_cleaning(df_dirty, selected_issue_names)

        # Сохраняем в сессию
        st.session_state.df_clean = df_clean
        st.session_state.cleaning_log = cleaning_log
        st.session_state.dq_score_after = score_after
        st.success("✅ Очистка завершена!")

# --- БЛОК 3: РЕЗУЛЬТАТЫ ---
if "cleaning_log" in st.session_state:
    st.subheader("📈 Динамика качества данных")

    # Сравнение Score До/После
    # (score_before берется со страницы DQ Report или считается по умолчанию 0)
    plot_dq_score_comparison(
        st.session_state.get("dq_score_before", 0),
        st.session_state.dq_score_after
    )

    st.divider()

    # Визуализация лога очистки (перевод и стили внутри viz.py)
    show_full_cleaning_report(
        st.session_state.cleaning_log.to_dataframe(),
        st.session_state.cleaning_log.total_rows_before,
        st.session_state.cleaning_log.total_rows_after
    )

    # Скачивание
    st.divider()
    csv = st.session_state.df_clean.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="💾 Скачать очищенный датасет (CSV)",
        data=csv,
        file_name="cleaned_events.csv",
        mime="text/csv",
    )
else:
    st.info("Настройте правила и нажмите кнопку запуска для получения результатов.")