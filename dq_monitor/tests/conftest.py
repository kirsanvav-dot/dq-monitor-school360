"""Общие фикстуры для тестов."""
from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.fixture
def small_clean_df() -> pd.DataFrame:
    """10 строк чистых корректных событий — базовая фикстура для unit-тестов."""
    base_ts = datetime(2025, 3, 1, 12, 0, 0)
    rows = []
    for i in range(10):
        is_txn = i % 2 == 0
        rows.append({
            "event_id": f"evt_{i:04d}",
            "client_id": f"C{i % 5:06d}",  # 5 уникальных клиентов
            "event_type": "transaction" if is_txn else "session",
            "event_ts": (base_ts + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"),
            "device_type": "mobile",
            "ip_address": f"192.168.1.{i+1}",
            "geo_country": "Russia",
            "geo_city": "Moscow",
            "channel": "app",
            "amount_rub": 5000.0 if is_txn else None,
            "currency": "RUB" if is_txn else None,
            "merchant_category": "grocery" if is_txn else None,
            "merchant_country": "Russia" if is_txn else None,
            "card_last4": "1234" if is_txn else None,
            "is_flagged": False,
            "flag_reason": None,
            "session_start_ts": None if is_txn else (base_ts + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"),
            "session_end_ts": None if is_txn else (base_ts + timedelta(minutes=i+5)).strftime("%Y-%m-%d %H:%M:%S"),
            "login_success": None if is_txn else True,
            "auth_method": None if is_txn else "password",
        })
    return pd.DataFrame(rows)


@pytest.fixture
def small_dirty_df(small_clean_df) -> pd.DataFrame:
    """Чистый датасет + точечные DQ-проблемы для проверки детекторов."""
    df = small_clean_df.copy()
    # Один пропуск client_id
    df.loc[0, "client_id"] = None
    # Один битый IP
    df.loc[1, "ip_address"] = "999.999.999.999"
    # Опечатка в currency
    df.loc[2, "currency"] = "rub"
    # Один дубликат
    df = pd.concat([df, df.iloc[3:4]], ignore_index=True)
    return df
