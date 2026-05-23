import streamlit as st
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.data_loader import load_events, get_summary, SchemaError

st.set_page_config(page_title="DQ Monitor — Главная", page_icon="🔍", layout="wide")

# --- ПРОДВИНУТАЯ ТИПОГРАФИКА (ARIAL) ---
st.markdown("""
<style>
    /* Основной текст */
    html, body, [class*="css"], p, div, span, label, li {
        font-family: 'Arial', sans-serif !important;
        font-size: 15px !important;
        color: #334155;
    }
    /* Заголовки разного уровня */
    h1 { font-size: 28px !important; font-weight: 700 !important; color: #0f172a !important; margin-bottom: 0.5rem !important; }
    h2 { font-size: 22px !important; font-weight: 600 !important; color: #1e293b !important; margin-top: 1rem !important; }
    h3 { font-size: 18px !important; font-weight: 600 !important; color: #1e293b !important; }

    /* Метрики (Стильные крупные цифры) */
    [data-testid="stMetricValue"] { font-size: 28px !important; font-weight: 700 !important; color: #0f172a !important; }
    [data-testid="stMetricLabel"] p { font-size: 15px !important; color: #64748b !important; font-weight: 600 !important; }
    [data-testid="stMetricDelta"] div { font-size: 14px !important; font-weight: 600 !important; }

    /* Таблицы */
    [data-testid="stTable"] th { font-size: 15px !important; font-weight: 600 !important; text-align: center !important; background-color: #f8fafc !important; }
    [data-testid="stTable"] td { font-size: 14px !important; text-align: center !important; vertical-align: middle !important; }

    /* Боковое меню */
    [data-testid="stSidebar"] span { font-size: 15px !important; font-weight: 500 !important; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 DQ Monitor — Аудит качества данных")

st.markdown("""
**DQ Monitor** — это аналитический инструмент для проверки качества данных в банковских антифрод-системах. 
Приложение позволяет оценить «здоровье» данных, выявить аномалии и исправить их перед запуском моделей машинного обучения.

**Основные шаги:**
1. **Загрузка данных** на этой странице.
2. **Разведочный анализ** (EDA) — визуализация аномалий.
3. **Отчет по качеству** (DQ Report) — расчет метрик по 4 измерениям.
4. **Очистка** (Cleaning) — автоматическое исправление ошибок.
""")

st.divider()

st.header("1. Загрузка данных")

uploaded = st.file_uploader(
    "Выберите CSV файл с событиями (например, events_dirty.csv)",
    type=["csv"],
    help="Файл должен содержать колонки: event_id, client_id, event_ts, event_type и др.",
)

with st.expander("Или загрузить из локальной папки данных (для разработки)"):
    local_path = Path("dq_monitor/data/raw/events_dirty.csv")
    if st.button("Загрузить локальный файл"):
        try:
            df_local = load_events(local_path)
            st.session_state["df_dirty"] = df_local
            for key in ["dq_score_after", "cleaning_log", "df_clean"]:
                if key in st.session_state: del st.session_state[key]
            st.success(f"✅ Загружено {len(df_local):,} строк из {local_path}")
        except Exception as e:
            st.error(f"Файл не найден или ошибка: {e}")

if uploaded is not None:
    try:
        df = load_events(uploaded)
        st.session_state["df_dirty"] = df
        for key in ["dq_score_after", "cleaning_log", "df_clean"]:
            if key in st.session_state: del st.session_state[key]
        st.success(f"✅ Файл успешно загружен. Количество записей: {len(df):,}")
    except SchemaError as e:
        st.error(f"❌ Ошибка схемы данных: {e}")
    except Exception as e:
        st.error(f"❌ Непредвиденная ошибка: {e}")

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