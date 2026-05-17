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

    #Completeness
    EMPTY_EVENT_ID = ('empty_event_id', "Пропущено обязательное значение event_id", DQDimension.COMPLETENESS, ('event_id'))
    EMPTY_CLIENT_ID = ('empty_client_id', "Пропущено обязательное значение client_id", DQDimension.COMPLETENESS, ('client_id'))
    EMPTY_EVENT_TS = ('empty_event_ts', "Пропущено обязательное значение event_ts", DQDimension.COMPLETENESS, ('event_ts'))
    EMPTY_DEVICE_TYPE = ('empty_device_type', "Пропущено обязательное значение device_type", DQDimension.COMPLETENESS, ('device_type'))
    EMPTY_GEO_CITY = ('empty_geo_city', "Пропущено обязательное значение geo_city", DQDimension.COMPLETENESS, ('geo_city'))
    EMPTY_AMOUNT_RUB = ('empty_amount_rub', "Пропущено обязательное значение amount_rub при типе операции transaction",
                        DQDimension.COMPLETENESS, ('amount_rub'))
    EMPTY_CURRENCY = ('empty_currency', "Пропущено обязательное значение currency при типе операции transaction",
                      DQDimension.COMPLETENESS, ('currency'))
    EMPTY_FLAG_REASON = ('empty_flag_reason', 'Пропущено обязательное значение flag_reason при is_flagged == true',
                         DQDimension.COMPLETENESS, ('flag_reason'))

    # VALIDITY
    INVALID_FORMAT_DATE = ("bad_format_date", "Неверный формат данных времени", DQDimension.VALIDITY, ('event_ts'))
    INVALID_IP_ADDRESS = ("invalid_ip_address", "Некорректный формат ip-адреса", DQDimension.VALIDITY, ('ip_address'))
    INVALID_AMOUNT_RUB = ("invalid_amount_rub", "Выход за пределы допустимых значений", DQDimension.VALIDITY, ('amount_rub'))
    INVALID_CURRENT = ("invalid_current", "Некорректный формат значения currency", DQDimension.VALIDITY, ('currency'))
    INVALID_MERCHANT_CATEGORY = ("invalid_merchant_category", "Некорректный формат merchant_category",
                                 DQDimension.VALIDITY, ('merchant_category'))
    INVALID_CARD_LAST4 = ("invalid_card_4last", "Некорректный формат card_last4", DQDimension.VALIDITY, ('card_last4'))

    # CONSISTENCY
    INCONSISTENCY_FLAGGED = ('inconsistency_flagged_field', "Несогласованны поля is_flagged и flagged_reason",
                             DQDimension.CONSISTENCY, ('is_flagged', 'flagged_reason'))
    INCONSISTENCY_TRANSACTION = ('inconsistency_transaction_field',
                                 "При типе операции transaction заполнены поля, соответствующие типу session",
                                 DQDimension.CONSISTENCY, ('event_type', 'session_start_ts', 'session_end_ts', 'login_success', 'auth_method'))
    INCONSISTENCY_SESSION = ('inconsistency_session_field',
                             "При типе операции transaction заполнены поля, соответствующие типу transaction",
                             DQDimension.CONSISTENCY, ('event_type', 'amount_rub', 'currency', 'merchant_category', 'merchant_country', 'card_last4', ))

    # UNIQUENESS
    DUPLICATE_FULL = ('full_duplicate', 'Наличие дубликатов строк', DQDimension.UNIQUENESS, ('all'))
    DUPLICATE_EVENT_ID = ('event_id_duplicate', 'Не уникальный event_id при различных операциях',
                          DQDimension.UNIQUENESS, ('event_id'))

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