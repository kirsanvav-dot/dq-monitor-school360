from enum import Enum

#FIXME обоснование использования таких классов: другие части приложения
#будут взаимодействовать с данными ошибками и чтобы их определять и не 
#иметь проблем с опечатками мы используем переменные как константы
class DQDimension(str, Enum):
    "класс констант измерений"
    COMPLETENESS = "Completeness"
    VALIDITY = "Validity"
    CONSISTENCY = "Consistency"
    UNIQUENESS = "Uniqueness"

ALL = "all" #служебное определение для column, если нет четкого столбца

class IssueType(Enum):
    """
    Класс констант типов ошибок.
    Значение (value) — это кортеж: (имя_для_метода, 
    описание_для_ui, 
    измерение,
    колонка tuple (currency / ALL))
    """
    # Пример создания:
    BAD_FORMAT_DATE = ("bad_format_date", "Неверный формат данных времени", DQDimension.VALIDITY, ("event_ts",))

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
    
    @property
    def column(self) -> tuple:
        """В какой колонке найдено ("currency" / ALL)"""
        return self.value[3]

#TODO сами типы определяются DQ