"""Cleaning — настройка и запуск пайплайна очистки."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.cleaner import DataCleaner, CleaningConfig, CleaningLog
from src.constant_issue import DQDimension

st.set_page_config(page_title="Cleaning", page_icon="🧹", layout="wide")
st.title("🧹 Cleaning")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()

df_dirty = st.session_state["df_dirty"]

st.subheader("Настройки очистки")
config = CleaningConfig(
    enabled_dimensions={
        DQDimension.COMPLETENESS,
        DQDimension.CONSISTENCY,
        DQDimension.UNIQUENESS,
        DQDimension.VALIDITY,
    },
)

if st.button("Запустить очистку", type="primary"):
    cleaner = DataCleaner()
    df_clean, log = cleaner.clean(df_dirty, config)
    st.session_state["df_clean"] = df_clean
    st.session_state["cleaning_log"] = log
    st.rerun()

if "cleaning_log" not in st.session_state:
    st.info("Нажмите «Запустить очистку», чтобы получить лог.")
    st.stop()

log: CleaningLog = st.session_state["cleaning_log"]

st.subheader("CleaningLog — сводка")
summary_cols = st.columns(4)
summary_cols[0].metric("Строк до очистки", log.total_rows_before)
summary_cols[1].metric("Строк после очистки", log.total_rows_after)
summary_cols[2].metric(
    "Удалено строк",
    log.total_rows_before - log.total_rows_after,
    help="Разница total_rows_before и total_rows_after",
)
summary_cols[3].metric("Затронуто строк (уник.)", log.total_all)

action_cols = st.columns(4)
action_cols[0].metric("DELETE (уник.)", log.total_deleted)
action_cols[1].metric("ZEROING (уник.)", log.total_zeroed)
action_cols[2].metric("CORRECTION (уник.)", log.total_corrected)
action_cols[3].metric("IGNORE (уник.)", log.total_ignored)

st.subheader("CleaningLog — правила")
st.dataframe(log.to_dataframe(), use_container_width=True, hide_index=True)

st.subheader("CleaningLog — детали по шагам")
for cl_issue in log.issues:
    with st.expander(
        f"{cl_issue.issue_type.name} · {cl_issue.clean_type} · {cl_issue.rows_affected} строк",
        expanded=False,
    ):
        st.write(cl_issue.issue_type.description)
        st.write(f"Измерение: **{cl_issue.issue_type.dimension}**")
        st.write(f"Колонки: `{cl_issue.issue_type.column}`")
        if cl_issue.rows_affected == 0:
            st.caption("Индексы не затронуты.")
        elif cl_issue.rows_affected <= 200:
            st.write("Индексы строк:", cl_issue.affected_indices.tolist())
        else:
            st.write(
                f"Индексы строк (первые 200 из {cl_issue.rows_affected}):",
                cl_issue.affected_indices[:200].tolist(),
            )
