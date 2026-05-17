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
  
  # 1. Если UI включает исправления целыми блоками (измерениями)
  enabled_dimensions: Set[DQDimension] = field(default_factory=set)
  
  # 2. Если UI включает исправления точечно (конкретные галочки)
  enabled_issues: Set[IssueType] = field(default_factory=set)
  
  # 3. Исключения (например, включили весь Completeness, но сняли галочку с одного поля)
  disabled_issues: Set[IssueType] = field(default_factory=set)
  def get_issues_to_clean(self) -> List[IssueType]:
    """Резолвер: собирает итоговый список проблем, которые нужно исправить."""
    issues_to_clean = set()
    
    # Шаг 1: Добавляем все проблемы из включенных измерений
    if self.enabled_dimensions:
        for issue in IssueType:
            if issue.dimension in self.enabled_dimensions:
                issues_to_clean.add(issue)
                
    # Шаг 2: Добавляем точечно выбранные проблемы
    if self.enabled_issues:
        issues_to_clean.update(self.enabled_issues)
        
    # Шаг 3: Удаляем то, что попало в исключения
    if self.disabled_issues:
        issues_to_clean.difference_update(self.disabled_issues)
        
    return list(issues_to_clean)

@dataclass
class CleaningLog:
  total_rows_before: int
  total_rows_after: int
  issues: List[ClIssue] = field(default_factory=list)

  def _total_unique(self, clean_type: CleanType) -> int:
    indices = pd.Index([])
    for issue in self.issues:
        if issue.clean_type == clean_type:
          indices = indices.union(issue.affected_indices)

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