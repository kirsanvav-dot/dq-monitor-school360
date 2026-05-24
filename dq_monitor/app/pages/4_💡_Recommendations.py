"""Recommendations — бизнес-рекомендации дата-инженерам банка."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from openai import OpenAI
import pandas as pd
from src.schemes import Recomendations
from src.profiler import Report
from src.prompt_builder import build_prompt

@st.cache_resource
def getOpenAIClient():
    try:
        f = open("api_key.env")
        apiKey = f.read()
    except:
        st.error("Не удалось найти API ключ!!!")
        return None
    apiKey = apiKey.strip()
    return OpenAI(api_key=apiKey, base_url="https://openrouter.ai/api/v1")

@st.cache_data(show_spinner="Обращение к LLM для получение рекомендаций...")
def getRecomendations(merged_dirty: pd.DataFrame,
                      merged_clean: pd.DataFrame,
                      _data_issues: Report,
                      _openAIClient: OpenAI) -> pd.DataFrame:
    responce = _openAIClient.responses.parse(model="openai/gpt-4.1",
                                             input=[
                                                 {
                                                     "role": "user",
                                                     "content": build_prompt(merged_dirty, merged_clean, _data_issues)
                                                 }
                                             ],
                                             text_format=Recomendations)
    recomendations = responce.output_parsed.recomendations
    return pd.DataFrame(recomendations, index=pd.RangeIndex(start=1, stop=len(recomendations)+1))

st.set_page_config(page_title="Recommendations", page_icon="💡", layout="wide")
st.title("💡 Рекомендации дата-инженерам")

if "merged_clean" not in st.session_state or "merged_dirty" not in st.session_state or "data_issues" not in st.session_state:
    st.warning("Сначала пройдитесь по предыдущим страницам и соберите информацию о вашем датасете")
    st.stop()

client = getOpenAIClient()

if client is None:
    st.stop()

st.table(getRecomendations(st.session_state["merged_dirty"],
                               st.session_state["merged_clean"],
                               st.session_state["data_issues"], client))
# st.markdown("""
# **Цель страницы:** превратить найденные DQ-проблемы в конкретные
# изменения, которые дата-инженеры банка могут внести в pipeline.

# Хорошая рекомендация:
# - называет **конкретную проблему** в данных
# - предлагает **конкретное техническое решение**
# - оценивает **бизнес-эффект**

# Плохая рекомендация: «нужно улучшить качество данных». Это вода.
# """)

# st.divider()
# st.info("""
# 🔲 **Страница ждёт ваших рекомендаций (Storyteller).**

# После того как DQ Report покажет вам найденные проблемы, сформулируйте
# 3–5 рекомендаций. Замените примеры ниже на свои.

# Структура одной рекомендации:
# - **Проблема:** что не так в данных (конкретно)
# - **Влияние:** как это бьёт по бизнесу (например, по детекции фрода)
# - **Решение:** что технически сделать дата-инженерам
# - **Приоритет:** High / Medium / Low
# """)

# Пример заполненной рекомендации — замените на свои
# example = {
#     "problem": "В currency встречаются опечатки и нестандартные коды "
#                "(USDD, rub, 810, $, RUR, '')",
#     "impact": "Антифрод-правила фильтруют по RUB и пропускают фрод "
#               "с опечаткой в валюте",
#     "solution": "Добавить валидацию на бэкенде: enum ISO 4217. "
#                 "В существующих данных — маппинг через справочник.",
#     "priority": "High",
# }

# st.subheader("Пример рекомендации")
# with st.container(border=True):
#     c1, c2 = st.columns([4, 1])
#     c1.markdown(f"**Проблема:** {example['problem']}")
#     c2.markdown(f"**Приоритет:** `{example['priority']}`")
#     st.markdown(f"**Влияние:** {example['impact']}")
#     st.markdown(f"**Решение:** {example['solution']}")
