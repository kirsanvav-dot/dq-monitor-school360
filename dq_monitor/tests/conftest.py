"""Общие фикстуры для тестов команды."""
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
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

@pytest.fixture
def medium_dirty_df(medium_clean_df) -> pd.DataFrame:
    """Загрязнённый средний датасет полученный датасета на реальных данных."""
    df = medium_clean_df.copy()
    # emptiness

    df.loc[0, "event_id"] = None
    df.loc[10, "client_id"] = None
    df.loc[1, "event_ts"] = None
    df.loc[2, "device_type"] = None
    df.loc[6, "geo_city"] = None
    df.loc[9, "amount_rub"] = None
    df.loc[7, "currency"] = None
    df.loc[8, "is_flagged"] = True

    # validity

    df.loc[0, "ip_address"] = "aboba"
    df.loc[1, "ip_address"] = "-1.0.0.0"
    df.loc[2, "ip_address"] = "0.0.256.0"

    df.loc[7, "currency"] = "rur"
    df.loc[8, "currency"] = "$"
    df.loc[9, "currency"] = "USDD"

    df.loc[10, "device_type"] = "atmr"

    df.loc[14, "amount_rub"] = 0.001
    df.loc[15, "amount_rub"] = -10.0
    df.loc[16, "amount_rub"] = 10000000.0

    df.loc[14, "card_last4"] = 10000.0
    df.loc[15, "card_last4"] = 5435.1
    df.loc[16, "card_last4"] = -1.0

    df.loc[11, "event_ts"] = "2012.12.32 22:48:23"

    df.loc[14, "merchant_category"] = "hi!"
    df.loc[15, "merchant_category"] = "3473"
    df.loc[16, "merchant_category"] = "healthcare."

    # inconsistency

    df.loc[21, "flag_reason"] = "aboba"

    df.loc[18, "amount_rub"] = 312.0
    df.loc[19, "merchant_category"] = "atm_withdrawal"

    df.loc[14, "login_success"] = False
    df.loc[15, "session_start_ts"] = "tomorow"

    # dublicates
    df = pd.concat([df, df.iloc[3:6]], ignore_index=True)
    df.loc[25, "client_id"] = "aboba"
    return df
