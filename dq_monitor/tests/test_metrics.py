"""Тесты для metrics.py — проверка математики confusion matrix."""
import pandas as pd
import pytest

from src.metrics import (
    ConfusionMatrix,
    attach_ground_truth,
    compare,
    compute_confusion_matrix,
)


def test_confusion_matrix_all_correct():
    cm = compute_confusion_matrix(
        predictions=[True, False, True, False],
        labels=[True, False, True, False],
    )
    assert cm.tp == 2 and cm.tn == 2
    assert cm.fp == 0 and cm.fn == 0
    assert cm.precision == 1.0
    assert cm.recall == 1.0
    assert cm.f1 == 1.0


def test_confusion_matrix_all_wrong():
    cm = compute_confusion_matrix(
        predictions=[True, False, True, False],
        labels=[False, True, False, True],
    )
    assert cm.tp == 0 and cm.tn == 0
    assert cm.fp == 2 and cm.fn == 2
    assert cm.precision == 0.0
    assert cm.recall == 0.0
    assert cm.f1 == 0.0


def test_confusion_matrix_mixed():
    # 3 истинных фрода, поймали 2, плюс 1 ложный
    cm = compute_confusion_matrix(
        predictions=[True, True, True, False, False],
        labels=[True, True, False, True, False],
    )
    assert cm.tp == 2
    assert cm.fp == 1
    assert cm.fn == 1
    assert cm.tn == 1
    assert cm.precision == pytest.approx(2 / 3, rel=1e-4)
    assert cm.recall == pytest.approx(2 / 3, rel=1e-4)


def test_confusion_matrix_mismatched_lengths():
    with pytest.raises(ValueError, match="не совпадают"):
        compute_confusion_matrix(predictions=[True], labels=[True, False])


def test_attach_ground_truth_missing_ids_treated_as_not_fraud():
    """Если строки в predictions нет в labels — считаем is_fraud_real=False.

    Это важно: после очистки часть фрода могла быть удалена,
    и это нужно правильно учесть в метриках.
    """
    df_pred = pd.DataFrame({
        "event_id": ["a", "b", "c"],
        "is_fraud_predicted": [True, False, True],
    })
    labels = pd.DataFrame({
        "event_id": ["a", "b"],
        "is_fraud_real": [True, False],
    })
    merged = attach_ground_truth(df_pred, labels)
    assert merged.loc[merged["event_id"] == "c", "is_fraud_real"].iloc[0] == False


def test_compare_returns_proper_deltas():
    before = ConfusionMatrix(tp=10, fp=5, fn=20, tn=100)
    after = ConfusionMatrix(tp=18, fp=2, fn=12, tn=103)
    result = compare(before, after)
    assert result["delta"]["tp"] == 8
    assert result["delta"]["fp"] == -3
    assert result["delta"]["fn"] == -8
    # Recall: до = 10/30 = 0.333, после = 18/30 = 0.6 → +26.67 п.п.
    assert result["delta"]["recall_pp"] == pytest.approx(26.67, abs=0.05)
