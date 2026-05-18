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
from typing import Set, List
from dataclasses import dataclass
from src.profiler import Report
from src.constant_issue import IssueType


ISSUE_COMPLETENESS = [
    # Глобально обязательные поля
    IssueType.EMPTY_EVENT_ID,
    IssueType.EMPTY_CLIENT_ID,
    IssueType.EMPTY_EVENT_TYPE,
    IssueType.EMPTY_EVENT_TS,
    IssueType.EMPTY_DEVICE_TYPE,
    IssueType.EMPTY_IP_ADDRESS,
    IssueType.EMPTY_GEO_COUNTRY,
    IssueType.EMPTY_GEO_CITY,
    IssueType.EMPTY_CHANNEL,
    # Обязательные для транзакций
    IssueType.EMPTY_AMOUNT_RUB,
    IssueType.EMPTY_CURRENCY,
    IssueType.EMPTY_MERCHANT_CATEGORY,
    IssueType.EMPTY_MERCHANT_COUNTRY,
    IssueType.EMPTY_CARD_LAST4,
    # Обязательные для сессий
    IssueType.EMPTY_SESSION_START_TS,
    IssueType.EMPTY_SESSION_END_TS,
    IssueType.EMPTY_LOGIN_SUCCESS,
    IssueType.EMPTY_AUTH_METHOD,
    # Условный
    IssueType.EMPTY_FLAG_REASON,
]
ISSUE_VALIDITY = [
    IssueType.INVALID_EVENT_TYPE,
    IssueType.INVALID_FORMAT_DATE,
    IssueType.INVALID_SESSION_START_TS,
    IssueType.INVALID_SESSION_END_TS,
    IssueType.INVALID_IP_ADDRESS,
    IssueType.INVALID_AMOUNT_RUB,
    IssueType.INVALID_CURRENCY,
    IssueType.INVALID_MERCHANT_CATEGORY,
    IssueType.INVALID_CARD_LAST4,
    IssueType.INVALID_DEVICE_TYPE,
    IssueType.INVALID_GEO_COUNTRY,  # включается, когда geo_country нормализован до ISO-2
    IssueType.INVALID_CHANNEL,
]
ISSUE_CONSISTENCY = [
    IssueType.INCONSISTENCY_FLAGGED,
    IssueType.INCONSISTENCY_TRANSACTION,
    IssueType.INCONSISTENCY_SESSION,
    IssueType.INCONSISTENCY_SESSION_TIMESTAMPS,
]
ISSUE_UNIQUENESS = [
    IssueType.DUPLICATE_FULL,
    IssueType.DUPLICATE_EVENT_ID,
]

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

def get_unique_affected_rows(issues: list, issue_types: List[IssueType]):
    affected_rows = set()
    for issue in issues:
        if issue.issue_type in issue_types:
            for idx in issue.affected_indices:
                affected_rows.add(idx)
    return affected_rows

def calculate_dimension_score(total_rows: int, issues: list, issue_types: List[IssueType]):
    if total_rows == 0:
        return 1.0
    affected_rows = get_unique_affected_rows(issues, issue_types)
    problems_count = len(affected_rows)
    score = 1 - (problems_count / total_rows)
    return score, affected_rows


def compute_dq_score(df: pd.DataFrame, report: Report) -> DQScore:
    total_rows = len(df)
    if total_rows == 0:
        return DQScore(
            completeness=1.0,
            validity=1.0,
            consistency=1.0,
            uniqueness=1.0,
            total=1.0
        )
    issues = report.issues
    completeness_score, completeness_set = calculate_dimension_score(total_rows, issues, ISSUE_COMPLETENESS)
    validity_score, validity_set = calculate_dimension_score(total_rows, issues, ISSUE_VALIDITY)
    consistency_score, consistency_set = calculate_dimension_score(total_rows, issues, ISSUE_CONSISTENCY)
    uniqueness_score, uniqueness_set = calculate_dimension_score(total_rows, issues, ISSUE_UNIQUENESS)
    total_set = consistency_set | validity_set | completeness_set | uniqueness_set
    total_score = 1 - (len(total_set) / total_rows)
    return DQScore(
        completeness=completeness_score,
        validity=validity_score,
        consistency=consistency_score,
        uniqueness=uniqueness_score,
        total=total_score
    )