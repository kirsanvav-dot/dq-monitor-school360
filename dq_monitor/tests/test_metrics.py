"""Тесты для готового metrics.py."""
import pandas as pd
import pytest

from src.metrics import (
    ConfusionMatrix, attach_ground_truth, compare, compute_confusion_matrix,
)


def test_confusion_matrix_all_correct():
    cm = compute_confusion_matrix([True, False, True, False], [True, False, True, False])
    assert cm.tp == 2 and cm.tn == 2 and cm.fp == 0 and cm.fn == 0
    assert cm.precision == 1.0 and cm.recall == 1.0 and cm.f1 == 1.0


def test_confusion_matrix_all_wrong():
    cm = compute_confusion_matrix([True, False, True, False], [False, True, False, True])
    assert cm.tp == 0 and cm.tn == 0 and cm.fp == 2 and cm.fn == 2


def test_confusion_matrix_mixed():
    cm = compute_confusion_matrix(
        [True, True, True, False, False], [True, True, False, True, False])
    assert cm.tp == 2 and cm.fp == 1 and cm.fn == 1 and cm.tn == 1
    assert cm.precision == pytest.approx(2 / 3, rel=1e-4)
    assert cm.recall == pytest.approx(2 / 3, rel=1e-4)


def test_confusion_matrix_mismatched_lengths():
    with pytest.raises(ValueError, match="не совпадают"):
        compute_confusion_matrix([True], [True, False])


def test_attach_ground_truth_missing_ids_treated_as_not_fraud():
    df_pred = pd.DataFrame({"event_id": ["a", "b", "c"],
                            "is_fraud_predicted": [True, False, True]})
    labels = pd.DataFrame({"event_id": ["a", "b"], "is_fraud_real": [True, False]})
    merged = attach_ground_truth(df_pred, labels)
    assert merged.loc[merged["event_id"] == "c", "is_fraud_real"].iloc[0] == False


def test_attach_ground_truth_ignores_is_fraud_real_in_predictions():
    """Clean CSV may still carry is_fraud_real; labels file is authoritative."""
    df_pred = pd.DataFrame({
        "event_id": ["a", "b"],
        "is_fraud_predicted": [True, False],
        "is_fraud_real": [False, False],
    })
    labels = pd.DataFrame({"event_id": ["a", "b"], "is_fraud_real": [True, False]})
    merged = attach_ground_truth(df_pred, labels)
    assert merged.loc[merged["event_id"] == "a", "is_fraud_real"].iloc[0] == True
    assert merged.loc[merged["event_id"] == "b", "is_fraud_real"].iloc[0] == False


def test_compare_returns_proper_deltas():
    before = ConfusionMatrix(tp=10, fp=5, fn=20, tn=100)
    after = ConfusionMatrix(tp=18, fp=2, fn=12, tn=103)
    result = compare(before, after)
    assert result["delta"]["tp"] == 8
    assert result["delta"]["fp"] == -3
    assert result["delta"]["recall_pp"] == pytest.approx(26.67, abs=0.05)
