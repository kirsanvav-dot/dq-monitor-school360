"""Тесты для готового data_loader.py — образец стиля для ваших тестов."""
import io

import pandas as pd
import pytest

from src.data_loader import (
    EVENTS_REQUIRED_COLUMNS,
    SchemaError,
    get_summary,
    load_events,
    validate_schema,
)


def test_validate_schema_passes_on_full_columns(small_clean_df):
    validate_schema(small_clean_df)


def test_validate_schema_raises_on_missing_column(small_clean_df):
    df = small_clean_df.drop(columns=["event_id"])
    with pytest.raises(SchemaError, match="event_id"):
        validate_schema(df)


def test_load_events_from_csv_buffer(small_clean_df):
    """Загрузка из буфера (как из streamlit uploader)."""
    buffer = io.StringIO()
    small_clean_df.to_csv(buffer, index=False)
    buffer.seek(0)
    loaded = load_events(buffer)
    assert len(loaded) == len(small_clean_df)
    assert list(loaded.columns) == list(small_clean_df.columns)


def test_load_events_does_not_parse_dates(small_clean_df, tmp_path):
    """event_ts остаётся строкой — важно для DQ-проверок."""
    path = tmp_path / "sample.csv"
    small_clean_df.to_csv(path, index=False)
    loaded = load_events(path)
    assert not pd.api.types.is_datetime64_any_dtype(loaded["event_ts"])


def test_get_summary(small_clean_df):
    summary = get_summary(small_clean_df)
    assert summary["rows"] == 10
    assert summary["transactions"] == 5
    assert summary["sessions"] == 5
    assert summary["unique_clients"] == 5
    assert summary["columns"] == len(EVENTS_REQUIRED_COLUMNS)
