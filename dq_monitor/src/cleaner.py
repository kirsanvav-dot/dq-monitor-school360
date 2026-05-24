"""
Очистка данных: применение правил к грязному датасету.

🔲 ЭТОТ МОДУЛЬ ВАШ — BACKEND + DQ ANALYST.

────────────────────────────────────────────────────────────────────
ЧТО МЫ ХОТИМ ПОЛУЧИТЬ

Класс или функция, которая принимает грязный DataFrame, применяет
к нему набор правил очистки и возвращает:
  — очищенный DataFrame
  — лог: какие правила применялись, сколько строк удалили / исправили
Лог нужен для отображения в UI и для финальной презентации.

────────────────────────────────────────────────────────────────────
ПРАВИЛА ОЧИСТКИ — МИНИМАЛЬНЫЙ НАБОР

Удаление (строка целиком улетает):
  — Дубликаты строк
  — Строки с пропуском в client_id
  — Строки с невалидной датой в event_ts
  — Строки с явно битой суммой (NaN / отрицательная / > 10 млн)

Восстановление (значение исправляется, строка остаётся):
  — currency: 'rub' → 'RUB', '$' → 'USD', 'USDD' → 'USD' и т.д.
    Это маппинг через справочник, обсудите границы случаев.
  — merchant_category: ISO-коды ('5411', '6011', ...) → текстовые
    категории ('grocery', 'atm_withdrawal'). Это обратный маппинг.
  — device_type: '' → NaN (пустая строка ≠ NaN на бекенде, чиним)

📖 Справочники для восстановления — в src/reference_data.py:
   ✅ MCC_ISO_TO_TEXT     — готов, можно использовать как есть
   ✅ VALID_DEVICE_TYPES  — готов
   🔲 CURRENCY_MAPPING    — заполняете сами, см. инструкцию в файле

Спорные случаи (решаете командой и обосновываете):
  — is_flagged без flag_reason — оставлять, удалять или дополнять?
  — Поля session_*, заполненные у event_type='transaction' — обнулять?

────────────────────────────────────────────────────────────────────
АРХИТЕКТУРНЫЕ ПОДСКАЗКИ

  1. Каждое правило очистки — отдельный метод/функция. Тогда вы сможете
     включать-выключать их через чекбоксы в UI.

  2. Конфиг очистки — отдельный dataclass с булевыми флагами на каждое
     правило. UI на странице Cleaning будет строиться по этому конфигу.

  3. Порядок шагов важен: сначала удаляем мусор (быстро освобождаем
     место), потом исправляем то, что осталось.

  4. Лог одного шага — название, сколько строк было до, сколько стало
     после, сколько модифицировано без удаления.

────────────────────────────────────────────────────────────────────
КАК ЭТО ИСПОЛЬЗУЕТСЯ В UI

    from src.cleaner import DataCleaner, CleaningConfig
    cleaner = DataCleaner()
    df_clean, log = cleaner.clean(df_dirty, config=CleaningConfig(...))
    st.dataframe(log.to_dataframe())

Спроектируйте API так, чтобы получить именно такой вызов.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Tuple, Set, Optional
import pandas as pd
import numpy as np
import re
import src.reference_data as ref
from src.constant_issue import IssueType, DQDimension, CleanType

PIPELINE_ORDER = {
    CleanType.DELETE: 4,      # Сначала выкидываем мусор (уменьшаем объем df)
    CleanType.ZEROING: 1,     # Затем зачищаем невалидные поля
    CleanType.CORRECTION: 2,  # Затем тратим ресурсы на сложный маппинг
    CleanType.IGNORE: 3,      # Игнорируемые можно ставить в самый конец (или вообще не передавать)
}

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

@dataclass
class ClIssue:
  issue_type: IssueType
  resolved_clean_type: CleanType
  affected_indices: pd.Index = field(default_factory=lambda: pd.Index([]))

  @property
  def rows_affected(self) -> int:
    """Количество затронутых строк для конкретного правила."""
    return len(self.affected_indices)

  @property
  def clean_type(self) -> CleanType:
    """Тип действия из CleaningConfig (выбор UI), не tuple из IssueType."""
    return self.resolved_clean_type.value

EnabledCleanRule = Tuple[IssueType, CleanType]

@dataclass
class CleaningConfig:
    """
    Контракт UI → DataCleaner.
    enabled_issues: пары (проблема, способ исправления).
    clean_type должен входить в issue.clean_type (допустимые из constant_issue).
    """

    enabled_issues: Set[EnabledCleanRule] = field(default_factory=set)

    def get_issues_to_clean(self) -> List[EnabledCleanRule]:
        """
        Валидирует пары, сортирует для конвейера.
        Порядок: PIPELINE_ORDER[выбранный CleanType], затем clean_type_pipeline_order issue.
        """

        rules = list(self.enabled_issues)
        for issue, clean_type in rules:
            if clean_type not in issue.clean_type:
                raise ValueError(
                    f"{clean_type.value} недопустим для {issue.name}. "
                    f"Допустимо: {tuple(ct.value for ct in issue.clean_type)}"
                )

        return sorted(
            rules,
            key=lambda pair: (
                PIPELINE_ORDER.get(pair[1], 99),
                pair[0].clean_type_pipeline_order,
            ),
        )

@dataclass
class CleaningLog:
  total_rows_before: int
  total_rows_after: int #Важно - это абсолютное значение оставшегося количества строк, так как
                        #далеко не все методы удаляют строки. Для конкретных изменений необходимо 
                        #ипользовать соотвествующие property
  issues: List[ClIssue] = field(default_factory=list)

  def _total_unique(self, clean_type: CleanType) -> int:
    indices = pd.Index([])
    for issue in self.issues:
      if issue.clean_type == clean_type:
        indices = indices.union(issue.affected_indices)
    return len(indices)

  @property
  def total_all(self) -> int:
    indices = pd.Index([])
    for issue in self.issues:
      indices = indices.union(issue.affected_indices)
    return len(indices)

  @property
  def total_deleted(self) -> int:
    return self._total_unique(CleanType.DELETE)
      
  @property
  def total_zeroed(self) -> int:
    return self._total_unique(CleanType.ZEROING)
      
  @property
  def total_corrected(self) -> int:
    return self._total_unique(CleanType.CORRECTION)
      
  @property
  def total_ignored(self) -> int:
    return self._total_unique(CleanType.IGNORE)

  def to_dataframe(self) -> pd.DataFrame:
    """Контракт для UI и графиков viz.py."""
    if not self.issues:
        return pd.DataFrame(columns=[
            "clean_action", "dimension", "issue_type", "description", "rows_affected"
        ])
        
    df = pd.DataFrame([
        {
            "clean_action": issue.clean_type,
            "dimension": issue.issue_type.dimension,
            "issue_type": issue.issue_type.name,
            "description": issue.issue_type.description,
            # Здесь используем свойство отдельного Issue
            "rows_affected": issue.rows_affected
        }
        for issue in self.issues
    ])
    
    return df.sort_values(by=["clean_action", "rows_affected"], ascending=[True, False]).reset_index(drop=True)

class DataCleaner:
  def clean(self, df: pd.DataFrame, config: CleaningConfig) -> Tuple[pd.DataFrame, CleaningLog]:
    df_clean = df.copy()
    log_issues = []
    initial_rows = len(df_clean)
    # 1. Получаем список ошибок (контракт ГАРАНТИРУЕТ правильный порядок)
    #    Мы просто итерируемся по нему без дополнительной сортировки.
    for issue_type, clean_type in config.get_issues_to_clean():
      # 2. Формируем имя метода (например: "_clean_empty_client_id_zeroing")
      method_name = f"_clean_{issue_type.method_name}_{clean_type.value}"
      
      try:
          clean_method = getattr(self, method_name)
      except AttributeError:
          raise NotImplementedError(
              f"Ошибка архитектуры: метод исправления '{method_name}' "
              f"не реализован в DataCleaner для {issue_type.name}."
          )
      
      # 3. Вызываем метод. Он сам найдет мусор и сам его уберет.
      df_clean, affected_indices = clean_method(df_clean)
      
      # 4. Если строки были изменены, добавляем запись в лог
      if len(affected_indices) > 0:
          log_issues.append(
              ClIssue(
                  issue_type=issue_type,
                  resolved_clean_type=clean_type,
                  affected_indices=affected_indices,
              )
          )
    # Собираем итоговый отчет
    log = CleaningLog(
        total_rows_before=initial_rows,
        total_rows_after=len(df_clean),
        issues=log_issues
    )
    return df_clean, log

  def _zeroing(self, df: pd.DataFrame, mask: pd.Series, columns: tuple) -> Tuple[pd.DataFrame, pd.Index]:
      """Вспомогательный метод для зануления значений по маске."""
      bad_indices = df[mask].index
      if len(bad_indices) > 0:
          for col in columns:
              if col in df.columns:
                  df.loc[bad_indices, col] = np.nan
      return df, bad_indices

  def _correct_amount_rub(self, df: pd.DataFrame, mask: pd.Series, columns: tuple) -> Tuple[pd.DataFrame, pd.Index]:
      negative_mask = (df['amount_rub'] < 0) & mask
      upper_mask = (df['amount_rub'] > 10_000_000) & mask
      bad_indices = df[negative_mask | upper_mask].index
      df.loc[negative_mask, 'amount_rub'] = df.loc[negative_mask, 'amount_rub'].abs()
      df.loc[upper_mask, 'amount_rub'] = df.loc[upper_mask, 'amount_rub'] / 100
      return df, bad_indices

  def _deletion(self, df: pd.DataFrame, mask: pd.Series) -> Tuple[pd.DataFrame, pd.Index]:
      """Вспомогательный метод для удаления строк по маске."""
      bad_indices = df[mask].index
      if len(bad_indices) > 0:
          df = df.drop(index=bad_indices)
      return df, bad_indices

  # COMPLETENESS
  def _clean_empty_event_id_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['event_id'].isnull()) | (df['event_id'] == "")
      return self._deletion(df, mask)

  def _clean_empty_event_id_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['event_id'].isnull()) | (df['event_id'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_EVENT_ID.column)

  def _clean_empty_client_id_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['client_id'].isnull()) | (df['client_id'] == "")
      return self._deletion(df, mask)

  def _clean_empty_client_id_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['client_id'].isnull()) | (df['client_id'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_CLIENT_ID.column)

  def _clean_empty_event_type_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['event_type'].isnull()) | (df['event_type'] == "")
      return self._deletion(df, mask)

  def _clean_empty_event_type_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['event_type'].isnull()) | (df['event_type'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_EVENT_TYPE.column)

  def _clean_empty_event_ts_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['event_ts'].isnull()) | (df['event_ts'] == "")
      return self._deletion(df, mask)

  def _clean_empty_event_ts_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['event_ts'].isnull()) | (df['event_ts'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_EVENT_TS.column)

  def _clean_empty_device_type_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['device_type'].isnull()) | (df['device_type'] == "")
      return self._deletion(df, mask)

  def _clean_empty_device_type_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['device_type'].isnull()) | (df['device_type'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_DEVICE_TYPE.column)

  def _clean_empty_ip_address_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['ip_address'].isnull()) | (df['ip_address'] == "")
      return self._deletion(df, mask)

  def _clean_empty_ip_address_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['ip_address'].isnull()) | (df['ip_address'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_IP_ADDRESS.column)

  def _clean_empty_geo_country_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['geo_country'].isnull()) | (df['geo_country'] == "")
      return self._deletion(df, mask)

  def _clean_empty_geo_country_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['geo_country'].isnull()) | (df['geo_country'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_GEO_COUNTRY.column)

  def _clean_empty_geo_city_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['geo_city'].isnull()) | (df['geo_city'] == "")
      return self._deletion(df, mask)

  def _clean_empty_geo_city_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['geo_city'].isnull()) | (df['geo_city'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_GEO_CITY.column)

  def _clean_empty_channel_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['channel'].isnull()) | (df['channel'] == "")
      return self._deletion(df, mask)

  def _clean_empty_channel_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['channel'].isnull()) | (df['channel'] == "")
      return self._zeroing(df, mask, IssueType.EMPTY_CHANNEL.column)

  def _clean_empty_amount_rub_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['amount_rub'].isnull()) | (df['amount_rub'] == "")) & (df['event_type'] == "transaction")
      return self._deletion(df, mask)

  def _clean_empty_amount_rub_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['amount_rub'].isnull()) | (df['amount_rub'] == "")) & (df['event_type'] == "transaction")
      return self._zeroing(df, mask, IssueType.EMPTY_AMOUNT_RUB.column)

  def _clean_empty_currency_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['currency'].isnull()) | (df['currency'] == "")) & (df['event_type'] == "transaction")
      return self._deletion(df, mask)

  def _clean_empty_currency_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['currency'].isnull()) | (df['currency'] == "")) & (df['event_type'] == "transaction")
      return self._zeroing(df, mask, IssueType.EMPTY_CURRENCY.column)

  def _clean_empty_merchant_category_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['merchant_category'].isnull()) | (df['merchant_category'] == "")) & (df['event_type'] == "transaction")
      return self._deletion(df, mask)

  def _clean_empty_merchant_category_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['merchant_category'].isnull()) | (df['merchant_category'] == "")) & (df['event_type'] == "transaction")
      return self._zeroing(df, mask, IssueType.EMPTY_MERCHANT_CATEGORY.column)

  def _clean_empty_merchant_country_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['merchant_country'].isnull()) | (df['merchant_country'] == "")) & (df['event_type'] == "transaction")
      return self._deletion(df, mask)

  def _clean_empty_merchant_country_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['merchant_country'].isnull()) | (df['merchant_country'] == "")) & (df['event_type'] == "transaction")
      return self._zeroing(df, mask, IssueType.EMPTY_MERCHANT_COUNTRY.column)

  def _clean_empty_card_last4_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['card_last4'].isnull()) | (df['card_last4'] == "")) & (df['event_type'] == "transaction")
      return self._deletion(df, mask)

  def _clean_empty_card_last4_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['card_last4'].isnull()) | (df['card_last4'] == "")) & (df['event_type'] == "transaction")
      return self._zeroing(df, mask, IssueType.EMPTY_CARD_LAST4.column)

  def _clean_empty_session_start_ts_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['session_start_ts'].isnull()) | (df['session_start_ts'] == "")) & (df['event_type'] == "session")
      return self._deletion(df, mask)

  def _clean_empty_session_start_ts_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['session_start_ts'].isnull()) | (df['session_start_ts'] == "")) & (df['event_type'] == "session")
      return self._zeroing(df, mask, IssueType.EMPTY_SESSION_START_TS.column)

  def _clean_empty_session_end_ts_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['session_end_ts'].isnull()) | (df['session_end_ts'] == "")) & (df['event_type'] == "session")
      return self._deletion(df, mask)

  def _clean_empty_session_end_ts_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['session_end_ts'].isnull()) | (df['session_end_ts'] == "")) & (df['event_type'] == "session")
      return self._zeroing(df, mask, IssueType.EMPTY_SESSION_END_TS.column)

  def _clean_empty_login_success_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['login_success'].isnull()) & (df['event_type'] == "session")
      return self._deletion(df, mask)

  def _clean_empty_login_success_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = (df['login_success'].isnull()) & (df['event_type'] == "session")
      return self._zeroing(df, mask, IssueType.EMPTY_LOGIN_SUCCESS.column)

  def _clean_empty_auth_method_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['auth_method'].isnull()) | (df['auth_method'] == "")) & (df['event_type'] == "session")
      return self._deletion(df, mask)

  def _clean_empty_auth_method_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['auth_method'].isnull()) | (df['auth_method'] == "")) & (df['event_type'] == "session")
      return self._zeroing(df, mask, IssueType.EMPTY_AUTH_METHOD.column)

  def _clean_empty_flag_reason_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['flag_reason'].isnull()) | (df['flag_reason'] == "")) & (df['is_flagged'] == True)
      return self._deletion(df, mask)

  def _clean_empty_flag_reason_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = ((df['flag_reason'].isnull()) | (df['flag_reason'] == "")) & (df['is_flagged'] == True)
      return self._zeroing(df, mask, IssueType.EMPTY_FLAG_REASON.column)

  # VALIDITY
  def _clean_invalid_event_type_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = df['event_type'].isnull() | (df['event_type'] == "")
      mask = ~is_empty & ~df['event_type'].astype(str).isin(ref.VALID_EVENT_TYPES)
      return self._deletion(df, mask)

  def _clean_invalid_format_date_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      parsed = pd.to_datetime(df['event_ts'], format='%Y-%m-%d %H:%M:%S', errors='coerce')
      mask1 = parsed.isna()
      if mask1.any():
          parsed2 = pd.to_datetime(df['event_ts'], format='%Y-%m-%d %H:%M', errors='coerce')
          parsed[mask1] = parsed2
      mask = parsed.isna() & df['event_ts'].notna() & (df['event_ts'].astype(str).str.strip() != "")
      return self._zeroing(df, mask, IssueType.INVALID_FORMAT_DATE.column)

  def _clean_invalid_session_start_ts_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = df['session_start_ts'].isnull() | (df['session_start_ts'].astype(str).str.strip() == "")
      parsed = pd.to_datetime(df['session_start_ts'], errors='coerce')
      mask = ~is_empty & parsed.isna()
      return self._zeroing(df, mask, IssueType.INVALID_SESSION_START_TS.column)

  def _clean_invalid_session_end_ts_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = df['session_end_ts'].isnull() | (df['session_end_ts'].astype(str).str.strip() == "")
      parsed = pd.to_datetime(df['session_end_ts'], errors='coerce')
      mask = ~is_empty & parsed.isna()
      return self._zeroing(df, mask, IssueType.INVALID_SESSION_END_TS.column)

  def _clean_invalid_ip_address_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
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
      return self._zeroing(df, mask, IssueType.INVALID_IP_ADDRESS.column)

  def _clean_invalid_amount_rub_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = (df['amount_rub'].isna()) | (df['amount_rub'] == "")
      mask = ~(is_empty) & ((df['amount_rub'] < 0.01) | (df['amount_rub'] >= 10_000_000))
      return self._zeroing(df, mask, IssueType.INVALID_AMOUNT_RUB.column)

  def _clean_invalid_amount_rub_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = (df['amount_rub'].isna()) | (df['amount_rub'] == "")
      mask = ~(is_empty)
      return self._correct_amount_rub(df, mask, IssueType.INVALID_AMOUNT_RUB.column)

  def _clean_invalid_channel_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = (df['channel'].isna()) | (df['channel'] == "")
      mask = ~is_empty & ~df['channel'].astype(str).isin(ref.VALID_CHANNELS)
      return self._zeroing(df, mask, IssueType.INVALID_CHANNEL.column)

  def _clean_invalid_currency_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = (df['currency'].isna()) | (df['currency'] == "")
      mask = ~(is_empty) & ~(df['currency'].astype(str).isin(ref.VALID_CURRENCIES))
      bad_indices = df.index[mask]
      if len(bad_indices) > 0:
          df.loc[bad_indices, 'currency'] = df.loc[bad_indices, 'currency'].replace(ref.CURRENCY_MAPPING)
          still_invalid = ~df.loc[bad_indices, 'currency'].astype(str).isin(ref.VALID_CURRENCIES)
          if still_invalid.any():
              df.loc[bad_indices[still_invalid], 'currency'] = np.nan
      return df, bad_indices

  def _clean_invalid_merchant_category_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = (df['merchant_category'].isna()) | (df['merchant_category'] == "")
      mask = ~(is_empty) & ~(df['merchant_category'].astype(str).isin(ref.VALID_MERCHANT_CATEGORIES))
      bad_indices = df.index[mask]
      if len(bad_indices) > 0:
          df.loc[bad_indices, 'merchant_category'] = df.loc[bad_indices, 'merchant_category'].replace(ref.MCC_ISO_TO_TEXT)
          still_invalid = ~df.loc[bad_indices, 'merchant_category'].astype(str).isin(ref.VALID_MERCHANT_CATEGORIES)
          if still_invalid.any():
              df.loc[bad_indices[still_invalid], 'merchant_category'] = np.nan
      return df, bad_indices

  def _clean_invalid_device_type_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = (df['device_type'].isna()) | (df['device_type'] == "")
      mask = ~(is_empty) & ~(df['device_type'].astype(str).isin(ref.VALID_DEVICE_TYPES))
      bad_indices = df.index[mask]
      if len(bad_indices) > 0:
          df.loc[bad_indices, 'device_type'] = df.loc[bad_indices, 'device_type'].astype(str).str.lower()
          still_invalid = ~df.loc[bad_indices, 'device_type'].astype(str).isin(ref.VALID_DEVICE_TYPES)
          if still_invalid.any():
              df.loc[bad_indices[still_invalid], 'device_type'] = np.nan
      return df, bad_indices

  def _clean_invalid_card_last4_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      # Политика CORRECTION: только цифры, длина < 4 → дополнение нулями слева ('42' → '0042') или зануление, в случаях, когда нельзя исправить.
      txn_mask = df['event_type'] == 'transaction'
      series = df['card_last4'].astype('string')
      is_empty = series.isna() | (series.str.strip() == '')
      is_digits = series.str.match(r'^\d+$', na=False)
      can_pad = txn_mask & ~is_empty & is_digits & (series.str.len() < 4)
      zero = txn_mask & ~is_empty & ((series.str.len() > 4) | (~is_digits))
      bad_indices = df.index[can_pad | zero]
      if len(can_pad) > 0:
          df.loc[can_pad, 'card_last4'] = series.loc[can_pad].str.zfill(4)
      if len(zero) > 0:
          df.loc[zero, 'card_last4'] = np.nan
      return df, bad_indices

  def _clean_invalid_geo_country_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
    series = df['geo_country']
    is_empty = series.isna() | (series == "")

    lower = series.str.lower()
    canonical = lower.map(ref.GEO_COUNTRY_BY_LOWER)
    mask = ~is_empty & (canonical.isna() | (series != canonical))
    bad_indices = df.index[mask]

    if len(bad_indices) > 0:
        df.loc[bad_indices, 'geo_country'] = lower.loc[bad_indices].map(ref.GEO_COUNTRY_BY_LOWER)
        still_invalid = df.loc[bad_indices, 'geo_country'].isna()
        if still_invalid.any():
            df.loc[bad_indices[still_invalid], 'geo_country'] = np.nan

    return df, bad_indices

  # CONSISTENCY
  def _clean_inconsistency_flagged_field_zeroing(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      is_empty = (df['flag_reason'].isna()) | (df['flag_reason'] == "")
      mask = (df['is_flagged'] == False) & ~is_empty
      # We just want to zero flag_reason, so we pass it explicitly.
      return self._zeroing(df, mask, ('flag_reason',))

  def _clean_inconsistency_transaction_field_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      transaction_mask = df['event_type'] == 'transaction'
      session_fields = ['session_start_ts', 'session_end_ts', 'login_success', 'auth_method']
      
      has_session_data = pd.Series([False] * len(df), index=df.index)
      for field in session_fields:
          if field in df.columns:
              has_session_data = has_session_data | (df[field].notna() & (df[field].astype(str).str.strip() != ""))
              
      mask = transaction_mask & has_session_data
      return self._zeroing(df, mask, tuple(session_fields))

  def _clean_inconsistency_session_field_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      session_mask = df['event_type'] == 'session'
      transaction_fields = ['amount_rub', 'currency', 'merchant_category', 'merchant_country', 'card_last4']
      
      has_transaction_data = pd.Series([False] * len(df), index=df.index)
      for field in transaction_fields:
          if field in df.columns:
              has_transaction_data = has_transaction_data | (df[field].notna() & (df[field].astype(str).str.strip() != ""))
              
      mask = session_mask & has_transaction_data
      return self._zeroing(df, mask, tuple(transaction_fields))

  def _clean_inconsistency_session_timestamps_correction(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      session_mask = df['event_type'] == 'session'
      both_present = df['session_start_ts'].notna() & df['session_end_ts'].notna() \
                     & (df['session_start_ts'].astype(str).str.strip() != "") \
                     & (df['session_end_ts'].astype(str).str.strip() != "")
      start = pd.to_datetime(df['session_start_ts'], errors='coerce')
      end   = pd.to_datetime(df['session_end_ts'],   errors='coerce')
      mask = session_mask & both_present & start.notna() & end.notna() & (end < start)
      bad_indices = df.index[mask]
      if len(bad_indices) > 0:
          temp = df.loc[bad_indices, 'session_start_ts'].copy()
          df.loc[bad_indices, 'session_start_ts'] = df.loc[bad_indices, 'session_end_ts']
          df.loc[bad_indices, 'session_end_ts'] = temp
      return df, bad_indices

  # UNIQUENESS
  def _clean_full_duplicate_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      mask = df.duplicated(keep='first')
      return self._deletion(df, mask)

  def _clean_event_id_duplicate_ignore(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      full_duplicates_mask = df.duplicated(keep='first')
      df_no_full_dups = df[~full_duplicates_mask]
      if len(df_no_full_dups) == 0:
          return df, pd.Index([])
          
      bad_indices = df_no_full_dups.index[
          df_no_full_dups['event_id'].duplicated(keep='first') & 
          df_no_full_dups['event_id'].notna() & 
          (df_no_full_dups['event_id'] != "")
      ]
      
      if len(bad_indices) > 0:
          # IGNORE - мы ничего не делаем с данными, но возвращаем индексы для лога
          pass
      return df, bad_indices

  def _clean_event_id_duplicate_delete(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Index]:
      full_duplicates_mask = df.duplicated(keep='first')
      df_no_full_dups = df[~full_duplicates_mask]
      event_id_counts = df_no_full_dups['event_id'].value_counts()
      duplicate_event_ids = event_id_counts[event_id_counts > 1].index.tolist()
      if not duplicate_event_ids:
          return df, pd.Index([])
      rows_to_delete = pd.Series(False, index=df.index)
      for event_id in duplicate_event_ids:
          event_rows = df_no_full_dups[df_no_full_dups['event_id'] == event_id]
          indices = event_rows.index.tolist()
          if len(indices) <= 1:
              continue
          best_idx = None
          min_empty = float('inf')
          for idx in indices:
              row = event_rows.loc[idx]
              empty_count = 0
              for col in df.columns:
                  if col == 'event_id':
                      continue
                  val = row[col]
                  if pd.isna(val) or val == "":
                      empty_count += 1
              if empty_count < min_empty:
                  min_empty = empty_count
                  best_idx = idx

          for idx in indices:
              if idx != best_idx:
                  rows_to_delete[idx] = True
      removed_indices = df.index[rows_to_delete]
      df_cleaned = df[~rows_to_delete]
      return df_cleaned, removed_indices
