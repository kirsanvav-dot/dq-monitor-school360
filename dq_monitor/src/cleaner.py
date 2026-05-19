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
from typing import List, Tuple
import pandas as pd
from typing import Set, List, Optional
from src.constant_issue import IssueType, DQDimension, CleanType

PIPELINE_ORDER = {
    CleanType.DELETE: 1,      # Сначала выкидываем мусор (уменьшаем объем df)
    CleanType.ZEROING: 2,     # Затем зачищаем невалидные поля
    CleanType.CORRECTION: 3,  # Затем тратим ресурсы на сложный маппинг
    CleanType.IGNORE: 4,      # Игнорируемые можно ставить в самый конец (или вообще не передавать)
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
  affected_indices: pd.Index = field(default_factory=lambda: pd.Index([]))
  @property
  def rows_affected(self) -> int:
    """Количество затронутых строк для конкретного правила."""
    return len(self.affected_indices)
      
  @property
  def clean_type(self) -> CleanType:
    """Тип действия прокидываем напрямую из константы ошибки."""
    return self.issue_type.clean_type

@dataclass
class CleaningConfig:
    """
    Контракт между UI и DataCleaner.
    Определяет, какие проблемы качества данных мы собираемся исправлять.
    """
    enabled_dimensions: Set[DQDimension] = field(default_factory=set)
    enabled_issues: Set[IssueType] = field(default_factory=set)
    disabled_issues: Set[IssueType] = field(default_factory=set)
    def get_issues_to_clean(self) -> List[IssueType]:
        """
        Резолвер: собирает и сортирует список проблем для исправления.
        
        АРХИТЕКТУРНОЕ РЕШЕНИЕ: 
        Обеспечением порядка конвейера (сначала удаление, затем зануление, 
        и только в конце - ресурсоемкое восстановление) занимается ИМЕННО ЭТОТ метод.
        Обработчик (DataCleaner) не должен сам перетасовывать правила, он 
        доверяет порядку, который пришел из контракта.
        """
        issues_to_clean = set()
        
        # Шаг 1: Сбор проблем из измерений
        if self.enabled_dimensions:
            for issue in IssueType:
                if issue.dimension in self.enabled_dimensions:
                    issues_to_clean.add(issue)
                    
        # Шаг 2: Добавление точечных проблем
        if self.enabled_issues:
            issues_to_clean.update(self.enabled_issues)
            
        # Шаг 3: Удаление исключений
        if self.disabled_issues:
            issues_to_clean.difference_update(self.disabled_issues)
            
        # Шаг 4: ГАРАНТИЯ ПОРЯДКА КОНВЕЙЕРА
        # Сортируем собранный set по весу CleanType, заданному в PIPELINE_ORDER
        sorted_issues = sorted(
            list(issues_to_clean),
            key=lambda issue: PIPELINE_ORDER.get(issue.clean_type, 99)
        )
        
        return sorted_issues

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
    # 1. Получаем список ошибок (контракт ГАРАНТИРУЕТ правильный порядок: 
    #    сначала DELETE, затем ZEROING, затем CORRECTION).
    #    Мы просто итерируемся по нему без дополнительной сортировки.
    issues_to_clean: List[IssueType] = config.get_issues_to_clean()
    for issue_type in issues_to_clean:
      # 2. Формируем имя метода (например: "_clean_empty_client_id")
      method_name = f"_clean_{issue_type.method_name}"
      
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
                  affected_indices=affected_indices
              )
          )
    # Собираем итоговый отчет
    log = CleaningLog(
        total_rows_before=initial_rows,
        total_rows_after=len(df_clean),
        issues=log_issues
    )
    return df_clean, log

  def _delete_zero_column(issue: ClIssue, df: pd.DataFrame) -> pd.DataFrame:
     column = issue.issue_type.column[0]
     mask = (df[column].isnull()) | (df[column] == "")
     del_index = df[mask].index
     filtered_df = df.drop(index=del_index)
     return filtered_df