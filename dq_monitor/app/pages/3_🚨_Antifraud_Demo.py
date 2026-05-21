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

# Глобальные стили Arial 15/22
st.markdown("""<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; }
    .stMetric label { font-size: 15px !important; }
</style>""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ АНТИФРОД-РАСЧЕТОВ ---
@st.cache_data(show_spinner="Запуск антифрод-движка (это может занять время)...")
def get_cached_antifraud_results(df_dirty, df_clean, labels):
    """
    Прогоняет правила на обоих датасетах и считает метрики.
    Кешируется, чтобы не пересчитывать 'Карусель' при каждом клике.
    """
    engine = RuleEngine()

    # 1. Прогон правил
    df_dirty_pred, _ = engine.run_all(df_dirty)
    df_clean_pred, _ = engine.run_all(df_clean)

    # 2. Склейка с эталоном (Ground Truth)
    merged_dirty = attach_ground_truth(df_dirty_pred, labels)
    merged_clean = attach_ground_truth(df_clean_pred, labels)

    # 3. Расчет матриц ошибок
    cm_dirty = compute_confusion_matrix(merged_dirty["is_fraud_predicted"], merged_dirty["is_fraud_real"])
    cm_clean = compute_confusion_matrix(merged_clean["is_fraud_predicted"], merged_clean["is_fraud_real"])

    # 4. Сравнение
    comp_results = compare(cm_dirty, cm_clean)

    return cm_dirty, cm_clean, comp_results


st.title("🚨 Antifraud Demo: Влияние качества данных на детекцию")

# Проверка наличия данных
if "df_dirty" not in st.session_state or "df_clean" not in st.session_state:
    st.warning("Для демонстрации нужны оба датасета. Пожалуйста, выполните очистку на странице Cleaning.")
    st.stop()

# --- БЛОК 1: ЗАГРУЗКА ЭТАЛОНА ---
st.subheader("1. Загрузка эталонных меток (Fraud Labels)")
labels_file = st.file_uploader("Загрузите файл fraud_labels.csv (от ментора)", type=["csv"])

if labels_file is None:
    st.info("💡 Нет файла? Нажмите кнопку для генерации тестовых меток (имитация 5% фрода).")
    if st.button("Сгенерировать демо-метки"):
        ids = st.session_state["df_dirty"]['event_id'].unique()
        st.session_state["mock_labels"] = pd.DataFrame({
            'event_id': ids,
            'is_fraud_real': [hash(str(i)) % 20 == 0 for i in ids]
        })

    if "mock_labels" not in st.session_state: st.stop()
    labels = st.session_state["mock_labels"]
else:
    labels = pd.read_csv(labels_file)

# --- БЛОК 2: РАСЧЕТЫ ---
cm_dirty, cm_clean, comp = get_cached_antifraud_results(
    st.session_state["df_dirty"],
    st.session_state["df_clean"],
    labels
)

# --- БЛОК 3: БИЗНЕС-МЕТРИКИ ---
st.header("2. Сравнительная эффективность")

# Расчет "спасенных" денег (TP * средний чек фрода 85к)
delta_tp = comp["delta"]["tp"]
money_saved = delta_tp * 85000

m1, m2, m3, m4 = st.columns(4)
m1.metric("Доп. поймано фрода", f"+{delta_tp} шт")
m2.metric("Снижение пропусков", f"{comp['delta']['fn']} шт", delta_color="inverse")
m3.metric("Прирост Recall", f"+{comp['delta']['recall_pp']}%")
m4.metric("DQ Profit (прогноз)", f"{money_saved:,.0f} ₽", delta="RUB")

st.divider()

# --- БЛОК 4: МАТРИЦЫ side-by-side ---
col_l, col_r = st.columns(2)

with col_l:
    # plot_confusion_matrix берется из вашего обновленного viz.py
    st.plotly_chart(plot_confusion_matrix(cm_dirty.to_dict(), "Грязные данные (Система 'слепа')"),
                    use_container_width=True)
    st.caption("⚠️ Из-за ошибок в MCC (цифры) и пропусков в суммах, правила не могут идентифицировать часть фрода.")

with col_r:
    st.plotly_chart(plot_confusion_matrix(cm_clean.to_dict(), "Очищенные данные (Система 'видит')"),
                    use_container_width=True)
    st.caption("✅ После очистки (восстановление MCC, сумм и дат) те же самые правила работают эффективнее.")

st.divider()

# --- БЛОК 5: ВЫВОД ДЛЯ ЗАЩИТЫ ---
st.success(f"""
### Главный вывод:
Повышение качества данных позволило обнаружить на **{delta_tp}** инцидентов больше. 
Это доказывает: **Data Quality — это не просто порядок в таблицах, а реальные деньги банка**, 
которые мы теряем, когда система «не видит» фрод из-за грязных входных данных.
""")