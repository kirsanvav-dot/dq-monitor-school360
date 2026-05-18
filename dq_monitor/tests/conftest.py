"""Общие фикстуры для тестов команды."""
from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.fixture
def small_clean_df() -> pd.DataFrame:
    """10 строк чистых корректных событий — базовая фикстура."""
    base_ts = datetime(2025, 3, 1, 12, 0, 0)
    rows = []
    for i in range(10):
        is_txn = i % 2 == 0
        rows.append({
            "event_id": f"evt_{i:04d}",
            "client_id": f"C{i % 5:06d}",
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
    df.loc[0, "client_id"] = None            # 1 пропуск client_id
    df.loc[1, "ip_address"] = "999.999.999.999"  # 1 битый IP
    df.loc[2, "currency"] = "rub"            # 1 опечатка в currency
    df = pd.concat([df, df.iloc[3:4]], ignore_index=True)  # 1 дубликат
    return df

@pytest.fixture
def medium_clean_df() -> pd.DataFrame:
    """Чистый средний датасет из реальных данных."""
    df = pd.read_csv("dq_monitor/data/raw/events_clean.csv")
    return df
