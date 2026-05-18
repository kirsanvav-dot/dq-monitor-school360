import pytest
import pandas as pd
import numpy as np
from src.profiler import DataProfiler, DQIssue
from src.constant_issue import IssueType
from src.data_loader import EVENTS_REQUIRED_COLUMNS
import src.reference_data as ref  # Предполагается, что константы VALID_* определены здесь
from typing import List, Optional


@pytest.fixture
def profiler():
    return DataProfiler()

@pytest.fixture
def base_transaction_df():
    """Возвращает датафрейм с одной идеальной транзакцией."""
    data = {col: "" for col in EVENTS_REQUIRED_COLUMNS}
    data.update({
        "event_id": "evt_tx_1",
        "client_id": "client_1",
        "event_type": "transaction",
        "event_ts": "2023-10-01 12:00:00",
        "device_type": "mobile", 
        "ip_address": "192.168.1.1",
        "geo_country": "RU",
        "geo_city": "Moscow",
        "channel": "app",
        "amount_rub": 1000.0,
        "currency": "RUB", 
        "merchant_category": "Supermarket", 
        "merchant_country": "RU",
        "card_last4": "1234",
        "is_flagged": False,
        "flag_reason": "Not flagged" # Заполняем, чтобы по умолчанию не срабатывал check_empty_flag_reason
    })
    
    # Имитируем загрузку из CSV, где все поля имеют строковый тип (кроме amount и флагов)
    df = pd.DataFrame([data])
    for col in df.columns:
        if col not in ['amount_rub', 'is_flagged']:
            df[col] = df[col].astype('string')
    return df

@pytest.fixture
def base_session_df():
    """Возвращает датафрейм с одной идеальной сессией."""
    data = {col: "" for col in EVENTS_REQUIRED_COLUMNS}
    data.update({
        "event_id": "evt_ss_1",
        "client_id": "client_1",
        "event_type": "session",
        "event_ts": "2023-10-01 12:00:00",
        "device_type": "desktop",
        "ip_address": "10.0.0.1",
        "geo_country": "RU",
        "geo_city": "Kazan",
        "session_start_ts": "2023-10-01 12:00:00",
        "session_end_ts": "2023-10-01 12:30:00",
        "login_success": "True",
        "auth_method": "password",
        "is_flagged": False,
        "amount_rub": np.nan # Для сессий пустые значения
    })
    df = pd.DataFrame([data])
    for col in df.columns:
        if col not in ['amount_rub', 'is_flagged']:
            df[col] = df[col].astype('string')
    return df

# ==================== COMPLETENESS CHECKS (8 шт.) ====================

def test_empty_event_id(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'event_id'] = ""
    issue = profiler._check_empty_event_id(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.EMPTY_EVENT_ID
    assert issue.rows_affected == 1
    assert 0 in issue.affected_indices

def test_empty_client_id(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'client_id'] = pd.NA
    issue = profiler._check_empty_client_id(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.EMPTY_CLIENT_ID

def test_empty_event_ts(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'event_ts'] = ""
    issue = profiler._check_empty_event_ts(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.EMPTY_EVENT_TS

def test_empty_device_type(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'device_type'] = ""
    issue = profiler._check_empty_device_type(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.EMPTY_DEVICE_TYPE

def test_empty_geo_city(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'geo_city'] = ""
    issue = profiler._check_empty_geo_city(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.EMPTY_GEO_CITY

def test_empty_amount_rub_for_transaction(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'amount_rub'] = np.nan
    issue = profiler._check_empty_amount_rub(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.EMPTY_AMOUNT_RUB

def test_empty_currency_for_transaction(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'currency'] = ""
    issue = profiler._check_empty_currency(df)
    
    assert issue is not None
    # Примечание: тут надо поправить IssueType.EMPTY_EMPTY_CURRENCY на EMPTY_CURRENCY в profiler.py
    assert issue.issue_type == IssueType.EMPTY_CURRENCY

"""def test_empty_flag_reason(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'flag_reason'] = ""

    issue = profiler._check_empty_flag_reason(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.EMPTY_FLAG_REASON
"""
# ==================== VALIDITY CHECKS (7 шт.) ====================

def test_invalid_format_date(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'event_ts'] = "32/13/2025" # Несуществующая дата
    issue = profiler._check_invalid_format_date(df)
    
    assert issue is not None
    # Примечание: тут надо поправить IssueType.EINVALID_FORMAT_DATE на INVALID_FORMAT_DATE в profiler.py
    assert issue.issue_type == IssueType.INVALID_FORMAT_DATE

def test_invalid_ip_address(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'ip_address'] = "999.999.999.999" # Ошибка диапазона
    issue = profiler._check_invalid_ip_address(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INVALID_IP_ADDRESS

def test_invalid_amount_rub(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'amount_rub'] = -500.0 # Отрицательная сумма
    issue = profiler._check_invalid_amount_rub(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INVALID_AMOUNT_RUB

def test_invalid_currency(profiler, base_transaction_df, monkeypatch):
    monkeypatch.setattr(ref, "VALID_CURRENCIES", ["RUB", "USD"])
    df = base_transaction_df.copy()
    df.loc[0, 'currency'] = "810" # ISO-код вместо строки
    issue = profiler._check_invalid_currency(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INVALID_CURRENCY

def test_invalid_merchant_category(profiler, base_transaction_df, monkeypatch):
    monkeypatch.setattr(ref, "VALID_MERCHANT_CATEGORIES", ["Supermarket", "Pharmacy"])
    df = base_transaction_df.copy()
    df.loc[0, 'merchant_category'] = "5411" # MCC код (число) вместо категории
    issue = profiler._check_invalid_merchant_category(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INVALID_MERCHANT_CATEGORY

def test_invalid_card_last4(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'card_last4'] = "12A4" # Не цифры
    issue = profiler._check_invalid_card_last4(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INVALID_CARD_LAST4

def test_invalid_device_type(profiler, base_transaction_df, monkeypatch):
    monkeypatch.setattr(ref, "VALID_DEVICE_TYPES", ["mobile", "desktop"])
    df = base_transaction_df.copy()
    df.loc[0, 'device_type'] = "toaster" # Устройство не из списка
    issue = profiler._check_invalid_device_type(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INVALID_DEVICE_TYPE


# ==================== CONSISTENCY CHECKS (3 шт.) ====================

def test_inconsistency_flagged_field(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    df.loc[0, 'is_flagged'] = False
    df.loc[0, 'flag_reason'] = "Suspicious behavior" # Фолс-флаг, но есть причина
    issue = profiler._check_inconsistency_flagged_field(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INCONSISTENCY_FLAGGED

def test_inconsistency_transaction_field(profiler, base_transaction_df):
    df = base_transaction_df.copy()
    # Транзакция, но содержит признаки сессии
    df.loc[0, 'session_start_ts'] = "2023-10-01 12:00:00"
    issue = profiler._check_inconsistency_transaction_field(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INCONSISTENCY_TRANSACTION

def test_inconsistency_session_field(profiler, base_session_df):
    df = base_session_df.copy()
    # Сессия, но содержит данные о транзакции
    df.loc[0, 'amount_rub'] = 1000.0 
    issue = profiler._check_inconsistency_session_field(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.INCONSISTENCY_SESSION

# ==================== UNIQUENESS CHECKS (2 шт.) ====================

def test_full_duplicate(profiler, base_transaction_df):
    # Дублируем первую строку
    df = pd.concat([base_transaction_df, base_transaction_df], ignore_index=True)
    issue = profiler._check_full_duplicate(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.DUPLICATE_FULL
    assert issue.rows_affected == 2 # Затронуты обе строки

def test_event_id_duplicate(profiler, base_transaction_df):
    df = pd.concat([base_transaction_df, base_transaction_df], ignore_index=True)
    # Делаем строки разными, чтобы это не был полный дубликат
    df.loc[1, 'amount_rub'] = 500.0 
    issue = profiler._check_event_id_duplicate(df)
    
    assert issue is not None
    assert issue.issue_type == IssueType.DUPLICATE_EVENT_ID
    assert issue.rows_affected == 2

def test_medium_df_reading(medium_clean_df):
    assert len(medium_clean_df) == 24

def check_dqissue_eq_list(ans: List[int], issue: Optional[DQIssue]):
    if issue is None and len(ans) == 0:
        return
    assert issue is not None
    assert len(issue.affected_indices) == len(ans)
    for ind in ans:
        assert ind in issue.affected_indices

@pytest.mark.parametrize("issue,rowsAffected", [
    (IssueType.EMPTY_EVENT_ID, []),
    (IssueType.EMPTY_CLIENT_ID, []),
    (IssueType.EMPTY_EVENT_TS, []),
    (IssueType.EMPTY_DEVICE_TYPE, []),
    (IssueType.EMPTY_GEO_CITY, []),
    (IssueType.EMPTY_AMOUNT_RUB, []),
    (IssueType.EMPTY_CURRENCY, []),
    (IssueType.EMPTY_FLAG_REASON, []),

    # Validity
    (IssueType.INVALID_IP_ADDRESS, []),
    (IssueType.INVALID_CURRENCY, []),
    (IssueType.INVALID_DEVICE_TYPE, []),
    (IssueType.INVALID_AMOUNT_RUB, []),
    (IssueType.INVALID_CARD_LAST4, []),
    (IssueType.INVALID_FORMAT_DATE, []),
    (IssueType.INVALID_MERCHANT_CATEGORY, []),

    # Consistency
    (IssueType.INCONSISTENCY_FLAGGED, []),
    (IssueType.INCONSISTENCY_SESSION, []),
    (IssueType.INCONSISTENCY_TRANSACTION, []),

    # Uniqueness
    (IssueType.DUPLICATE_EVENT_ID, []),
    (IssueType.DUPLICATE_FULL, []),
])
def test_each_issue_checker_dont_react_to_clean(issue: IssueType, rowsAffected: List[int], medium_clean_df):
    profiler = DataProfiler()
    func = getattr(profiler, f"_check_{issue.method_name}")
    assert func is not None
    check_dqissue_eq_list(rowsAffected, func(medium_clean_df))

@pytest.mark.parametrize("issue,rowsAffected", [
    (IssueType.EMPTY_EVENT_ID, [0]),
    (IssueType.EMPTY_CLIENT_ID, [10]),
    (IssueType.EMPTY_EVENT_TS, [1]),
    (IssueType.EMPTY_DEVICE_TYPE, [2]),
    (IssueType.EMPTY_GEO_CITY, [6]),
    (IssueType.EMPTY_AMOUNT_RUB, [9]),
    (IssueType.EMPTY_CURRENCY, [7]),
    (IssueType.EMPTY_FLAG_REASON, [8]),

    # Validity
    (IssueType.INVALID_IP_ADDRESS, [0, 1, 2]),
    (IssueType.INVALID_CURRENCY, [7, 8, 9]),
    (IssueType.INVALID_DEVICE_TYPE, [10]),
    (IssueType.INVALID_AMOUNT_RUB, [14, 15, 16]),
    (IssueType.INVALID_CARD_LAST4, [14, 15, 16]),
    (IssueType.INVALID_FORMAT_DATE, [11]),
    (IssueType.INVALID_MERCHANT_CATEGORY, [14, 15, 16]),

    # Consistency
    (IssueType.INCONSISTENCY_FLAGGED, [21]),
    (IssueType.INCONSISTENCY_SESSION, [18, 19, 20]),
    (IssueType.INCONSISTENCY_TRANSACTION, [14, 15, 16]),

    # Uniqueness
    (IssueType.DUPLICATE_EVENT_ID, [24, 25, 26]),
    (IssueType.DUPLICATE_FULL, [24, 26]),
])
def test_each_issue_checker_react_to_dirty(issue: IssueType, rowsAffected: List[int], medium_dirty_df):
    profiler = DataProfiler()
    func = getattr(profiler, f"_check_{issue.method_name}")
    assert func is not None
    check_dqissue_eq_list(rowsAffected, func(medium_dirty_df))

def test_dirty_medium_dataset(medium_dirty_df):
    print(medium_dirty_df)
    print("a")
