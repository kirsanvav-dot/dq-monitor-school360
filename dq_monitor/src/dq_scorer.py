"""
DQ Score: численная оценка качества данных от 0 до 1 по 4 измерениям.

🔲 ЭТО МОДУЛЬ КОМАНДЫ DQ ANALYST (вместе с profiler.py).

Идея: для каждого измерения возвращаем число от 0 до 1, где 1 = идеал,
0 = всё сломано. Итоговый score — среднее.

Контракт публичного API: функция compute_dq_score(df, report) -> DQScore.
Внутри — реализуете как удобно.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import pandas as pd

from src.profiler import DQReport


@dataclass
class DQScore:
    """Численная оценка качества данных по 4 измерениям + total."""
    completeness: float
    validity: float
    consistency: float
    uniqueness: float

    @property
    def total(self) -> float:
        """Среднее по 4 измерениям. Команда может ввести веса, если обоснует."""
        return (self.completeness + self.validity
                + self.consistency + self.uniqueness) / 4

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total"] = round(self.total, 4)
        for k in ("completeness", "validity", "consistency", "uniqueness"):
            d[k] = round(d[k], 4)
        return d


def compute_dq_score(df: pd.DataFrame, report: DQReport) -> DQScore:
    """Собрать DQScore из датасета и отчёта профайлера.

    Args:
        df: датасет, на котором считаем.
        report: результат DataProfiler.profile(df).

    Returns:
        DQScore.
    """
    # TODO команде: реализовать.
    #
    # Вопросы, на которые нужно ответить и обосновать на защите:
    #   - Как считать score одного измерения? Простой вариант:
    #       1 - (число строк с проблемами / всего строк).
    #     Но: одна строка может попасть в несколько issues — суммировать
    #     rows_affected напрямую = score может стать отрицательным.
    #     Что делать: брать максимум? уникальные строки? Решите.
    #   - Для uniqueness формула немного другая — подумайте, почему дубликат
    #     «затрагивает» 1 строку, а не 2.
    #   - Веса: оставлять равные или давать больший вес completeness/validity?
    #     Аргумент в пользу разных весов — слабая полнота критичнее
    #     для антифрод-правил, чем рассогласование флагов.
    raise NotImplementedError(
        "compute_dq_score не реализован. "
        "Реализуйте подсчёт скоров и обоснуйте выбор формулы."
    )
