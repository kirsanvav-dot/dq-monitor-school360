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
@st.cache_data(show_spinner="Запуск антифрод-анализа и расчет финансовых метрик...")
def get_full_antifraud_analysis(df_dirty, df_clean, labels):
    engine = RuleEngine()

    # Прогон правил
    df_dirty_pred, r_dirty = engine.run_all(df_dirty)
    df_clean_pred, r_clean = engine.run_all(df_clean)

    # Склейка с метками
    merged_dirty = attach_ground_truth(df_dirty_pred, labels)
    merged_clean = attach_ground_truth(df_clean_pred, labels)
    st.session_state["merged_clean"] = merged_clean
    st.session_state["merged_dirty"] = merged_dirty

    # Расчет матриц
    cm_dirty = compute_confusion_matrix(merged_dirty["is_fraud_predicted"], merged_dirty["is_fraud_real"])
    cm_clean = compute_confusion_matrix(merged_clean["is_fraud_predicted"], merged_clean["is_fraud_real"])

    # --- ЧЕСТНЫЙ РАСЧЕТ ЭКОНОМИИ ПО ЕДИНОЙ БАЗЕ СУММ ---

    # 1. Формируем "справочник" правильных сумм из чистого датасета.
    # Дропаем дубликаты event_id (на всякий случай, чтобы set_index не упал)
    clean_unique = df_clean.drop_duplicates(subset=['event_id']).copy()
    clean_amounts = clean_unique.set_index('event_id')['amount_rub'].copy()
    clean_amounts = pd.to_numeric(clean_amounts, errors='coerce').fillna(0)

    # 2. Находим event_id тех транзакций, которые система пропустила (FN) ДО очистки
    fn_dirty_mask = (~merged_dirty["is_fraud_predicted"].fillna(False).astype(bool)) & (merged_dirty["is_fraud_real"])
    fn_dirty_events = merged_dirty.loc[fn_dirty_mask, "event_id"].dropna().unique()

    # 3. Находим event_id тех транзакций, которые система пропустила (FN) ПОСЛЕ очистки
    fn_clean_mask = (~merged_clean["is_fraud_predicted"].fillna(False).astype(bool)) & (merged_clean["is_fraud_real"])
    fn_clean_events = merged_clean.loc[fn_clean_mask, "event_id"].dropna().unique()

    # 4. Считаем финансовые потери, используя ТОЛЬКО ПРАВИЛЬНЫЕ суммы из clean_amounts
    # Метод .reindex() безопасно сопоставляет список event_id с нашим справочником сумм
    loss_dirty = clean_amounts.reindex(fn_dirty_events).fillna(0).sum()
    loss_clean = clean_amounts.reindex(fn_clean_events).fillna(0).sum()

    # 5. Итоговая честная экономия
    exact_money_saved = loss_dirty - loss_clean

    return cm_dirty, cm_clean, compare(cm_dirty, cm_clean), r_dirty, r_clean, exact_money_saved


st.title("🚨 Antifraud Demo: Влияние качества данных")

if "df_dirty" not in st.session_state or "df_clean" not in st.session_state:
    st.warning("Сначала загрузите датасет и выполните очистку на странице Cleaning.")
    st.stop()

# --- БЛОК 1: ВЫБОР ИСТОЧНИКА МЕТОК ---
st.subheader("1. Подготовка эталонных меток (Ground Truth)")

col_source_1, col_source_2 = st.columns(2)
labels = None
mode_label = ""

with col_source_1:
    st.write("**Вариант А: Реальный аудит**")
    labels_file = st.file_uploader("Загрузите fraud_labels.csv", type=["csv"], key="real_labels")
    if labels_file:
        st.session_state["labels_data"] = pd.read_csv(labels_file)
        columns = st.session_state["labels_data"].columns
        if "is_fraud_real" not in columns or "event_id" not in columns:
            st.warning("Necessary columns are abscent")
            st.session_state.pop("labels_data")

with col_source_2:
    st.write("**Вариант Б: Демонстрация**")
    st.write("Если у вас нет файла, используйте имитацию фрода на основе текущих данных.")
    if st.button("Сгенерировать демо-метки"):
        if "labels_data" in st.session_state:
            st.session_state.pop("labels_data")
        ids = st.session_state["df_dirty"]['event_id'].unique()
        # Имитируем: каждый 20-й — фрод
        st.session_state["mock_labels_data"] = pd.DataFrame({
            'event_id': ids,
            'is_fraud_real': [hash(str(i)) % 20 == 0 for i in ids]
        })
        st.success("Демо-метки созданы!")

# Проверка, что метки выбраны
if "labels_data" not in st.session_state:
    if "mock_labels_data" in st.session_state:
        labels = st.session_state["mock_labels_data"]
        mode_label = "🧪 Режим: Демонстрационные метки"
    else:
        st.info("👈 Загрузите файл с метками или нажмите кнопку «Сгенерировать демо-метки», чтобы начать анализ.")
        st.stop()
else:
    labels = st.session_state["labels_data"]
    mode_label = "📂 Режим: Загруженный файл"

st.info(f"**{mode_label}**")

# --- БЛОК 2: РАСЧЕТЫ ---
cm_dirty, cm_clean, comp, r_dirty, r_clean, money_saved = get_full_antifraud_analysis(
    st.session_state["df_dirty"],
    st.session_state["df_clean"],
    labels
)

# --- БЛОК 3: БИЗНЕС-МЕТРИКИ ---
st.header("2. Сравнение эффективности системы")

fn_reduction = -comp["delta"]["fn"]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Доп. поймано фрода", f"+{comp['delta']['tp']} шт")
m2.metric("Снижение пропусков", f"{fn_reduction} шт", delta_color="normal")
m3.metric("Прирост Recall", f"+{comp['delta']['recall_pp']}%")
m4.metric(
    "Экономия (точный расчет)",
    f"{money_saved:,.0f} ₽",
    delta="Profit",
    help="Считается как разница между финансовыми потерями (сумма всех пропущенных мошеннических транзакций) до и после очистки данных."
)

st.divider()

# --- БЛОК 4: СВОДНАЯ ТАБЛИЦА МЕТРИК ---
st.subheader("📊 Сравнение ключевых метрик детекции")

# Вспомогательная функция для форматирования дельты
def format_delta(val):
    if val > 0:
        return f"+{val}%"
    elif val < 0:
        return f"{val}%" # Минус уже встроен в само число
    else:
        return "0%"

metrics_comp = pd.DataFrame([
    {
        "Метрика": "Precision (Точность)",
        "Грязные данные": f"{comp['before']['precision']:.2%}",
        "После очистки": f"{comp['after']['precision']:.2%}",
        "Улучшение": format_delta(comp['delta']['precision_pp'])
    },
    {
        "Метрика": "Recall (Полнота)",
        "Грязные данные": f"{comp['before']['recall']:.2%}",
        "После очистки": f"{comp['after']['recall']:.2%}",
        "Улучшение": format_delta(comp['delta']['recall_pp'])
    },
    {
        "Метрика": "F1-Score (Баланс)",
        "Грязные данные": f"{comp['before']['f1']:.3f}",
        "После очистки": f"{comp['after']['f1']:.3f}",
        "Улучшение": format_delta(comp['delta']['f1_pp'])
    },
    {
        "Метрика": "Accuracy (Аккуратность)", # Вернули Accuracy
        "Грязные данные": f"{comp['before']['accuracy']:.2%}",
        "После очистки": f"{comp['after']['accuracy']:.2%}",
        "Улучшение": "---" # Accuracy обычно не сравнивают дельтой при дисбалансе
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

