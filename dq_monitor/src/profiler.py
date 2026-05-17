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


#Датакласс для одной ошибки
@dataclass
class DQIssue:
    issue_type: IssueType
    rows_affected: int   # Количество затронутых строк
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
          return pd.DataFrame(columns=["Измерение", "Тип", "Колонка", "Описание", "Затронуто строк", "% от всех строк"])
          
      df = pd.DataFrame([
          {
              "Измерение": issue.issue_type.dimension,
              "Тип": issue.issue_type.name,  
              "Колонка": issue.issue_type.column,
              "Описание": issue.issue_type.description,
              "Затронуто строк": issue.rows_affected,
              "% от всех строк": round((issue.rows_affected / self.total_rows) * 100, 2) if self.total_rows > 0 else 0
          }
          for issue in self.issues
      ])
      
      # Группируем (сортируем) проблемы по измерениям для удобного отображения в UI
      return df.sort_values(by=["Измерение", "Затронуто строк"], ascending=[True, False]).reset_index(drop=True)

#TODO Основная идея архитектуры:
#DQ реализует только сами  issue в виде констант и функций
#не задумываясь о том, как данные будут затем передаваться и обрабатываться
class DataProfiler():
  def profile(self, df: pd.DataFrame) -> Report:
    issues = []
    # Список обхода поиска ошибок
    checks_to_run: list[IssueType] = [
        IssueType.EMPTY_EVENT_ID,
        IssueType.EMPTY_CLIENT_ID,
        IssueType.EMPTY_EVENT_TS,
        IssueType.EMPTY_EVENT_TYPE,
        IssueType.EMPTY_DEVICE_TYPE,
        IssueType.EMPTY_GEO_COUNTRY,
        IssueType.EMPTY_GEO_CITY,
        IssueType.EMPTY_CHANNEL,
        IssueType.EMPTY_AMOUNT_RUB,
        IssueType.EMPTY_CURRENCY,
        IssueType.EMPTY_MERCHANT_CATEGORY,
        IssueType.EMPTY_MERCHANT_COUNTRY,
        IssueType.EMPTY_CARD_LAST4,
        IssueType.EMPTY_SESSION_START,
        IssueType.EMPTY_SESSION_END,
        IssueType.EMPTY_LOGIN_SUCCESS,
        IssueType.EMPTY_AUTH_METHOD,
        IssueType.EMPTY_FLAG_REASON,
        IssueType.EMPTY_STRING,

        # Validity
        IssueType.INVALID_DATE,
        IssueType.INVALID_FUTURE_DATE,
        IssueType.INVALID_IP_ADDRESS,
        IssueType.INVALID_CURRENCY,
        IssueType.NEGATIVE_AMOUNT,
        IssueType.ANOMALOUS_AMOUNT,
        IssueType.INVALID_EVENT_TYPE,
        IssueType.INVALID_DEVICE_TYPE,
        IssueType.INVALID_AUTH_METHOD,
        IssueType.NUMERIC_MERCHANT_CATEGORY,
        IssueType.INVALID_CARD_FORMAT,

        # Consistency
        IssueType.INCONSISTENT_FLAG,
        IssueType.MISSING_FLAG_REASON_WHEN_FLAGGED,
        IssueType.TRANSACTION_HAS_SESSION_FIELDS,
        IssueType.SESSION_HAS_TRANSACTION_FIELDS,
        IssueType.INVALID_SESSION_TIMESTAMP,

        # Uniqueness
        IssueType.DUPLICATE_EVENT_ID,
        IssueType.DUPLICATE_FULL_ROW,
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


  def _check_empty_event_id(self, df: pd.DataFrame):
      mask = (df['event_id'].isnull()) or (df['event_id'] == "")


#пример реализации метода проверки
def _check_bad_format_date(self, df: pd.DataFrame) -> Optional[DQIssue]:
    parsed = pd.to_datetime(df['event_ts'], errors='coerce')
    mask = parsed.isna() & df['event_ts'].notna() & (df['event_ts'] != "")
    
    # Получаем индексы строк, где маска == True
    bad_indices = df.index[mask]
    count = len(bad_indices)
    
    if count > 0:
        return DQIssue(
            issue_type=IssueType.BAD_FORMAT_DATE,
            column="event_ts",
            affected_indices=bad_indices  # Передаем индексы!
        )
    return None