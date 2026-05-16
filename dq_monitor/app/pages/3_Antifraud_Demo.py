"""Antifraud Demo — главное шоу для защиты: side-by-side dirty vs clean."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pandas as pd
import streamlit as st

from src.antifraud_rules import RuleEngine
from src.data_loader import load_fraud_labels
from src.metrics import compute_confusion_matrix, attach_ground_truth, compare
from src.viz import plot_confusion_matrix

st.set_page_config(page_title="Antifraud Demo", page_icon="🚨", layout="wide")
st.title("🚨 Antifraud Demo — влияние качества данных на детекцию фрода")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()
if "df_clean" not in st.session_state:
    st.warning("Сначала запустите очистку на странице Cleaning.")
    st.stop()

st.header("Ground truth")
st.markdown(
    "Для оценки качества правил нужен файл `fraud_labels.csv` с эталонными "
    "метками `is_fraud_real`. Ментор выдаёт его на дне 7-8."
)

labels_upload = st.file_uploader("Загрузите fraud_labels.csv", type=["csv"])
with st.expander("Или с диска"):
    labels_path = st.text_input("Путь", value="data/ground_truth/fraud_labels.csv")
    if st.button("Загрузить метки с диска"):
        try:
            st.session_state["fraud_labels"] = load_fraud_labels(labels_path)
            st.success(f"Загружено {len(st.session_state['fraud_labels']):,} меток")
        except FileNotFoundError:
            st.error(f"Файл не найден: {labels_path}")

if labels_upload is not None:
    st.session_state["fraud_labels"] = load_fraud_labels(labels_upload)

if "fraud_labels" not in st.session_state:
    st.stop()

labels = st.session_state["fraud_labels"]
df_dirty = st.session_state["df_dirty"]
df_clean = st.session_state["df_clean"]

if st.button("🚀 Прогнать антифрод-правила на обеих версиях", type="primary"):
    try:
        engine = RuleEngine()
        with st.spinner("Грязные данные..."):
            df_dirty_pred, rule_results_dirty = engine.run_all(df_dirty)
            merged_dirty = attach_ground_truth(df_dirty_pred, labels)
            cm_dirty = compute_confusion_matrix(
                predictions=merged_dirty["is_fraud_predicted"].tolist(),
                labels=merged_dirty["is_fraud_real"].tolist(),
            )
        with st.spinner("Чистые данные..."):
            df_clean_pred, rule_results_clean = engine.run_all(df_clean)
            merged_clean = attach_ground_truth(df_clean_pred, labels)
            cm_clean = compute_confusion_matrix(
                predictions=merged_clean["is_fraud_predicted"].tolist(),
                labels=merged_clean["is_fraud_real"].tolist(),
            )
        st.session_state["cm_dirty"] = cm_dirty
        st.session_state["cm_clean"] = cm_clean
        st.session_state["rule_results_dirty"] = rule_results_dirty
        st.session_state["rule_results_clean"] = rule_results_clean
    except NotImplementedError as e:
        st.info(
            "🔲 **Эта страница ждёт реализации RuleEngine.**\n\n"
            f"Сообщение от модуля: `{e}`\n\n"
            "Antifraud Engineer: см. `src/antifraud_rules.py`."
        )
        st.stop()

if "cm_dirty" in st.session_state and "cm_clean" in st.session_state:
    cm_dirty = st.session_state["cm_dirty"]
    cm_clean = st.session_state["cm_clean"]
    comparison = compare(cm_dirty, cm_clean)

    st.divider()
    st.header("Главный слайд защиты: до vs после")

    cols = st.columns(4)
    cols[0].metric("TP (поймали фрод)", cm_clean.tp,
                   delta=comparison["delta"]["tp"])
    cols[1].metric("FP (ложные тревоги)", cm_clean.fp,
                   delta=comparison["delta"]["fp"], delta_color="inverse")
    cols[2].metric("FN (пропустили фрод)", cm_clean.fn,
                   delta=comparison["delta"]["fn"], delta_color="inverse")
    cols[3].metric("Recall", f"{cm_clean.recall:.3f}",
                   delta=f"{comparison['delta']['recall_pp']:+.1f} п.п.")

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            plot_confusion_matrix(cm_dirty.to_dict(), title="Грязные данные"),
            use_container_width=True,
        )
        st.metric("F1 на грязных", f"{cm_dirty.f1:.3f}")
    with c2:
        st.plotly_chart(
            plot_confusion_matrix(cm_clean.to_dict(), title="Чистые данные"),
            use_container_width=True,
        )
        st.metric("F1 на чистых", f"{cm_clean.f1:.3f}")

    extra_caught = comparison["delta"]["tp"]
    fewer_false_alarms = -comparison["delta"]["fp"]
    avg_fraud_amount = 85_000
    saved_money = extra_caught * avg_fraud_amount

    st.success(
        f"**Эффект очистки:** дополнительно поймали **{extra_caught}** фродов, "
        f"уменьшили ложные тревоги на **{fewer_false_alarms}**. "
        f"В пересчёте на средний чек фрода (~{avg_fraud_amount:,} ₽) — "
        f"это **~{saved_money/1_000_000:.1f} млн ₽** сохранённых средств."
    )

    st.divider()
    st.subheader("Срабатывания по правилам")
    rule_data = []
    for r_dirty, r_clean in zip(
        st.session_state["rule_results_dirty"],
        st.session_state["rule_results_clean"],
    ):
        rule_data.append({
            "rule_id": r_dirty.rule_id,
            "rule_name": r_dirty.rule_name,
            "triggered_dirty": r_dirty.triggered_count,
            "triggered_clean": r_clean.triggered_count,
            "delta": r_clean.triggered_count - r_dirty.triggered_count,
        })
    st.dataframe(pd.DataFrame(rule_data), use_container_width=True)

    st.info("👈 Дальше — **Recommendations**: что советуем дата-инженерам банка.")
