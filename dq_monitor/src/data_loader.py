"""
Загрузка датасета транзакций. Этот модуль команде УЖЕ дан готовым —
не потому что писать загрузку CSV сложно, а потому что в нашем датасете
есть тонкости с типами данных, на которые легко наступить (см. ниже).
Изучите код как образец стиля и используйте `load_events()` во всех
других модулях, где нужно прочитать CSV.

Почему это уже написано:
1. В CSV есть `card_last4` с ведущими нулями ('0042'). Pandas при
   обычном чтении видит чистые цифры и делает float64 → '0042' → 42.0.
   Поэтому мы явно задаём dtype='string' для текстовых полей.
2. В currency бывает значение '810' (опечатка ISO numeric для RUB).
   Тоже выглядит как число и подвергается риску — поэтому тоже string.
3. Поля event_ts мы НЕ парсим автоматически как datetime — иначе
   потеряем DQ-проблемы с битыми форматами ('32/13/2025', 'вчера').
"""
from __future__ import annotations

from pathlib import Path
from typing import IO

import pandas as pd


# Ожидаемая схема событий. Если в CSV нет какой-то из этих колонок —
# это структурная ошибка, и приложение должно сразу её показать.
EVENTS_REQUIRED_COLUMNS = [
    "event_id", "client_id", "event_type", "event_ts",
    "device_type", "ip_address", "geo_country", "geo_city", "channel",
    "amount_rub", "currency", "merchant_category", "merchant_country",
    "card_last4", "is_flagged", "flag_reason",
    "session_start_ts", "session_end_ts", "login_success", "auth_method",
]


class SchemaError(ValueError):
    """Бросается, если в загруженных данных нет обязательных колонок."""


def load_events(source: str | Path | IO) -> pd.DataFrame:
    """Загрузить датасет событий из CSV-файла или потока (streamlit uploader).

    Args:
        source: путь к файлу или file-like объект.

    Returns:
        DataFrame с событиями, где строковые поля гарантированно — строки.

    Raises:
        SchemaError: если в CSV нет обязательных колонок.
    """
    # Явный dtype для всех текстовых полей. Это критично — см. docstring модуля.
    string_columns = {
        "event_id": "string", "client_id": "string", "event_type": "string",
        "event_ts": "string", "device_type": "string", "ip_address": "string",
        "geo_country": "string", "geo_city": "string", "channel": "string",
        "currency": "string", "merchant_category": "string",
        "merchant_country": "string", "card_last4": "string",
        "flag_reason": "string", "session_start_ts": "string",
        "session_end_ts": "string", "auth_method": "string",
    }
    df = pd.read_csv(source, dtype=string_columns, low_memory=False)
    validate_schema(df)
    return df


def load_fraud_labels(source: str | Path | IO) -> pd.DataFrame:
    """Загрузить ground truth метки фрода: event_id -> is_fraud_real.

    Этот файл вам выдаст ментор на 6-7 день. До этого работаете слепо.
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
