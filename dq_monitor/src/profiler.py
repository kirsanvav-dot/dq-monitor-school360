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
from dataclasses import dataclass
from enum import Enum
import pandas as pd

#FIXME обоснование использования таких классов: другие части приложения
#будут взаимодействовать с данными ошибками и чтобы их определять и не 
#иметь проблем с опечатками мы используем переменные как константы
class DQDimension(str, Enum):
    "класс констант измерений"
    COMPLETENESS = "Completeness"
    VALIDITY = "Validity"
    CONSISTENCY = "Consistency"
    UNIQUENESS = "Uniqueness"

class IssueType(Enum):
    """
    Класс констант типов ошибок.
    Значение (value) — это кортеж: (имя_для_метода, описание_для_ui, измерение)
    """
    # Пример создания:
    BAD_FORMAT_DATE = ("bad_format_date", "Неверный формат данных времени", DQDimension.VALIDITY)

    @property
    def method_name(self) -> str:
        """Служебное имя, используется для поиска метода (например, 'bad_format_date')."""
        return self.value[0]
        
    @property
    def description(self) -> str:
        """Человекочитаемое описание для UI."""
        return self.value[1]
        
    @property
    def dimension(self) -> DQDimension:
        """Тип измерения качества."""
        return self.value[2]

#TODO сами типы определяются DQ



ALL = "all" #служебное определение для column, если нет четкого столбца

#Датакласс для одной ошибки
@dataclass
class Issue:
    issue_type: IssueType
    column: str          # В какой колонке найдено ("currency" / ALL)
    rows_affected: int   # Количество затронутых строк
    
    @property
    def dimension(self) -> DQDimension:
        return self.issue_type.dimension
        
    @property
    def description(self) -> str:
        return self.issue_type.description

@dataclass
class Report:
    total_rows: int
    issues: List[Issue]
    
    def to_dataframe(self) -> pd.DataFrame:
        if not self.issues:
            return pd.DataFrame(columns=["Измерение", "Тип", "Колонка", "Описание", "Затронуто строк"])
            
        return pd.DataFrame([
            {
                "Измерение": issue.dimension.value,
                "Тип": issue.issue_type.name,  # Имя константы (например, 'BAD_FORMAT_DATE')
                "Колонка": issue.column,
                "Описание": issue.description,
                "Затронуто строк": issue.rows_affected
            }
            for issue in self.issues
        ])

#TODO Основная идея архитектуры:
#DQ реализует только сами  issue в виде констант и функций
#не задумываясь о том, как данные будут затем передаваться и обрабатываться
class DataProfiler():
    def profile(self, df: pd.DataFrame) -> Report:
      issues = []
      # Список обхода поиска ошибок
      checks_to_run: list[IssueType] = [
          IssueType.BAD_FORMAT_DATE,
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

#пример реализации метода проверки
def _check_bad_format_date(self, df: pd.DataFrame) -> Optional[Issue]:
    """Проверяет колонку event_ts на битые даты."""
    parsed = pd.to_datetime(df['event_ts'], errors='coerce')
    mask = parsed.isna() & df['event_ts'].notna() & (df['event_ts'] != "")
    count = int(mask.sum())
    
    if count > 0:
        return Issue(
            issue_type=IssueType.BAD_FORMAT_DATE,
            column="event_ts",
            rows_affected=count
        )
    return None