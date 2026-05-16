"""Cleaning — настройка и запуск пайплайна очистки."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.cleaner import CleaningConfig, DataCleaner
from src.profiler import DataProfiler
from src.dq_scorer import compute_dq_score
from src.viz import plot_dq_score_comparison

st.set_page_config(page_title="Cleaning", page_icon="🧹", layout="wide")
st.title("🧹 Cleaning")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()

df_dirty = st.session_state["df_dirty"]

st.header("Какие правила применить")
c1, c2 = st.columns(2)
with c1:
    st.subheader("Удаление")
    cfg_remove_duplicates = st.checkbox("Удалить дубликаты строк", value=True)
    cfg_drop_missing_client = st.checkbox("Удалить строки без client_id", value=True)
    cfg_parse_dates = st.checkbox("Удалить строки с невалидной датой", value=True)
    cfg_drop_amounts = st.checkbox("Удалить аномальные суммы (NaN, <0, >10M)", value=True)
    cfg_drop_ips = st.checkbox("Удалить строки с невалидным IP", value=False)
with c2:
    st.subheader("Восстановление")
    cfg_currency = st.checkbox("Исправить опечатки в currency → RUB/USD/EUR", value=True)
    cfg_mcc = st.checkbox("Раскодировать ISO-коды в merchant_category", value=True)
    cfg_device = st.checkbox("Привести '' в device_type к NaN", value=True)
    cfg_flag = st.checkbox("Согласовать is_flagged и flag_reason", value=True)
    cfg_session_leak = st.checkbox(
        "Обнулить чужие поля по типу события (transaction/session)", value=True)

config = CleaningConfig(
    remove_duplicates=cfg_remove_duplicates,
    drop_missing_client_id=cfg_drop_missing_client,
    parse_dates_drop_invalid=cfg_parse_dates,
    fix_currency_typos=cfg_currency,
    fix_mcc_iso_codes=cfg_mcc,
    fix_device_type_empty=cfg_device,
    drop_invalid_amounts=cfg_drop_amounts,
    drop_invalid_ips=cfg_drop_ips,
    fix_flag_inconsistency=cfg_flag,
    fix_session_transaction_leak=cfg_session_leak,
)

if st.button("🚀 Запустить очистку", type="primary"):
    try:
        with st.spinner("Чищу данные..."):
            cleaner = DataCleaner()
            df_clean, log = cleaner.clean(df_dirty, config)
            st.session_state["df_clean"] = df_clean
            st.session_state["cleaning_log"] = log

            report_after = DataProfiler().profile(df_clean)
            score_after = compute_dq_score(df_clean, report_after)
            st.session_state["dq_report_after"] = report_after
            st.session_state["dq_score_after"] = score_after
    except NotImplementedError as e:
        st.info(
            "🔲 **Эта страница ждёт реализации DataCleaner.**\n\n"
            f"Сообщение от модуля: `{e}`\n\n"
            "Backend / DQ Analyst: см. `src/cleaner.py`."
        )
        st.stop()

if "df_clean" in st.session_state:
    st.divider()
    st.header("Результат")
    log = st.session_state["cleaning_log"]
    score_before = st.session_state.get("dq_score_before")
    score_after = st.session_state["dq_score_after"]

    cols = st.columns(3)
    cols[0].metric("Строк до", f"{log.initial_rows:,}")
    cols[1].metric("Строк после", f"{log.final_rows:,}",
                   delta=log.final_rows - log.initial_rows)
    cols[2].metric("Удалено", f"{log.initial_rows - log.final_rows:,}")

    st.subheader("Лог по шагам")
    st.dataframe(log.to_dataframe(), use_container_width=True)

    if score_before is not None:
        st.subheader("DQ Score: до vs после")
        st.plotly_chart(
            plot_dq_score_comparison(score_before.to_dict(), score_after.to_dict()),
            use_container_width=True,
        )
        c1, c2 = st.columns(2)
        c1.metric("Total Score до", f"{score_before.total:.3f}")
        c2.metric("Total Score после", f"{score_after.total:.3f}",
                  delta=f"{score_after.total - score_before.total:+.3f}")

    st.info("👈 Дальше — **Antifraud Demo**: смотрим, как очистка влияет на детекцию фрода.")
