"""
DQ Score: численная оценка качества данных от 0 до 1 по 4 измерениям.

🔲 ЭТОТ МОДУЛЬ ВАШ — DQ ANALYST.

────────────────────────────────────────────────────────────────────
ЧТО МЫ ХОТИМ ПОЛУЧИТЬ

Функция, которая принимает датасет + отчёт профайлера и возвращает
4 числа (по одному на каждое измерение качества) плюс общее total-число.
Каждое число в диапазоне [0, 1], где 1 = идеальные данные, 0 = всё сломано.

────────────────────────────────────────────────────────────────────
ПОДСКАЗКИ ПО ФОРМУЛАМ

Простой вариант для одного измерения:
    score = 1 - (число строк с проблемами этого измерения / всего строк)

Тонкий момент: одна строка может попасть в несколько issues. Если просто
суммировать rows_affected по всем issues одного измерения, можно получить
score < 0. Что делать? Варианты:
  — брать максимум rows_affected среди issues измерения
  — собирать уникальные индексы строк с проблемами
  — взвешивать issues по severity
Команда сама выбирает подход и обосновывает его на защите.

Для uniqueness формула чуть другая: дубликат «затрагивает» 1 лишнюю строку,
а не 2. Подумайте, почему.

────────────────────────────────────────────────────────────────────
КАК ЭТО ИСПОЛЬЗУЕТСЯ В UI

    from src.dq_scorer import compute_dq_score
    score = compute_dq_score(df, report)
    st.metric("Completeness", f"{score.completeness:.3f}")
    st.metric("Total DQ Score", f"{score.total:.3f}")

Проектируйте так, чтобы у возвращаемого объекта были атрибуты
completeness, validity, consistency, uniqueness и свойство total.
"""
import pandas as pd
from dataclasses import dataclass
from src.profiler import Report

@dataclass
class DQScore:
    completeness: float
    validity: float
    consistency: float
    uniqueness: float
    total: float
        
    def to_dict(self) -> dict:
        """Контракт для viz.py (plot_dq_score_radar)"""
        return {
            "completeness": self.completeness,
            "validity": self.validity,
            "consistency": self.consistency,
            "uniqueness": self.uniqueness
        }


def compute_dq_score(df: pd.DataFrame, report: Report) -> DQScore:
    pass