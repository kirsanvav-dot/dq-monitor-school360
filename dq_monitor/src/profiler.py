"""
Профилирование данных: поиск DQ-проблем по 4 измерениям качества.

🔲 ЭТОТ МОДУЛЬ ВАШ — DQ ANALYST.

Файл сейчас пустой. Ваша задача — спроектировать классы и функции
так, чтобы получить отчёт о найденных проблемах, и связать модуль
со страницей DQ Report в приложении.

────────────────────────────────────────────────────────────────────
ЧТО МЫ ХОТИМ ПОЛУЧИТЬ

После прогона профайлера на грязном DataFrame у нас должен быть
объект-отчёт, который умеет:
  — перечислить найденные проблемы (тип, описание, сколько строк затронуто)
  — сгруппировать проблемы по 4 измерениям качества
  — превратить себя в pandas.DataFrame для отображения в UI

────────────────────────────────────────────────────────────────────
4 ИЗМЕРЕНИЯ КАЧЕСТВА — ЧТО ИСКАТЬ

  Completeness — есть ли значения в обязательных полях
    Примеры: пропуски в client_id, event_id, event_ts, amount_rub
    Учтите: пустая строка '' — это тоже пропуск качества данных,
    но pandas считает её непустой. Нужна явная проверка.

  Validity — соответствуют ли значения формату/диапазону
    Примеры: 'event_ts' = 'вчера', ip_address = '999.999.999.999',
    currency = '$' / 'rub' / '810' / 'USDD', amount_rub < 0 или > 10M,
    merchant_category = '5411' (это ISO-код, должна быть текстовая категория).
    Подсказка: pd.to_datetime(..., errors='coerce') превращает мусор в NaT.

  Consistency — согласованы ли поля между собой (cross-field логика)
    Примеры: is_flagged=True, но flag_reason пустой; event_type='transaction',
    но заполнены session_start_ts/session_end_ts/login_success.

  Uniqueness — нет ли дубликатов
    Полные дубликаты строк и/или дубликаты по event_id.

────────────────────────────────────────────────────────────────────
АРХИТЕКТУРНЫЕ ПОДСКАЗКИ

  1. Удобно завести dataclass для одной найденной проблемы:
     поля типа issue_type, description, dimension, column, rows_affected.
     Это будет общий язык между профайлером, страницей UI и cleaner'ом.

  2. И второй dataclass для отчёта целиком: список проблем + общая статистика.

  3. Сам класс DataProfiler — это контейнер с методами check_*, каждый
     возвращает список проблем по своему измерению. Метод profile()
     собирает все check_* и возвращает отчёт.

────────────────────────────────────────────────────────────────────
КАК ЭТО ИСПОЛЬЗУЕТСЯ В UI

В app/pages/1_📊_DQ_Report.py будет код вида:

    from src.profiler import DataProfiler
    profiler = DataProfiler()
    report = profiler.profile(df)
    st.dataframe(report.to_dataframe())

Поэтому проектируйте публичный API именно под такое использование.
"""
from typing import Optional, List
from dataclasses import dataclass, field
from src.constant_issue import IssueType, DQDimension
import pandas as pd
import src.reference_data as ref
import re


#Датакласс для одной ошибки
@dataclass
class DQIssue:
    issue_type: IssueType
    affected_indices: pd.Index = field(default_factory=lambda: pd.Index([]))

    @property
    def rows_affected(self) -> int:
        """Количество затронутых строк вычисляется автоматически по длине индексов."""
        return len(self.affected_indices)

@dataclass
class Report:
  total_rows: int
  issues: List[DQIssue]
  
  @property
  def total_issues(self) -> int:
      """Общее количество найденных проблем."""
      return len(self.issues)
      
  def get_summary_by_dimension(self) -> dict:
      """Группировка количества проблем по 4 измерениям качества."""
      summary = {dim.value: 0 for dim in DQDimension}
      for issue in self.issues:
          summary[issue.dimension.value] += 1
      return summary
  
  def to_dataframe(self) -> pd.DataFrame:
        if not self.issues:
            return pd.DataFrame(columns=["dimension", "issue_type", "column", "description", "rows_affected", "percent_affected"])
            
        df = pd.DataFrame([
            {
                "dimension": issue.issue_type.dimension,
                "issue_type": issue.issue_type.name,  
                "column": str(issue.issue_type.column), # tuple лучше привести к строке
                "description": issue.issue_type.description,
                "rows_affected": issue.rows_affected,
                "percent_affected": round((issue.rows_affected / self.total_rows) * 100, 2) if self.total_rows > 0 else 0
            }
            for issue in self.issues
        ])
        
        return df.sort_values(by=["dimension", "rows_affected"], ascending=[True, False]).reset_index(drop=True)

#TODO Основная идея архитектуры:
#DQ реализует только сами  issue в виде констант и функций
#не задумываясь о том, как данные будут затем передаваться и обрабатываться
class DataProfiler():
  def profile(self, df: pd.DataFrame) -> Report:
    issues = []
    # Список обхода поиска ошибок
    checks_to_run: list[IssueType] = [
        # Completeness — глобальные поля
        IssueType.EMPTY_EVENT_ID,
        IssueType.EMPTY_CLIENT_ID,
        IssueType.EMPTY_EVENT_TYPE,
        IssueType.EMPTY_EVENT_TS,
        IssueType.EMPTY_DEVICE_TYPE,
        IssueType.EMPTY_IP_ADDRESS,
        IssueType.EMPTY_GEO_COUNTRY,
        IssueType.EMPTY_GEO_CITY,
        IssueType.EMPTY_CHANNEL,
        # Completeness — поля транзакций
        IssueType.EMPTY_AMOUNT_RUB,
        IssueType.EMPTY_CURRENCY,
        IssueType.EMPTY_MERCHANT_CATEGORY,
        IssueType.EMPTY_MERCHANT_COUNTRY,
        IssueType.EMPTY_CARD_LAST4,
        # Completeness — поля сессий
        IssueType.EMPTY_SESSION_START_TS,
        IssueType.EMPTY_SESSION_END_TS,
        IssueType.EMPTY_LOGIN_SUCCESS,
        IssueType.EMPTY_AUTH_METHOD,
        # Completeness — условный (is_flagged)
        IssueType.EMPTY_FLAG_REASON,

        # Validity
        IssueType.INVALID_EVENT_TYPE,
        IssueType.INVALID_FORMAT_DATE,
        IssueType.INVALID_SESSION_START_TS,
        IssueType.INVALID_SESSION_END_TS,
        IssueType.INVALID_IP_ADDRESS,
        IssueType.INVALID_AMOUNT_RUB,
        IssueType.INVALID_CURRENCY,
        IssueType.INVALID_MERCHANT_CATEGORY,
        IssueType.INVALID_CARD_LAST4,
        IssueType.INVALID_DEVICE_TYPE,
        IssueType.INVALID_GEO_COUNTRY,
        # INVALID_GEO_COUNTRY исключён из пайплайна: датасет хранит полные названия
        # стран ("Russia", "Germany"), а не ISO-2 коды ("RU", "DE").
        # Константа и метод сохранены — включить после нормализации geo_country.
        IssueType.INVALID_CHANNEL,

        # Consistency
        IssueType.INCONSISTENCY_FLAGGED,
        IssueType.INCONSISTENCY_TRANSACTION,
        IssueType.INCONSISTENCY_SESSION,
        IssueType.INCONSISTENCY_SESSION_TIMESTAMPS,

        # Uniqueness
        IssueType.DUPLICATE_FULL,
        IssueType.DUPLICATE_EVENT_ID,
    ]
    
    for issue_type in checks_to_run:
        # Формируем имя метода: IssueType.BAD_FORMAT_DATE -> "_check_bad_format_date"
        method_name = f"_check_{issue_type.method_name}"
        # Получаем сам метод у текущего объекта (self)
        try:
            check_method = getattr(self, method_name)
        except AttributeError:
            raise NotImplementedError(
                f"Ошибка архитектуры: в пайплайне включено правило '{issue_type.name}', "
                f"но метод '{method_name}' не реализован в классе {self.__class__.__name__}."
            )
      
        # Вызываем метод. Ожидаем, что он вернет Issue или None
        issue = check_method(df)
        if issue is not None:
            issues.append(issue)
            
    return Report(total_rows=len(df), issues=issues)


#Completness
  def _check_empty_event_id(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['event_id'].isnull()) | (df['event_id'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_EVENT_ID,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_client_id(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['client_id'].isnull()) | (df['client_id'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_CLIENT_ID,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_event_type(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['event_type'].isnull()) | (df['event_type'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_EVENT_TYPE,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_event_ts(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['event_ts'].isnull()) | (df['event_ts'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_EVENT_TS,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_device_type(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['device_type'].isnull()) | (df['device_type'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_DEVICE_TYPE,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_ip_address(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['ip_address'].isnull()) | (df['ip_address'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_IP_ADDRESS,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_geo_country(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['geo_country'].isnull()) | (df['geo_country'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_GEO_COUNTRY,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_geo_city(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['geo_city'].isnull()) | (df['geo_city'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_GEO_CITY,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_channel(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['channel'].isnull()) | (df['channel'] == "")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_CHANNEL,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_amount_rub(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['amount_rub'].isnull()) | (df['amount_rub'] == "")) & (df['event_type'] == "transaction")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_AMOUNT_RUB,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_currency(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['currency'].isnull()) | (df['currency'] == "")) & (df['event_type'] == "transaction")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_CURRENCY,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_merchant_category(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['merchant_category'].isnull()) | (df['merchant_category'] == "")) & (df['event_type'] == "transaction")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_MERCHANT_CATEGORY,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_merchant_country(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['merchant_country'].isnull()) | (df['merchant_country'] == "")) & (df['event_type'] == "transaction")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_MERCHANT_COUNTRY,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_card_last4(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['card_last4'].isnull()) | (df['card_last4'] == "")) & (df['event_type'] == "transaction")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_CARD_LAST4,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_session_start_ts(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['session_start_ts'].isnull()) | (df['session_start_ts'] == "")) & (df['event_type'] == "session")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_SESSION_START_TS,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_session_end_ts(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['session_end_ts'].isnull()) | (df['session_end_ts'] == "")) & (df['event_type'] == "session")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_SESSION_END_TS,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_login_success(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = (df['login_success'].isnull()) & (df['event_type'] == "session")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_LOGIN_SUCCESS,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_auth_method(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['auth_method'].isnull()) | (df['auth_method'] == "")) & (df['event_type'] == "session")
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_AUTH_METHOD,
              affected_indices=bad_index,
          )
      return None

  def _check_empty_flag_reason(self, df: pd.DataFrame) -> Optional[DQIssue]:
      mask = ((df['flag_reason'].isnull()) | (df['flag_reason'] == "")) & (df['is_flagged'] == True)
      bad_index = df[mask].index
      if len(bad_index) > 0:
          return DQIssue(
              issue_type=IssueType.EMPTY_FLAG_REASON,
              affected_indices=bad_index,
          )
      return None


    #Validity
  def _check_invalid_event_type(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = df['event_type'].isnull() | (df['event_type'] == "")
    mask = ~is_empty & ~df['event_type'].astype(str).isin(ref.VALID_EVENT_TYPES)
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_EVENT_TYPE,
            affected_indices=bad_indices,
        )
    return None

  def _check_invalid_format_date(self, df: pd.DataFrame) -> Optional[DQIssue]:
    parsed = pd.to_datetime(df['event_ts'], errors='coerce')
    mask = parsed.isna() & df['event_ts'].notna() & (df['event_ts'].astype(str).str.strip() != "")
    bad_index = df[mask].index
    if len(bad_index) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_FORMAT_DATE,
            affected_indices=bad_index,
        )
    return None

  def _check_invalid_session_start_ts(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = df['session_start_ts'].isnull() | (df['session_start_ts'].astype(str).str.strip() == "")
    parsed = pd.to_datetime(df['session_start_ts'], errors='coerce')
    mask = ~is_empty & parsed.isna()
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_SESSION_START_TS,
            affected_indices=bad_indices,
        )
    return None

  def _check_invalid_session_end_ts(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = df['session_end_ts'].isnull() | (df['session_end_ts'].astype(str).str.strip() == "")
    parsed = pd.to_datetime(df['session_end_ts'], errors='coerce')
    mask = ~is_empty & parsed.isna()
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_SESSION_END_TS,
            affected_indices=bad_indices,
        )
    return None

  def _check_invalid_ip_address(self, df: pd.DataFrame) -> Optional[DQIssue]:
    ipv4_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')
    ip_series = df['ip_address'].copy()
    is_empty = (ip_series.isna()) | (ip_series.astype(str).str.strip() == "")
    matches_pattern = ip_series.astype(str).str.match(ipv4_pattern)
    valid_range = pd.Series([False] * len(df), index=df.index)
    pattern_matched_indices = df.index[matches_pattern & ~is_empty]
    for idx in pattern_matched_indices:
        ip_str = str(ip_series[idx])
        parts = ip_str.split('.')
        if all(0 <= int(part) <= 255 for part in parts):
            valid_range[idx] = True

    mask = ~is_empty & (~matches_pattern | ~valid_range)
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
                issue_type=IssueType.INVALID_IP_ADDRESS,
                affected_indices=bad_indices
        )
    return None

  def _check_invalid_amount_rub(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = (df['amount_rub'].isna()) | (df['amount_rub'] == "")
    # Минимум — 1 копейка (0.01 руб); суммы меньше или равные 0 недопустимы.
    # Максимум — 10 000 000 руб включительно (сумма >= 10M считается аномалией).
    mask = ~(is_empty) & ((df['amount_rub'] < 0.01) | (df['amount_rub'] >= 10_000_000))
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_AMOUNT_RUB,
            affected_indices=bad_indices
        )
    return None

  def _check_invalid_currency(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = (df['currency'].isna()) | (df['currency'] == "")
    mask = ~(is_empty) & ~(df['currency'].astype(str).isin(ref.VALID_CURRENCIES))
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_CURRENCY,
            affected_indices=bad_indices
        )
    return None

  def _check_invalid_merchant_category(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = (df['merchant_category'].isna()) | (df['merchant_category'] == "")
    mask = ~(is_empty) & ~(df['merchant_category'].astype(str).isin(ref.VALID_MERCHANT_CATEGORIES))
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_MERCHANT_CATEGORY,
            affected_indices=bad_indices
        )
    return None

  def _check_invalid_device_type(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = (df['device_type'].isna()) | (df['device_type'] == "")
    mask = ~(is_empty) & ~(df['device_type'].astype(str).isin(ref.VALID_DEVICE_TYPES))
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_DEVICE_TYPE,
            affected_indices=bad_indices
        )
    return None

  def _check_invalid_card_last4(self, df: pd.DataFrame) -> Optional[DQIssue]:
    # Проверяем только транзакции: для сессий наличие card_last4 — ошибка согласованности,
    # которую ловит INCONSISTENCY_SESSION, а не INVALID_CARD_LAST4.
    txn_mask = df['event_type'] == 'transaction'
    is_empty = (df['card_last4'].isna()) | (df['card_last4'] == "")

    def _normalize(val) -> str:
        """'1234.0' → '1234' (целое, записанное как float); прочие значения без изменений."""
        s = str(val)
        if '.' in s:
            try:
                f = float(s)
                if f == int(f):
                    return str(int(f))
            except (ValueError, OverflowError):
                pass
        return s

    normalized = df['card_last4'].apply(lambda x: _normalize(x) if pd.notna(x) else '')
    mask = txn_mask & ~is_empty & ~normalized.str.match(r'^\d{4}$')
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_CARD_LAST4,
            affected_indices=bad_indices
        )
    return None

  def _check_invalid_geo_country(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = (df['geo_country'].isna()) | (df['geo_country'] == "")
    mask = ~is_empty & ~df['geo_country'].astype(str).isin(ref.GEO_COUNTRY_PATTERN)
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_GEO_COUNTRY,
            affected_indices=bad_indices,
        )
    return None

  def _check_invalid_channel(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = (df['channel'].isna()) | (df['channel'] == "")
    mask = ~is_empty & ~df['channel'].astype(str).isin(ref.VALID_CHANNELS)
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INVALID_CHANNEL,
            affected_indices=bad_indices,
        )
    return None

  # CONSISTENCY
  def _check_inconsistency_flagged_field(self, df: pd.DataFrame) -> Optional[DQIssue]:
    is_empty = (df['flag_reason'].isna()) | (df['flag_reason'] == "")
    mask = (df['is_flagged'] == False) & ~is_empty
    bad_indices = df.index[mask]
    if len(bad_indices) > 0:
        return DQIssue(
            issue_type=IssueType.INCONSISTENCY_FLAGGED,
            affected_indices=bad_indices
        )
    return None

  def _check_inconsistency_transaction_field(self, df: pd.DataFrame) -> Optional[DQIssue]:
      transaction_mask = df['event_type'] == 'transaction'

      session_fields = ['session_start_ts', 'session_end_ts', 'login_success']
      has_session_data = pd.Series([False] * len(df), index=df.index)

      for field in session_fields:
          if field in df.columns:
              has_session_data = has_session_data | (df[field].notna() & (df[field].astype(str).str.strip() != ""))

      mask = transaction_mask & has_session_data
      bad_indices = df.index[mask]
      if len(bad_indices) > 0:
          return DQIssue(
              issue_type=IssueType.INCONSISTENCY_TRANSACTION,
              affected_indices=bad_indices)
      return None

  def _check_inconsistency_session_field(self, df: pd.DataFrame) -> Optional[DQIssue]:
        session_mask = df['event_type'] == 'session'

        transaction_fields = ['amount_rub', 'currency', 'merchant_category', 'merchant_country', 'card_last4']
        has_transaction_data = pd.Series([False] * len(df), index=df.index)

        for field in transaction_fields:
            if field in df.columns:
                has_transaction_data = has_transaction_data | (df[field].notna() & (df[field].astype(str).str.strip() != ""))
        mask = session_mask & has_transaction_data
        bad_indices = df.index[mask]
        if len(bad_indices) > 0:
            return DQIssue(
                issue_type=IssueType.INCONSISTENCY_SESSION,
                affected_indices=bad_indices)
        return None

  def _check_inconsistency_session_timestamps(self, df: pd.DataFrame) -> Optional[DQIssue]:
      session_mask = df['event_type'] == 'session'
      both_present = df['session_start_ts'].notna() & df['session_end_ts'].notna() \
                     & (df['session_start_ts'].astype(str).str.strip() != "") \
                     & (df['session_end_ts'].astype(str).str.strip() != "")
      start = pd.to_datetime(df['session_start_ts'], errors='coerce')
      end   = pd.to_datetime(df['session_end_ts'],   errors='coerce')
      mask = session_mask & both_present & start.notna() & end.notna() & (end < start)
      bad_indices = df.index[mask]
      if len(bad_indices) > 0:
          return DQIssue(
              issue_type=IssueType.INCONSISTENCY_SESSION_TIMESTAMPS,
              affected_indices=bad_indices,
          )
      return None

  # UNIQUENESS
  def _check_full_duplicate(self, df: pd.DataFrame):
      duplicated_mask = df.duplicated(keep='first')
      bad_indices = df.index[duplicated_mask]
      if len(bad_indices) > 0:
          return DQIssue(issue_type=IssueType.DUPLICATE_FULL, affected_indices=bad_indices)
      return None

  def _check_event_id_duplicate(self, df: pd.DataFrame) -> Optional[DQIssue]:
      full_duplicates_mask = df.duplicated(keep='first')
      full_duplicate_indices = df.index[full_duplicates_mask]
      df_no_full_dups = df[~full_duplicates_mask].copy()
      if len(df_no_full_dups) == 0:
          return None
      bad_indices = df_no_full_dups.index[
          df_no_full_dups['event_id'].duplicated(keep='first')
      ]
      if len(bad_indices) > 0:
          return DQIssue(issue_type=IssueType.DUPLICATE_EVENT_ID, affected_indices=bad_indices)
      return None
