"""
Метрики качества обнаружения фрода. Этот модуль вам УЖЕ дан готовым —
математика confusion matrix должна быть одинаковой у всех, чтобы цифры
на защите были корректные.

Используйте отсюда:
  compute_confusion_matrix(predictions, labels) -> ConfusionMatrix
  attach_ground_truth(df_predicted, fraud_labels)  -> df с is_fraud_real
  evaluate_on_cohort(df_pred, fraud_labels, cohort) -> честная оценка на фикс. когорте
  compute_newly_caught_fraud(eval_dirty, eval_clean) -> сколько фрода реально допоймали
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

    Если event_id из предсказаний нет в labels, считаем is_fraud_real=False.
    Для сравнения dirty vs clean после удаления строк используйте evaluate_on_cohort.
    """
    merged = df_with_predictions.merge(fraud_labels, on="event_id", how="left")
    merged["is_fraud_real"] = merged["is_fraud_real"].fillna(False).astype(bool)
    return merged


def evaluate_on_cohort(
    df_with_predictions: pd.DataFrame,
    fraud_labels: pd.DataFrame,
    cohort_event_ids: Sequence,
) -> pd.DataFrame:
    """Оценить предсказания на фиксированной когорте event_id.

    Нужно для честного сравнения до/после очистки: удалённые строки остаются
    в когорте, is_fraud_predicted для них = False (правила не сработали на
    отсутствующей строке), is_fraud_real берётся из fraud_labels.

    Args:
        df_with_predictions: DataFrame с event_id и is_fraud_predicted.
        fraud_labels: эталон с event_id и is_fraud_real.
        cohort_event_ids: фиксированный набор id (обычно все event_id из dirty).

    Returns:
        DataFrame с колонками event_id, is_fraud_predicted, is_fraud_real.
    """
    cohort = pd.DataFrame({"event_id": pd.unique(pd.Series(cohort_event_ids))})
    labels = (
        fraud_labels[["event_id", "is_fraud_real"]]
        .drop_duplicates(subset="event_id", keep="first")
    )
    out = cohort.merge(labels, on="event_id", how="left")
    out["is_fraud_real"] = out["is_fraud_real"].fillna(False).astype(bool)

    pred_cols = ["event_id", "is_fraud_predicted"]
    pred = df_with_predictions[pred_cols].drop_duplicates(subset="event_id", keep="first")
    out = out.merge(pred, on="event_id", how="left")
    out["is_fraud_predicted"] = out["is_fraud_predicted"].fillna(False).astype(bool)
    return out


def compute_newly_caught_fraud(
    eval_before: pd.DataFrame,
    eval_after: pd.DataFrame,
) -> int:
    """Сколько fraud-событий перешли из пропуска (FN) в детекцию (TP) на одной когорте."""
    before = eval_before[["event_id", "is_fraud_predicted", "is_fraud_real"]].rename(
        columns={"is_fraud_predicted": "pred_before"}
    )
    after = eval_after[["event_id", "is_fraud_predicted"]].rename(
        columns={"is_fraud_predicted": "pred_after"}
    )
    merged = before.merge(after, on="event_id", how="inner")
    mask = (
        merged["is_fraud_real"]
        & ~merged["pred_before"].astype(bool)
        & merged["pred_after"].astype(bool)
    )
    return int(mask.sum())


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
