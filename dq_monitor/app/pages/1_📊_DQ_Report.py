"""DQ Report — обзор найденных проблем качества данных.

🔲 Эта страница ждёт, пока DQ Analyst реализует src/profiler.py
   и src/dq_scorer.py. Раскомментируйте код по мере готовности модулей.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="DQ Report", page_icon="📊", layout="wide")
st.title("📊 DQ Report")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()

st.info("""
🔲 **Страница ждёт реализации профайлера и DQ-score.**

Что нужно сделать (DQ Analyst):
1. Реализовать классы в `src/profiler.py` (см. описание в файле)
2. Реализовать `compute_dq_score` в `src/dq_scorer.py`
3. Раскомментировать код ниже и адаптировать под имена ваших классов

Шаблон того, что должно быть на странице:

```python
from src.profiler import DataProfiler
from src.dq_scorer import compute_dq_score
from src.viz import plot_dq_score_radar, plot_issues_breakdown

df = st.session_state["df_dirty"]

profiler = DataProfiler()
report = profiler.profile(df)
score = compute_dq_score(df, report)

# Сохраняем для следующих страниц
st.session_state["dq_report_before"] = report
st.session_state["dq_score_before"] = score

# Метрики
cols = st.columns(5)
cols[0].metric("Total DQ Score", f"{score.total:.3f}")
cols[1].metric("Completeness", f"{score.completeness:.3f}")
cols[2].metric("Validity", f"{score.validity:.3f}")
cols[3].metric("Consistency", f"{score.consistency:.3f}")
cols[4].metric("Uniqueness", f"{score.uniqueness:.3f}")

# Графики
st.plotly_chart(plot_dq_score_radar(score.to_dict()))
st.plotly_chart(plot_issues_breakdown(report.to_dataframe()))
st.dataframe(report.to_dataframe())
```
""")
