import sys
import streamlit as st
import pandas as pd
from pathlib import Path

# --- ИСПРАВЛЕНИЕ ПУТЕЙ ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.antifraud_rules import RuleEngine
from src.metrics import compute_confusion_matrix, attach_ground_truth, compare
from src.viz import plot_confusion_matrix

st.set_page_config(page_title="Antifraud Demo", page_icon="🚨", layout="wide")

# Глобальные стили Arial + Центрирование
st.markdown("""<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; }
    .stMetric label { font-size: 15px !important; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { text-align: center !important; }
</style>""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ ---
@st.cache_data(show_spinner="Запуск антифрод-анализа...")
def get_full_antifraud_analysis(df_dirty, df_clean, labels):
    engine = RuleEngine()
    df_dirty_pred, r_dirty = engine.run_all(df_dirty)
    df_clean_pred, r_clean = engine.run_all(df_clean)

    merged_dirty = attach_ground_truth(df_dirty_pred, labels)
    merged_clean = attach_ground_truth(df_clean_pred, labels)

    cm_dirty = compute_confusion_matrix(merged_dirty["is_fraud_predicted"], merged_dirty["is_fraud_real"])
    cm_clean = compute_confusion_matrix(merged_clean["is_fraud_predicted"], merged_clean["is_fraud_real"])

    return cm_dirty, cm_clean, compare(cm_dirty, cm_clean), r_dirty, r_clean


st.title("🚨 Antifraud Demo: Влияние качества данных")

if "df_dirty" not in st.session_state or "df_clean" not in st.session_state:
    st.warning("Сначала загрузите датасет и выполните очистку на странице Cleaning.")
    st.stop()

# --- БЛОК 1: ВЫБОР ИСТОЧНИКА МЕТОК (БЕЗ АВТОМАТИКИ) ---
st.subheader("1. Подготовка эталонных меток (Ground Truth)")

col_source_1, col_source_2 = st.columns(2)
labels = None
mode_label = ""

with col_source_1:
    st.write("**Вариант А: Реальный аудит**")
    labels_file = st.file_uploader("Загрузите fraud_labels.csv", type=["csv"], key="real_labels")
    if labels_file:
        labels = pd.read_csv(labels_file)
        mode_label = "📂 Режим: Загруженный файл"

with col_source_2:
    st.write("**Вариант Б: Демонстрация**")
    st.write("Если у вас нет файла, используйте имитацию фрода на основе текущих данных.")
    if st.button("Сгенерировать демо-метки"):
        ids = st.session_state["df_dirty"]['event_id'].unique()
        # Имитируем: каждый 20-й — фрод (стабильный результат через hash)
        st.session_state["mock_labels_data"] = pd.DataFrame({
            'event_id': ids,
            'is_fraud_real': [hash(str(i)) % 20 == 0 for i in ids]
        })
        st.success("Демо-метки созданы!")

# Проверка, что метки выбраны
if labels is None:
    if "mock_labels_data" in st.session_state:
        labels = st.session_state["mock_labels_data"]
        mode_label = "🧪 Режим: Демонстрационные метки"
    else:
        st.info("👈 Загрузите файл с метками или нажмите кнопку «Сгенерировать демо-метки», чтобы начать анализ.")
        st.stop()

# Индикатор активного режима
st.info(f"**{mode_label}**")

# --- БЛОК 2: РАСЧЕТЫ ---
cm_dirty, cm_clean, comp, r_dirty, r_clean = get_full_antifraud_analysis(
    st.session_state["df_dirty"],
    st.session_state["df_clean"],
    labels
)

# --- БЛОК 3: БИЗНЕС-МЕТРИКИ ---
st.header("2. Сравнение эффективности системы")

# Абсолютное снижение пропусков (FN) – положительная величина
fn_reduction = -comp["delta"]["fn"]   # т.к. delta["fn"] = FN_after - FN_before < 0 при улучшении

# Общая экономия = (доп. пойманные TP + переставшие пропускаться FN) × стоимость одного фрода
total_frauds_prevented = comp["delta"]["tp"] + fn_reduction
money_saved = total_frauds_prevented * 85000

m1, m2, m3, m4 = st.columns(4)
m1.metric("Доп. поймано фрода", f"+{comp['delta']['tp']} шт")
m2.metric("Снижение пропусков", f"{fn_reduction} шт", delta_color="normal")   # теперь положительное число
m3.metric("Прирост Recall", f"+{comp['delta']['recall_pp']}%")
m4.metric("Экономия (прогноз)", f"{money_saved:,.0f} ₽", delta="Profit")

st.divider()

# --- БЛОК 4: СВОДНАЯ ТАБЛИЦА МЕТРИК ---
st.subheader("📊 Сравнение ключевых метрик детекции")
metrics_comp = pd.DataFrame([
    {
        "Метрика": "Precision (Точность)",
        "Грязные данные": f"{comp['before']['precision']:.2%}",
        "После очистки": f"{comp['after']['precision']:.2%}",
        "Улучшение": f"+{comp['delta']['precision_pp']}%"
    },
    {
        "Метрика": "Recall (Полнота)",
        "Грязные данные": f"{comp['before']['recall']:.2%}",
        "После очистки": f"{comp['after']['recall']:.2%}",
        "Улучшение": f"+{comp['delta']['recall_pp']}%"
    },
    {
        "Метрика": "F1-Score (Баланс)",
        "Грязные данные": f"{comp['before']['f1']:.3f}",
        "После очистки": f"{comp['after']['f1']:.3f}",
        "Улучшение": f"+{comp['delta']['f1_pp']}%"
    }
])
metrics_comp.index = range(1, len(metrics_comp) + 1)
st.table(metrics_comp.style.set_properties(**{'text-align': 'center'}))

# --- БЛОК 5: МАТРИЦЫ ---
c_l, c_r = st.columns(2)
with c_l:
    st.plotly_chart(plot_confusion_matrix(cm_dirty.to_dict(), "Матрица: Грязные данные"), use_container_width=True)
with c_r:
    st.plotly_chart(plot_confusion_matrix(cm_clean.to_dict(), "Матрица: Чистые данные"), use_container_width=True)

st.divider()

# --- БЛОК 6: АНАЛИЗ ПРАВИЛ ---
st.subheader("⚙️ Эффективность работы правил")

rules_dirty_df = pd.DataFrame(r_dirty).set_index('rule_id')
rules_clean_df = pd.DataFrame(r_clean).set_index('rule_id')

rules_comp = pd.DataFrame({
    "Название правила": rules_dirty_df['name'],
    "Сработок (Dirty)": rules_dirty_df['triggered_count'],
    "Сработок (Clean)": rules_clean_df['triggered_count'],
    "Дельта": rules_clean_df['triggered_count'] - rules_dirty_df['triggered_count']
}).reset_index()

rules_comp.index = range(1, len(rules_comp) + 1)
st.table(rules_comp.style.set_properties(**{'text-align': 'center'}))

st.success(f"""
### Итог для защиты:
Очистка данных позволила антифрод-системе работать эффективнее: F1-мера выросла на **{comp['delta']['f1_pp']}%**. 
Мы доказали на цифрах: **Data Quality напрямую влияет на безопасность банка**.
""")