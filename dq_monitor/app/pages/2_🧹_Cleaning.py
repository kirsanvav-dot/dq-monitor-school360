"""Cleaning — настройка и запуск пайплайна очистки.

🔲 Эта страница ждёт, пока Backend + DQ Analyst реализуют src/cleaner.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="Cleaning", page_icon="🧹", layout="wide")
st.title("🧹 Cleaning")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()

st.info("""
🔲 **Страница ждёт реализации пайплайна очистки.**

Что нужно сделать (Backend + DQ Analyst):
1. Реализовать `DataCleaner` и `CleaningConfig` в `src/cleaner.py`
2. Реализовать `compute_dq_score` для пересчёта DQ-score после очистки

Что должно быть на странице:
- Чекбоксы для каждого правила очистки (вкл/выкл)
- Кнопка «Запустить очистку»
- После запуска: лог по шагам (что удалилось, что исправилось),
  DQ-score до/после, график сравнения
- Сохранение очищенного df в `st.session_state["df_clean"]` для
  следующей страницы

Структура кода — см. шаблон в комментариях этого файла:

```python
from src.cleaner import DataCleaner, CleaningConfig
from src.viz import plot_dq_score_comparison

df_dirty = st.session_state["df_dirty"]

# Сборка config из чекбоксов
cfg_remove_duplicates = st.checkbox("Удалить дубликаты", value=True)
# ... другие чекбоксы

config = CleaningConfig(remove_duplicates=cfg_remove_duplicates, ...)

if st.button("Запустить очистку"):
    cleaner = DataCleaner()
    df_clean, log = cleaner.clean(df_dirty, config)
    st.session_state["df_clean"] = df_clean
    # Показать лог, метрики, графики
```
""")
