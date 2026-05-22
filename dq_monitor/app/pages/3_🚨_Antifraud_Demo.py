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

# Глобальные стили Arial + Центрирование ячеек
st.markdown("""<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; }
    .stMetric label { font-size: 15px !important; }
    [data-testid="stTable"] td, [data-testid="stTable"] th { text-align: center !important; }
</style>""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ: используем всю мощь metrics.py ---
@st.cache_data(show_spinner="Запуск антифрод-анализа...")
def get_full_antifraud_analysis(df_dirty, df_clean, labels):
    engine = RuleEngine()

    # 1. Прогон правил
    df_dirty_pred, rules_info_dirty = engine.run_all(df_dirty)
    df_clean_pred, rules_info_clean = engine.run_all(df_clean)

    # 2. Склейка с Ground Truth (is_fraud_real)
    merged_dirty = attach_ground_truth(df_dirty_pred, labels)
    merged_clean = attach_ground_truth(df_clean_pred, labels)

    # 3. Расчет матриц (объекты ConfusionMatrix)
    cm_dirty = compute_confusion_matrix(merged_dirty["is_fraud_predicted"], merged_dirty["is_fraud_real"])
    cm_clean = compute_confusion_matrix(merged_clean["is_fraud_predicted"], merged_clean["is_fraud_real"])

    # 4. Сравнение через metrics.compare (получаем dict с дельтами)
    comparison_dict = compare(cm_dirty, cm_clean)

    return cm_dirty, cm_clean, comparison_dict, rules_info_dirty, rules_info_clean


st.title("🚨 Antifraud Demo: Влияние качества данных")

if "df_dirty" not in st.session_state or "df_clean" not in st.session_state:
    st.warning("Сначала загрузите датасет и выполните очистку на странице Cleaning.")
    st.stop()

# --- 1. ЗАГРУЗКА МЕТОК ---
st.subheader("1. Загрузка эталонных меток (Ground Truth)")
labels_file = st.file_uploader("Загрузите fraud_labels.csv (от ментора)", type=["csv"])

if labels_file is None:
    if "mock_labels" not in st.session_state:
        ids = st.session_state["df_dirty"]['event_id'].unique()
        st.session_state["mock_labels"] = pd.DataFrame({
            'event_id': ids,
            'is_fraud_real': [hash(str(i)) % 22 == 0 for i in ids]
        })
    labels = st.session_state["mock_labels"]
    st.info("💡 Используются демо-метки.")
else:
    labels = pd.read_csv(labels_file)

# --- 2. РАСЧЕТЫ ---
cm_dirty, cm_clean, comp, r_dirty, r_clean = get_full_antifraud_analysis(
    st.session_state["df_dirty"],
    st.session_state["df_clean"],
    labels
)

# --- 3. ВЕРХНИЕ БИЗНЕС-МЕТРИКИ (Берем данные из comp['delta']) ---
st.header("2. Сравнение эффективности системы")
money_saved = comp["delta"]["tp"] * 85000

m1, m2, m3, m4 = st.columns(4)
m1.metric("Доп. поймано фрода (TP)", f"+{comp['delta']['tp']} шт")
m2.metric("Снижение пропусков (FN)", f"{comp['delta']['fn']} шт", delta_color="inverse")
m3.metric("Прирост Recall", f"+{comp['delta']['recall_pp']}%")
m4.metric("Экономия (прогноз)", f"{money_saved:,.0f} ₽", delta="Profit")

st.divider()

# --- 4. СВОДНАЯ ТАБЛИЦА (Берем данные из comp['before'], comp['after'], comp['delta']) ---
st.subheader("📊 Сравнение метрик детекции")

metrics_data = [
    {
        "Показатель": "Precision (Точность)",
        "Грязные данные": f"{comp['before']['precision']:.2%}",
        "Чистые данные": f"{comp['after']['precision']:.2%}",
        "Улучшение": f"+{comp['delta']['precision_pp']}%"
    },
    {
        "Показатель": "Recall (Полнота)",
        "Грязные данные": f"{comp['before']['recall']:.2%}",
        "Чистые данные": f"{comp['after']['recall']:.2%}",
        "Улучшение": f"+{comp['delta']['recall_pp']}%"
    },
    {
        "Показатель": "F1-Score (Баланс)",
        "Грязные данные": f"{comp['before']['f1']:.3f}",
        "Чистые данные": f"{comp['after']['f1']:.3f}",
        "Улучшение": f"+{comp['delta']['f1_pp']}%"
    },
    {
        "Показатель": "Accuracy (Точность)",
        "Грязные данные": f"{comp['before']['accuracy']:.2%}",
        "Чистые данные": f"{comp['after']['accuracy']:.2%}",
        "Улучшение": "---"
    }
]
df_metrics = pd.DataFrame(metrics_data)
df_metrics.index = range(1, len(df_metrics) + 1)
st.table(df_metrics.style.set_properties(**{'text-align': 'center'}))

# --- 5. МАТРИЦЫ side-by-side ---
c_l, c_r = st.columns(2)
with c_l:
    st.plotly_chart(plot_confusion_matrix(cm_dirty.to_dict(), "Матрица: Грязные данные"), use_container_width=True)
with c_r:
    st.plotly_chart(plot_confusion_matrix(cm_clean.to_dict(), "Матрица: Чистые данные"), use_container_width=True)

st.divider()

# --- 6. АНАЛИЗ ПРАВИЛ ---
st.subheader("⚙️ Эффективность работы правил")

# Склеиваем результаты работы правил из RuleEngine
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
Благодаря очистке данных, F1-мера системы выросла на **{comp['delta']['f1_pp']}%**. 
Мы доказали: высокое качество данных (DQ) позволяет антифрод-правилам работать в полную силу, 
обнаруживая на **{comp['delta']['tp']}** больше инцидентов и сохраняя бюджет банка.
""")