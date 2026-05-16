"""Recommendations — бизнес-рекомендации дата-инженерам банка.

Здесь команда формирует выводы из DQ-отчёта в виде ACTIONABLE рекомендаций.
Это раздел Storyteller / Business Analyst — самый важный для жюри.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="Recommendations", page_icon="💡", layout="wide")
st.title("💡 Рекомендации дата-инженерам")

st.markdown("""
**Цель этой страницы:** превратить найденные DQ-проблемы в конкретные
изменения, которые дата-инженеры банка могут внести в pipeline.

Хорошая рекомендация:
- называет **конкретную проблему** в данных
- предлагает **конкретное техническое решение**
- оценивает **бизнес-эффект**

Плохая рекомендация: "нужно улучшить качество данных". Это вода.
""")

# Если DQ-отчёт уже посчитан — показываем его как контекст
if "dq_report_before" in st.session_state:
    report = st.session_state["dq_report_before"]
    with st.expander(f"Контекст: {report.total_issues} найденных DQ-проблем"):
        st.dataframe(report.to_dataframe(), use_container_width=True)

st.divider()
st.header("Шаблоны рекомендаций")
st.markdown(
    "Команда заполняет 3-5 рекомендаций ниже. Это и есть финальный артефакт "
    "проекта для бизнеса."
)

# TODO команде: заменить эти шаблоны на реальные рекомендации из своего анализа
EXAMPLE_RECOMMENDATIONS = [
    {
        "problem": "В currency встречаются опечатки и нестандартные коды "
                   "(USDD, rub, 810, $, RUR, '')",
        "impact": "Антифрод-правила фильтруют по RUB и пропускают фрод "
                  "с опечаткой в валюте",
        "solution": "Добавить валидацию на бэкенде: enum ISO 4217. "
                    "В существующих данных — маппинг через справочник.",
        "priority": "High",
    },
    {
        "problem": "В одном из месяцев merchant_category содержит ISO-коды "
                   "(5411, 5812, ...) вместо текстовых значений",
        "impact": "Правило по рисковым категориям не сработает на этих "
                  "транзакциях — фрод проходит",
        "solution": "Стандартизировать формат на уровне ETL: один источник "
                    "правды по справочнику MCC, обратный маппинг для legacy.",
        "priority": "High",
    },
    # TODO команде: добавить ещё 1-3 рекомендации из своего анализа
]

for rec in EXAMPLE_RECOMMENDATIONS:
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**Проблема:** {rec['problem']}")
        c2.markdown(f"**Приоритет:** `{rec['priority']}`")
        st.markdown(f"**Влияние на бизнес:** {rec['impact']}")
        st.markdown(f"**Что делать:** {rec['solution']}")

st.divider()
st.subheader("📝 TODO команде")
st.info(
    "Замените `EXAMPLE_RECOMMENDATIONS` в этом файле на реальные рекомендации, "
    "сформулированные из вашего DQ-отчёта. Минимум 3-5 пунктов. "
    "Это — то, что увидит жюри на финальной защите."
)
