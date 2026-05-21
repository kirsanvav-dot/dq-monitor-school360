import streamlit as st
import sys
from pathlib import Path

# --- ИСПРАВЛЕНИЕ ПУТЕЙ (САМЫЙ ПЕРВЫЙ БЛОК) ---
# Находим корень проекта (dq_monitor)
# Если файл в dq_monitor/app/streamlit_app.py, корень на 1 уровень выше
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Импорт загрузчика из src
from src.data_loader import load_events, get_summary, SchemaError

st.set_page_config(
    page_title="DQ Monitor — Главная",
    page_icon="🔍",
    layout="wide",
)

# Глобальные стили (Arial 15/22)
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: Arial, sans-serif !important;
        font-size: 15px !important;
    }
    h1 {
        font-size: 22px !important;
        font-weight: bold !important;
    }
    h2, h3 {
        font-size: 18px !important;
        font-weight: bold !important;
    }
    .stMetric label {
        font-size: 15px !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🔍 DQ Monitor — Аудит качества данных")

st.markdown("""
**DQ Monitor** — это аналитический инструмент для проверки качества данных в банковских антифрод-системах. 
Приложение позволяет оценить «здоровье» данных, выявить аномалии и исправить их перед запуском моделей машинного обучения.

**Основные шаги:**
1. **Загрузка данных** на этой странице.
2. **Разведочный анализ** (Exploration) — визуализация аномалий.
3. **Отчет по качеству** (DQ Report) — расчет метрик по 4 измерениям.
4. **Очистка** (Cleaning) — автоматическое исправление ошибок.
""")

st.divider()

# -- БЛОК 1: Загрузка датасета --------------------------------------------
st.header("1. Загрузка данных")

uploaded = st.file_uploader(
    "Выберите CSV файл с событиями (например, events_dirty.csv)",
    type=["csv"],
    help="Файл должен содержать колонки: event_id, client_id, event_ts, event_type и др.",
)

# Кнопка быстрой загрузки для разработки (опционально)
with st.expander("Или загрузить из локальной папки данных"):
    local_path = Path("dq_monitor/data/raw/events_dirty.csv")
    if st.button("Загрузить локальный файл"):
        try:
            df_local = load_events(local_path)
            st.session_state["df_dirty"] = df_local
            # Сброс старых состояний при новой загрузке
            for key in ["dq_score_after", "cleaning_log", "df_clean"]:
                if key in st.session_state: del st.session_state[key]
            st.success(f"✅ Загружено {len(df_local):, pulse} строк из {local_path}")
        except Exception as e:
            st.error(f"Файл не найден или ошибка схемы: {e}")

# Обработка загруженного файла
if uploaded is not None:
    try:
        df = load_events(uploaded)
        st.session_state["df_dirty"] = df
        # Сброс старых состояний при новой загрузке
        for key in ["dq_score_after", "cleaning_log", "df_clean"]:
            if key in st.session_state: del st.session_state[key]
        st.success(f"✅ Файл успешно загружен. Количество записей: {len(df):,}")
    except SchemaError as e:
        st.error(f"❌ Ошибка схемы данных: {e}")
    except Exception as e:
        st.error(f"❌ Непредвиденная ошибка: {e}")

# -- БЛОК 2: Сводка по загруженному датасету ------------------------------
if "df_dirty" in st.session_state:
    df = st.session_state["df_dirty"]
    st.divider()
    st.header("2. Краткая сводка")

    summary = get_summary(df)
    cols = st.columns(5)
    cols[0].metric("Всего строк", f"{summary['rows']:,}")
    cols[1].metric("Транзакции", f"{summary['transactions']:,}")
    cols[2].metric("Сессии", f"{summary['sessions']:,}")
    cols[3].metric("Уникальные клиенты", f"{summary['unique_clients']:,}")
    cols[4].metric("Размер в памяти", f"{summary['memory_mb']} МБ")

    with st.expander("Посмотреть первые 50 строк датасета"):
        st.dataframe(df.head(50), use_container_width=True)

    st.info("👈 Теперь вы можете перейти в боковое меню и выбрать раздел **Exploration** или **DQ Report**.")
else:
    st.info("Пожалуйста, загрузите CSV файл, чтобы начать работу с приложением.")