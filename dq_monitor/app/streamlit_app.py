"""
DQ Monitor — главная страница (Upload).

Streamlit multipage app. Файлы в app/pages/ автоматически становятся
отдельными страницами в боковом меню.

Состояние между страницами передаётся через st.session_state.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Делаем src/ доступным для импорта при запуске streamlit run app/streamlit_app.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src.data_loader import load_events, get_summary, SchemaError


st.set_page_config(
    page_title="DQ Monitor",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 DQ Monitor — аудит данных для антифрода")

st.markdown("""
**Главная цель:** доказать на цифрах, что качество данных напрямую влияет
на способность системы ловить фрод.

**Пайплайн приложения:**

1. **Upload** (эта страница) — загрузить CSV с событиями
2. **DQ Report** — найти проблемы качества по 4 измерениям
3. **Cleaning** — очистить данные, сравнить score «до/после»
4. **Antifraud Demo** — прогнать правила на грязных и чистых, сравнить confusion matrix
5. **Recommendations** — бизнес-рекомендации дата-инженерам банка
""")

st.divider()

# -- Загрузка файла -------------------------------------------------------
st.header("1. Загрузка датасета")

uploaded = st.file_uploader(
    "Выберите CSV с событиями (events_dirty.csv)",
    type=["csv"],
    help="Файл должен соответствовать схеме EVENTS_REQUIRED_COLUMNS",
)

# Альтернатива — загрузка из файла на диске (удобно для разработки)
with st.expander("Или загрузить из локального файла"):
    default_path = Path(r".dq_monitor_data/data/raw/events_dirty.csv")
    local_path = st.text_input("Путь", value=str(default_path))
    if st.button("Загрузить с диска"):
        try:
            df = load_events(local_path)
            st.session_state["df_dirty"] = df
            st.success(f"Загружено {len(df):,} строк из {local_path}")
        except FileNotFoundError:
            st.error(f"Файл не найден: {local_path}")
        except SchemaError as e:
            st.error(str(e))

if uploaded is not None:
    try:
        df = load_events(uploaded)
        st.session_state["df_dirty"] = df
        st.success(f"Загружено {len(df):,} строк")
    except SchemaError as e:
        st.error(str(e))

# -- Сводка по загруженному датасету --------------------------------------
if "df_dirty" in st.session_state:
    df = st.session_state["df_dirty"]
    st.divider()
    st.header("2. Сводка")

    summary = get_summary(df)
    cols = st.columns(5)
    cols[0].metric("Всего строк", f"{summary['rows']:,}")
    cols[1].metric("Транзакции", f"{summary['transactions']:,}")
    cols[2].metric("Сессии", f"{summary['sessions']:,}")
    cols[3].metric("Уникальные клиенты", f"{summary['unique_clients']:,}")
    cols[4].metric("Размер в памяти", f"{summary['memory_mb']} МБ")

    with st.expander("Превью данных (первые 50 строк)"):
        st.dataframe(df.head(50), use_container_width=True)

    st.info("👈 Переходите в **DQ Report** для анализа качества данных.")
else:
    st.info("Загрузите датасет, чтобы начать.")
