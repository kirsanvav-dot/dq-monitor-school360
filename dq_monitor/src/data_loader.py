"""
Загрузка датасета транзакций и валидация схемы.

Этот модуль — общая инфраструктура. Все остальные модули принимают
на вход уже загруженный DataFrame.
"""
from __future__ import annotations

from pathlib import Path
from typing import IO

import pandas as pd


# Ожидаемая схема событий. Команда может расширять,
# но эти поля обязаны быть.
EVENTS_REQUIRED_COLUMNS = [
    "event_id", "client_id", "event_type", "event_ts",
    "device_type", "ip_address", "geo_country", "geo_city", "channel",
    "amount_rub", "currency", "merchant_category", "merchant_country",
    "card_last4", "is_flagged", "flag_reason",
    "session_start_ts", "session_end_ts", "login_success", "auth_method",
]

# Колонки, которые мы НЕ парсим автоматически как datetime —
# в них могут быть битые значения, и пусть с ними разбирается profiler/cleaner.
_DATETIME_COLUMNS = ["event_ts", "session_start_ts", "session_end_ts"]


class SchemaError(ValueError):
    """Бросается, если в загруженных данных нет требуемых колонок."""


def load_events(source: str | Path | IO) -> pd.DataFrame:
    """Загрузить датасет событий из CSV-файла или потока.

    Даты НЕ парсятся при загрузке — иначе мы потеряем DQ-проблемы
    с битыми форматами (вся точка проекта именно в них).

    Поля card_last4, currency, merchant_category читаются как строки,
    чтобы pandas не делал из них float64 и не терял ведущие нули
    (например, '0042' -> 42.0).

    Args:
        source: путь к файлу или file-like объект (как из streamlit uploader).

    Returns:
        DataFrame с событиями.

    Raises:
        SchemaError: если в CSV нет обязательных колонок.
    """
    # Явный dtype для всех текстовых полей, у которых значения могут
    # выглядеть как числа (опечатка '810' в currency, ISO-коды в MCC,
    # ведущие нули в card_last4).
    string_columns = {
        "event_id": "string",
        "client_id": "string",
        "event_type": "string",
        "event_ts": "string",
        "device_type": "string",
        "ip_address": "string",
        "geo_country": "string",
        "geo_city": "string",
        "channel": "string",
        "currency": "string",
        "merchant_category": "string",
        "merchant_country": "string",
        "card_last4": "string",
        "flag_reason": "string",
        "session_start_ts": "string",
        "session_end_ts": "string",
        "auth_method": "string",
    }
    df = pd.read_csv(source, dtype=string_columns, low_memory=False)
    validate_schema(df)
    return df


def load_fraud_labels(source: str | Path | IO) -> pd.DataFrame:
    """Загрузить ground truth метки фрода: event_id -> is_fraud_real.

    Используется только для финальной оценки антифрод-правил.
    Студенты ПОЛУЧАЮТ этот файл на дне 7-8, не раньше.
    """
    labels = pd.read_csv(source)
    expected = {"event_id", "is_fraud_real"}
    missing = expected - set(labels.columns)
    if missing:
        raise SchemaError(f"В файле меток нет колонок: {missing}")
    return labels


def validate_schema(df: pd.DataFrame) -> None:
    """Проверить, что в df есть все ожидаемые колонки.

    Raises:
        SchemaError со списком отсутствующих колонок.
    """
    missing = set(EVENTS_REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise SchemaError(
            f"В загруженных данных не хватает колонок: {sorted(missing)}. "
            f"Ожидалось: {EVENTS_REQUIRED_COLUMNS}"
        )


def get_summary(df: pd.DataFrame) -> dict:
    """Быстрая сводка по датасету — для отображения в UI после загрузки."""
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "transactions": int((df["event_type"] == "transaction").sum()),
        "sessions": int((df["event_type"] == "session").sum()),
        "unique_clients": df["client_id"].nunique(dropna=True),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 1),
    }
