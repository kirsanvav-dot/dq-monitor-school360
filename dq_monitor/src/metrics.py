"""
Метрики качества обнаружения фрода. Этот модуль вам УЖЕ дан готовым —
математика confusion matrix должна быть одинаковой у всех, чтобы цифры
на защите были корректные.

Используйте отсюда:
  compute_confusion_matrix(predictions, labels) -> ConfusionMatrix
  attach_ground_truth(df_predicted, fraud_labels)  -> df с is_fraud_real
  compare(cm_dirty, cm_clean)                       -> dict со сравнением

Изучите код как образец dataclass'ов — это удобный паттерн для других
ваших модулей.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Sequence

import pandas as pd


@dataclass
class ConfusionMatrix:
    """Confusion matrix + производные метрики.

    Attributes:
        tp: True Positive  — правило сработало, и это правда фрод.
        fp: False Positive — правило сработало, но это не фрод (ложная тревога).
        fn: False Negative — правило не сработало, а это был фрод (пропустили).
        tn: True Negative  — правило не сработало, и это не фрод.
    """
    tp: int
    fp: int
    fn: int
    tn: int

    @property
    def precision(self) -> float:
        """Из тех, кого правило отметило — какая доля действительно фрод."""
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        """Из всего реального фрода — какую долю правило поймало."""
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        """Гармоническое среднее precision и recall."""
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def accuracy(self) -> float:
        """Доля правильных предсказаний. На дисбалансе классов бесполезна."""
        total = self.tp + self.fp + self.fn + self.tn
        return (self.tp + self.tn) / total if total else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update({
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "accuracy": round(self.accuracy, 4),
        })
        return d


def compute_confusion_matrix(
    predictions: Sequence[bool],
    labels: Sequence[bool],
) -> ConfusionMatrix:
    """Посчитать confusion matrix из двух булевых последовательностей.

    Args:
        predictions: что предсказала команда правил (is_fraud_predicted).
        labels: ground truth (is_fraud_real).

    Returns:
        ConfusionMatrix.

    Raises:
        ValueError: если длины не совпадают.
    """
    if len(predictions) != len(labels):
        raise ValueError(
            f"Длины не совпадают: predictions={len(predictions)}, labels={len(labels)}"
        )
    pred = pd.Series(predictions).fillna(False).astype(bool)
    real = pd.Series(labels).fillna(False).astype(bool)
    tp = int((pred & real).sum())
    fp = int((pred & ~real).sum())
    fn = int((~pred & real).sum())
    tn = int((~pred & ~real).sum())
    return ConfusionMatrix(tp=tp, fp=fp, fn=fn, tn=tn)


def attach_ground_truth(
    df_with_predictions: pd.DataFrame,
    fraud_labels: pd.DataFrame,
) -> pd.DataFrame:
    """Приклеить ground truth к предсказаниям по event_id.

    Если event_id в предсказаниях нет в labels (например, очистка
    удалила строку), считаем is_fraud_real=False.
    """
    # В clean CSV иногда есть is_fraud_real — без drop merge даст _x/_y и KeyError.
    df_pred = df_with_predictions.drop(columns=["is_fraud_real"], errors="ignore")
    labels = fraud_labels[["event_id", "is_fraud_real"]].copy()
    merged = df_pred.merge(labels, on="event_id", how="left")
    merged["is_fraud_real"] = merged["is_fraud_real"].fillna(False).astype(bool)
    return merged


def compare(before: ConfusionMatrix, after: ConfusionMatrix) -> dict:
    """Сформировать структуру сравнения dirty vs clean для UI и слайдов.

    Возвращает разницу в абсолютных значениях и процентных пунктах —
    готовый материал для слайдов защиты.
    """
    return {
        "before": before.to_dict(),
        "after": after.to_dict(),
        "delta": {
            "tp": after.tp - before.tp,
            "fp": after.fp - before.fp,
            "fn": after.fn - before.fn,
            "tn": after.tn - before.tn,
            "precision_pp": round((after.precision - before.precision) * 100, 2),
            "recall_pp": round((after.recall - before.recall) * 100, 2),
            "f1_pp": round((after.f1 - before.f1) * 100, 2),
        },
    }
