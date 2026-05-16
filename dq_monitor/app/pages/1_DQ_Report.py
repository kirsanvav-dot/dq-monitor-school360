"""DQ Report — обзор найденных проблем качества данных."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from src.profiler import DataProfiler
from src.dq_scorer import compute_dq_score
from src.viz import plot_dq_score_radar, plot_issues_breakdown

st.set_page_config(page_title="DQ Report", page_icon="📊", layout="wide")
st.title("📊 DQ Report")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()

df = st.session_state["df_dirty"]

try:
    with st.spinner("Профилирую датасет..."):
        profiler = DataProfiler()
        report = profiler.profile(df)
        score = compute_dq_score(df, report)
except NotImplementedError as e:
    st.info(
        "🔲 **Эта страница ждёт реализации DataProfiler и compute_dq_score.**\n\n"
        f"Сообщение от модуля: `{e}`\n\n"
        "DQ Analyst: см. `src/profiler.py` и `src/dq_scorer.py`."
    )
    st.stop()

st.session_state["dq_report_before"] = report
st.session_state["dq_score_before"] = score

st.header("Сводка по 4 измерениям качества")
cols = st.columns(5)
cols[0].metric("Total DQ Score", f"{score.total:.3f}")
cols[1].metric("Completeness", f"{score.completeness:.3f}")
cols[2].metric("Validity", f"{score.validity:.3f}")
cols[3].metric("Consistency", f"{score.consistency:.3f}")
cols[4].metric("Uniqueness", f"{score.uniqueness:.3f}")

c1, c2 = st.columns([1, 2])
with c1:
    st.plotly_chart(
        plot_dq_score_radar(score.to_dict(), title="DQ Score (до очистки)"),
        use_container_width=True,
    )
with c2:
    st.subheader("Распределение проблем по измерениям")
    counts = report.by_dimension()
    st.bar_chart(counts)

st.divider()
st.header(f"Найдено {report.total_issues} типов DQ-проблем")

if report.total_issues == 0:
    st.warning(
        "Профайлер ничего не нашёл. В датасете есть закладки — "
        "проверьте логику проверок в src/profiler.py."
    )
else:
    issues_df = report.to_dataframe()
    st.plotly_chart(plot_issues_breakdown(issues_df), use_container_width=True)
    st.subheader("Подробная таблица")
    st.dataframe(issues_df, use_container_width=True)

st.info("👈 Дальше — **Cleaning**: применяем правила очистки.")
