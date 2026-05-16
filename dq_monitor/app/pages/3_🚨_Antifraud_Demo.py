"""Antifraud Demo — главное шоу для защиты: side-by-side dirty vs clean.

🔲 Эта страница ждёт реализации src/antifraud_rules.py + готовой очистки.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="Antifraud Demo", page_icon="🚨", layout="wide")
st.title("🚨 Antifraud Demo — влияние качества данных на детекцию фрода")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()
if "df_clean" not in st.session_state:
    st.warning("Сначала запустите очистку на странице Cleaning.")
    st.stop()

st.info("""
🔲 **Страница ждёт реализации антифрод-движка.**

Это **главная сцена защиты** — здесь вы покажете жюри две confusion matrix
рядом: на грязных и чистых данных, и разницу в количестве пойманного фрода.

Что нужно сделать (Antifraud Engineer):
1. Реализовать `RuleEngine` в `src/antifraud_rules.py`
2. Получить от ментора `fraud_labels.csv` (день 6 — 22 мая)
3. Раскомментировать код страницы

Шаблон того, что должно быть:

```python
from src.antifraud_rules import RuleEngine
from src.data_loader import load_fraud_labels
from src.metrics import compute_confusion_matrix, attach_ground_truth, compare
from src.viz import plot_confusion_matrix

# 1. Загрузка ground truth (от ментора)
labels_upload = st.file_uploader("Загрузите fraud_labels.csv", type=["csv"])
if labels_upload:
    labels = load_fraud_labels(labels_upload)

# 2. Прогон правил на dirty и clean
engine = RuleEngine()
df_dirty_pred, _ = engine.run_all(st.session_state["df_dirty"])
df_clean_pred, _ = engine.run_all(st.session_state["df_clean"])

# 3. Confusion matrix через готовый metrics.py
merged_dirty = attach_ground_truth(df_dirty_pred, labels)
merged_clean = attach_ground_truth(df_clean_pred, labels)
cm_dirty = compute_confusion_matrix(
    merged_dirty["is_fraud_predicted"], merged_dirty["is_fraud_real"])
cm_clean = compute_confusion_matrix(
    merged_clean["is_fraud_predicted"], merged_clean["is_fraud_real"])

# 4. Side-by-side визуализация
c1, c2 = st.columns(2)
c1.plotly_chart(plot_confusion_matrix(cm_dirty.to_dict(), "Грязные данные"))
c2.plotly_chart(plot_confusion_matrix(cm_clean.to_dict(), "Чистые данные"))

# 5. Главная цифра защиты
comp = compare(cm_dirty, cm_clean)
extra_caught = comp["delta"]["tp"]
st.success(f"+{extra_caught} пойманных фродов ≈ {extra_caught * 85_000:,.0f} ₽")
```
""")
