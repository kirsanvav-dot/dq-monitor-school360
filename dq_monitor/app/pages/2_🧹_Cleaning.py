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
from src.constant_issue import DQDimension, IssueType, CleanType
from src.viz import plot_dq_score_comparison, show_full_cleaning_report

st.set_page_config(page_title="Очистка данных", layout="wide")

# --- Подписи способов исправления ---
CLEAN_TYPE_LABELS: dict[CleanType, str] = {
    CleanType.DELETE: "Удалить строку",
    CleanType.ZEROING: "Занулить поле (NaN)",
    CleanType.CORRECTION: "Исправить значение",
    CleanType.IGNORE: "Не менять данные (только в отчёт)",
}

# Дефолты = реализованные методы DataCleaner (_clean_{method}_{action})
DEFAULT_CLEAN_TYPE: dict[IssueType, CleanType] = {
    # Completeness
    IssueType.EMPTY_EVENT_ID: CleanType.DELETE,
    IssueType.EMPTY_CLIENT_ID: CleanType.ZEROING,
    IssueType.EMPTY_EVENT_TYPE: CleanType.DELETE,
    IssueType.EMPTY_EVENT_TS: CleanType.ZEROING,
    IssueType.EMPTY_DEVICE_TYPE: CleanType.ZEROING,
    IssueType.EMPTY_IP_ADDRESS: CleanType.ZEROING,
    IssueType.EMPTY_GEO_COUNTRY: CleanType.ZEROING,
    IssueType.EMPTY_GEO_CITY: CleanType.ZEROING,
    IssueType.EMPTY_CHANNEL: CleanType.ZEROING,
    IssueType.EMPTY_AMOUNT_RUB: CleanType.ZEROING,
    IssueType.EMPTY_CURRENCY: CleanType.ZEROING,
    IssueType.EMPTY_MERCHANT_CATEGORY: CleanType.ZEROING,
    IssueType.EMPTY_MERCHANT_COUNTRY: CleanType.ZEROING,
    IssueType.EMPTY_CARD_LAST4: CleanType.ZEROING,
    IssueType.EMPTY_SESSION_START_TS: CleanType.ZEROING,
    IssueType.EMPTY_SESSION_END_TS: CleanType.ZEROING,
    IssueType.EMPTY_LOGIN_SUCCESS: CleanType.ZEROING,
    IssueType.EMPTY_AUTH_METHOD: CleanType.ZEROING,
    IssueType.EMPTY_FLAG_REASON: CleanType.ZEROING,
    # Validity
    IssueType.INVALID_EVENT_TYPE: CleanType.DELETE,
    IssueType.INVALID_FORMAT_DATE: CleanType.ZEROING,
    IssueType.INVALID_SESSION_START_TS: CleanType.ZEROING,
    IssueType.INVALID_SESSION_END_TS: CleanType.ZEROING,
    IssueType.INVALID_IP_ADDRESS: CleanType.ZEROING,
    IssueType.INVALID_AMOUNT_RUB: CleanType.ZEROING,
    IssueType.INVALID_CURRENCY: CleanType.CORRECTION,
    IssueType.INVALID_MERCHANT_CATEGORY: CleanType.CORRECTION,
    IssueType.INVALID_CARD_LAST4: CleanType.CORRECTION,
    IssueType.INVALID_DEVICE_TYPE: CleanType.CORRECTION,
    IssueType.INVALID_GEO_COUNTRY: CleanType.ZEROING,
    IssueType.INVALID_CHANNEL: CleanType.ZEROING,
    # Consistency
    IssueType.INCONSISTENCY_FLAGGED: CleanType.IGNORE,
    IssueType.INCONSISTENCY_TRANSACTION: CleanType.CORRECTION,
    IssueType.INCONSISTENCY_SESSION: CleanType.CORRECTION,
    IssueType.INCONSISTENCY_SESSION_TIMESTAMPS: CleanType.CORRECTION,
    # Uniqueness
    IssueType.DUPLICATE_FULL: CleanType.DELETE,
    IssueType.DUPLICATE_EVENT_ID: CleanType.IGNORE,
}


def _default_clean_type(issue: IssueType) -> CleanType:
    default = DEFAULT_CLEAN_TYPE[issue]
    if default not in issue.clean_type:
        return issue.clean_type[0]
    return default


def _labels_for_issue(issue: IssueType) -> list[str]:
    return [CLEAN_TYPE_LABELS[ct] for ct in issue.clean_type]


def _label_to_clean_type(issue: IssueType) -> dict[str, CleanType]:
    return {CLEAN_TYPE_LABELS[ct]: ct for ct in issue.clean_type}


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


@st.cache_data(show_spinner="Выполнение очистки и пересчет DQ-метрик...")
def run_cached_cleaning(df, enabled_rules_key: tuple[tuple[str, str], ...]):
    """enabled_rules_key: ((issue.name, clean_type.value), ...) — для кеша."""
    enabled_issues = {
        (IssueType[name], CleanType(ct_value))
        for name, ct_value in enabled_rules_key
    }
    config = CleaningConfig(enabled_issues=enabled_issues)

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

enabled_rules: list[tuple[IssueType, CleanType]] = []
cols = st.columns(4)

for i, dim_enum in enumerate(DQDimension):
    with cols[i]:
        st.markdown(f"**{dim_enum.value}**")

        issues_in_dim = [it for it in IssueType if it.dimension == dim_enum.value]
        for issue in issues_in_dim:
            if st.checkbox(issue.description, value=True, key=f"cb_{issue.name}"):
                labels = _labels_for_issue(issue)
                label_map = _label_to_clean_type(issue)
                default_label = CLEAN_TYPE_LABELS[_default_clean_type(issue)]

                selected_label = st.selectbox(
                    "Способ исправления",
                    options=labels,
                    index=labels.index(default_label),
                    key=f"action_{issue.name}",
                )
                enabled_rules.append((issue, label_map[selected_label]))

st.divider()

# --- БЛОК 2: ЗАПУСК ---
if st.button("🚀 Запустить очистку выбранных пунктов"):
    if not enabled_rules:
        st.error("Выберите хотя бы одно правило!")
    else:
        cache_key = tuple(
            sorted((issue.name, ct.value) for issue, ct in enabled_rules)
        )
        df_clean, cleaning_log, score_after = run_cached_cleaning(df_dirty, cache_key)

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
