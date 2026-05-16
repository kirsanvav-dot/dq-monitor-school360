"""
Профилирование данных: поиск DQ-проблем по 4 измерениям качества.

🔲 ЭТО ОСНОВНОЙ МОДУЛЬ КОМАНДЫ DQ ANALYST.

В этом файле — только контракты (dataclass'ы и сигнатуры).
Реализацию пишете сами.

Контракты — это API, который ожидают:
  - Streamlit-страница DQ Report
  - DataCleaner (использует DQReport, чтобы понимать, что чистить)
  - dq_scorer (считает скоры на основе issues из DQReport)

Не меняйте имена и сигнатуры публичных классов/методов — иначе
интеграция с приложением сломается. Внутреннюю реализацию можно
делать как угодно: добавлять приватные методы, кешировать, и т.п.

4 измерения качества:
  Completeness — есть ли значения в обязательных полях
  Validity     — соответствуют ли значения ожидаемому формату/диапазону
  Consistency  — согласованы ли поля между собой (cross-field логика)
  Uniqueness   — нет ли дубликатов
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

import pandas as pd


Dimension = Literal["completeness", "validity", "consistency", "uniqueness"]
Severity = Literal["low", "medium", "high"]


@dataclass
class DQIssue:
    """Одна найденная DQ-проблема.

    Attributes:
        issue_type: короткий машиночитаемый id, напр. 'missing_client_id'.
        description: человеко-читаемое описание для отчёта.
        dimension: к какому из 4 измерений относится.
        column: затронутое поле (или 'multiple' для cross-field проблем).
        rows_affected: сколько строк затронуто.
        severity: приоритет для дата-инженеров.
        examples: 3-5 примеров значений-нарушителей (опционально, для UI).
    """
    issue_type: str
    description: str
    dimension: Dimension
    column: str
    rows_affected: int
    severity: Severity
    examples: list = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DQReport:
    """Сводный отчёт по всем найденным проблемам."""
    issues: list[DQIssue]
    total_rows: int

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    def by_dimension(self) -> dict[str, int]:
        """Сколько issues по каждому измерению. Используется для UI."""
        counts = {"completeness": 0, "validity": 0, "consistency": 0, "uniqueness": 0}
        for issue in self.issues:
            counts[issue.dimension] += 1
        return counts

    def to_dataframe(self) -> pd.DataFrame:
        """Удобно для отображения в st.dataframe и для plot_issues_breakdown."""
        if not self.issues:
            return pd.DataFrame(columns=[
                "issue_type", "description", "dimension", "column",
                "rows_affected", "severity",
            ])
        return pd.DataFrame([
            {k: v for k, v in issue.to_dict().items() if k != "examples"}
            for issue in self.issues
        ])


class DataProfiler:
    """Профайлер: запускает проверки и собирает DQReport.

    Использование (контракт публичного API — не меняйте):
        profiler = DataProfiler()
        report = profiler.profile(df)

    Внутри метода profile() вызывайте свои проверки. Как именно их
    организовать (по методу на измерение / по методу на проблему /
    через реестр) — решаете сами.
    """

    def profile(self, df: pd.DataFrame) -> DQReport:
        """Прогнать все проверки и собрать DQReport.

        Returns:
            DQReport со списком всех найденных проблем.
        """
        # TODO команде:
        #   1. Реализовать проверки по 4 измерениям. В датасете
        #      11 типов закладок — вам предстоит их найти.
        #   2. Каждая найденная проблема -> DQIssue.
        #   3. Все DQIssue -> DQReport(issues=[...], total_rows=len(df)).
        #
        # Подсказка по архитектуре:
        # Один из подходов — отдельные методы:
        #     check_completeness(df) -> list[DQIssue]
        #     check_validity(df)     -> list[DQIssue]
        #     check_consistency(df)  -> list[DQIssue]
        #     check_uniqueness(df)   -> list[DQIssue]
        # Затем в profile() собираете результаты всех методов.
        # Но можно сделать и через реестр функций, и через subclass'ы —
        # как удобнее команде.
        raise NotImplementedError(
            "DataProfiler.profile не реализован. "
            "Прочитайте docstring класса и реализуйте проверки по 4 измерениям."
        )
