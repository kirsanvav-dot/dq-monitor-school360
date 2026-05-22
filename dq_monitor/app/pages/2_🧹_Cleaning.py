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
    IssueType.INCONSISTENCY_FLAGGED: CleanType.ZEROING,
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

    /* Таблица правил очистки */
    .clean-rules-header {
        font-weight: bold;
        font-size: 13px;
        padding: 6px 4px;
        border-bottom: 2px solid #ccc;
        margin-bottom: 4px;
    }
    .clean-rules-row {
        padding: 6px 4px;
        border-bottom: 1px solid #eee;
        min-height: 2.4rem;
        white-space: normal;
        word-wrap: break-word;
        line-height: 1.4;
        font-size: 14px;
    }
    /* Selectbox на всю ширину колонки, без обрезки подписи */
    div[data-testid="column"] [data-testid="stSelectbox"] {
        width: 100% !important;
    }
    div[data-testid="column"] [data-testid="stSelectbox"] > div {
        width: 100% !important;
    }
    div[data-testid="column"] [data-testid="stSelectbox"] [data-baseweb="select"] {
        width: 100% !important;
    }
    div[data-testid="column"] [data-testid="stSelectbox"] div[role="combobox"] {
        white-space: normal !important;
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

# --- БЛОК 1: НАСТРОЙКА ПРАВИЛ (табличный вид) ---
st.subheader("⚙️ Настройка правил очистки")

enabled_rules: list[tuple[IssueType, CleanType]] = []

# Дефолт чекбоксов только через session_state (без value= у виджета — иначе конфликт с «Снять все»)
for _issue in IssueType:
    _cb_key = f"cb_{_issue.name}"
    if _cb_key not in st.session_state:
        st.session_state[_cb_key] = True

# Полная ширина: ✓ | Проблема | Способ
_COL_ENABLED = 0.04
_COL_DESC = 0.56
_COL_ACTION = 0.40

for dim_enum in DQDimension:
    issues_in_dim = [it for it in IssueType if it.dimension == dim_enum.value]

    title_col, btn_col = st.columns([0.78, 0.22])
    with title_col:
        st.markdown(f"#### {dim_enum.value}")
    with btn_col:
        sel_all_btn, sel_none_btn = st.columns(2)
        with sel_all_btn:
            if st.button(
                "Все",
                key=f"sel_all_{dim_enum.name}",
                use_container_width=True,
            ):
                for issue in issues_in_dim:
                    st.session_state[f"cb_{issue.name}"] = True
        with sel_none_btn:
            if st.button(
                "Снять",
                key=f"sel_none_{dim_enum.name}",
                use_container_width=True,
            ):
                for issue in issues_in_dim:
                    st.session_state[f"cb_{issue.name}"] = False

    hdr = st.columns([_COL_ENABLED, _COL_DESC, _COL_ACTION])
    hdr[0].markdown('<div class="clean-rules-header">✓</div>', unsafe_allow_html=True)
    hdr[1].markdown('<div class="clean-rules-header">Проблема</div>', unsafe_allow_html=True)
    hdr[2].markdown('<div class="clean-rules-header">Способ исправления</div>', unsafe_allow_html=True)

    for issue in issues_in_dim:
        row = st.columns([_COL_ENABLED, _COL_DESC, _COL_ACTION])
        labels = _labels_for_issue(issue)
        label_map = _label_to_clean_type(issue)
        default_label = CLEAN_TYPE_LABELS[_default_clean_type(issue)]

        with row[0]:
            enabled = st.checkbox(
                "вкл",
                key=f"cb_{issue.name}",
                label_visibility="collapsed",
            )
        with row[1]:
            st.markdown(
                f'<div class="clean-rules-row">{issue.description}</div>',
                unsafe_allow_html=True,
            )
        with row[2]:
            selected_label = st.selectbox(
                "Способ",
                options=labels,
                index=labels.index(default_label),
                key=f"action_{issue.name}",
                label_visibility="collapsed",
                disabled=not enabled,
            )

        if enabled:
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
