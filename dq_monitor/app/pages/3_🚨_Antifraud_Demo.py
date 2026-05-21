"""Antifraud Demo — side-by-side dirty vs clean: влияние качества данных на детекцию фрода."""
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

df_dirty = st.session_state["df_dirty"]
df_clean = st.session_state.get("df_clean")
has_clean = df_clean is not None

if not has_clean:
    st.info("Очистка ещё не запущена — показан прогон только на грязных данных. Для сравнения выполните Cleaning.")

FRAUD_COST_RUB = 85_000


def _run_engine(df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
    engine = RuleEngine()
    return engine.run_all(df)


def _cache_key() -> str:
    return f"{id(df_dirty)}_{id(df_clean) if has_clean else 'no_clean'}"


def _ensure_predictions() -> None:
    key = _cache_key()
    if st.session_state.get("antifraud_cache_key") == key and "antifraud_dirty_pred" in st.session_state:
        return

    with st.spinner("Прогон антифрод-правил…"):
        df_dirty_pred, rules_dirty = _run_engine(df_dirty)
        st.session_state["antifraud_dirty_pred"] = df_dirty_pred
        st.session_state["antifraud_rules_dirty"] = rules_dirty

        if has_clean:
            df_clean_pred, rules_clean = _run_engine(df_clean)
            st.session_state["antifraud_clean_pred"] = df_clean_pred
            st.session_state["antifraud_rules_clean"] = rules_clean
        else:
            st.session_state.pop("antifraud_clean_pred", None)
            st.session_state.pop("antifraud_rules_clean", None)

        st.session_state["antifraud_cache_key"] = key


_ensure_predictions()

df_dirty_pred: pd.DataFrame = st.session_state["antifraud_dirty_pred"]
rules_dirty: list = st.session_state["antifraud_rules_dirty"]
df_clean_pred: pd.DataFrame | None = st.session_state.get("antifraud_clean_pred")
rules_clean: list | None = st.session_state.get("antifraud_rules_clean")

if st.button("Пересчитать правила"):
    for key in (
        "antifraud_dirty_pred",
        "antifraud_clean_pred",
        "antifraud_rules_dirty",
        "antifraud_rules_clean",
        "antifraud_cache_key",
    ):
        st.session_state.pop(key, None)
    st.rerun()

st.subheader("Срабатывания правил")

if has_clean and df_clean_pred is not None and rules_clean is not None:
    rule_cols = st.columns(2)
    with rule_cols[0]:
        st.markdown("**Грязные данные**")
        st.dataframe(pd.DataFrame(rules_dirty), use_container_width=True, hide_index=True)
        st.metric("Помечено как фрод", int(df_dirty_pred["is_fraud_predicted"].sum()))
    with rule_cols[1]:
        st.markdown("**Чистые данные**")
        st.dataframe(pd.DataFrame(rules_clean), use_container_width=True, hide_index=True)
        st.metric("Помечено как фрод", int(df_clean_pred["is_fraud_predicted"].sum()))
    delta_fraud = int(df_clean_pred["is_fraud_predicted"].sum()) - int(
        df_dirty_pred["is_fraud_predicted"].sum()
    )
    st.caption(f"Δ помеченных строк (clean − dirty): **{delta_fraud:+d}**")
else:
    st.markdown("**Грязные данные**")
    st.dataframe(pd.DataFrame(rules_dirty), use_container_width=True, hide_index=True)
    st.metric("Помечено как фрод", int(df_dirty_pred["is_fraud_predicted"].sum()))

example_cols = st.columns(2 if has_clean and df_clean_pred is not None else 1)
with example_cols[0]:
    with st.expander("Примеры срабатываний — грязные данные"):
        sample_dirty = df_dirty_pred[df_dirty_pred["is_fraud_predicted"]][
            ["event_id", "client_id", "event_ts", "amount_rub", "merchant_category", "triggered_rules"]
        ].head(20)
        if sample_dirty.empty:
            st.write("Срабатываний нет.")
        else:
            st.dataframe(sample_dirty, use_container_width=True, hide_index=True)

if has_clean and df_clean_pred is not None and len(example_cols) > 1:
    with example_cols[1]:
        with st.expander("Примеры срабатываний — чистые данные"):
            sample_clean = df_clean_pred[df_clean_pred["is_fraud_predicted"]][
                ["event_id", "client_id", "event_ts", "amount_rub", "merchant_category", "triggered_rules"]
            ].head(20)
            if sample_clean.empty:
                st.write("Срабатываний нет.")
            else:
                st.dataframe(sample_clean, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Confusion matrix (нужен ground truth)")

labels_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "fraud_labels.csv"
labels: pd.DataFrame | None = None

if labels_path.exists():
    labels = load_fraud_labels(labels_path)
    st.caption(f"Загружены метки из `{labels_path.name}`")

uploaded = st.file_uploader("Или загрузите fraud_labels.csv", type=["csv"])
if uploaded is not None:
    labels = load_fraud_labels(uploaded)

if labels is None:
    st.info(
        "Положите `fraud_labels.csv` в `data/raw/` или загрузите файл выше, "
        "чтобы построить confusion matrix."
    )
    st.stop()

merged_dirty = attach_ground_truth(df_dirty_pred, labels)
cm_dirty = compute_confusion_matrix(
    merged_dirty["is_fraud_predicted"],
    merged_dirty["is_fraud_real"],
)

if has_clean and df_clean_pred is not None:
    merged_clean = attach_ground_truth(df_clean_pred, labels)
    cm_clean = compute_confusion_matrix(
        merged_clean["is_fraud_predicted"],
        merged_clean["is_fraud_real"],
    )
    comp = compare(cm_dirty, cm_clean)

    cm_cols = st.columns(2)
    with cm_cols[0]:
        st.plotly_chart(
            plot_confusion_matrix(cm_dirty.to_dict(), "Грязные данные"),
            use_container_width=True,
        )
    with cm_cols[1]:
        st.plotly_chart(
            plot_confusion_matrix(cm_clean.to_dict(), "Чистые данные"),
            use_container_width=True,
        )

    st.subheader("Метрики качества детекции")
    metrics_df = pd.DataFrame(
        [
            {
                "Датасет": "Грязные",
                "TP": cm_dirty.tp,
                "FP": cm_dirty.fp,
                "FN": cm_dirty.fn,
                "TN": cm_dirty.tn,
                "Precision": round(cm_dirty.precision, 4),
                "Recall": round(cm_dirty.recall, 4),
                "F1": round(cm_dirty.f1, 4),
            },
            {
                "Датасет": "Чистые",
                "TP": cm_clean.tp,
                "FP": cm_clean.fp,
                "FN": cm_clean.fn,
                "TN": cm_clean.tn,
                "Precision": round(cm_clean.precision, 4),
                "Recall": round(cm_clean.recall, 4),
                "F1": round(cm_clean.f1, 4),
            },
        ]
    )
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)

    delta = comp["delta"]
    extra_caught = delta["tp"]
    st.success(
        f"**+{extra_caught}** дополнительно пойманных фродов (ΔTP) "
        f"≈ **{extra_caught * FRAUD_COST_RUB:,.0f} ₽** "
        f"(оценка {FRAUD_COST_RUB:,} ₽ на один кейс)"
    )

    delta_cols = st.columns(4)
    delta_cols[0].metric("Δ TP", delta["tp"])
    delta_cols[1].metric("Δ FP", delta["fp"])
    delta_cols[2].metric("Δ Recall, п.п.", delta["recall_pp"])
    delta_cols[3].metric("Δ F1, п.п.", delta["f1_pp"])

    with st.expander("Полное сравнение (compare)"):
        st.json(comp)
else:
    st.plotly_chart(
        plot_confusion_matrix(cm_dirty.to_dict(), "Грязные данные"),
        use_container_width=True,
    )
    st.subheader("Метрики (грязные данные)")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "TP": cm_dirty.tp,
                    "FP": cm_dirty.fp,
                    "FN": cm_dirty.fn,
                    "TN": cm_dirty.tn,
                    "Precision": round(cm_dirty.precision, 4),
                    "Recall": round(cm_dirty.recall, 4),
                    "F1": round(cm_dirty.f1, 4),
                }
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
