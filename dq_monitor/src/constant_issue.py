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

# Класс типов применяемых действий при очистке
#TODO прописать их в константах
class CleanType(str, Enum):
    #TODO Определить четкий набор правил
    DELETE = "delete" #удаляет строку целиком
    ZEROING = "zeroing" #set Nan
    CORRECTION = "correction"
    IGNORE = "ignore"

ALL = "all" #служебное определение для column, если нет четкого столбца

class IssueType(Enum):
    """
    Класс констант типов ошибок.
    Значение (value) — это кортеж: (имя_для_метода, 
    описание_для_ui, 
    измерение,
    колонка tuple (currency / ALL)),
    тип исправления

    """

   # Completeness — глобально обязательные поля (для всех типов событий)
    EMPTY_EVENT_ID = ('empty_event_id', "Пропущено обязательное значение event_id", DQDimension.COMPLETENESS, ('event_id',), CleanType.DELETE)
    EMPTY_CLIENT_ID = ('empty_client_id', "Пропущено обязательное значение client_id", DQDimension.COMPLETENESS, ('client_id',), CleanType.ZEROING)
    EMPTY_EVENT_TYPE = ('empty_event_type', "Пропущено обязательное значение event_type", DQDimension.COMPLETENESS, ('event_type',), CleanType.DELETE)
    EMPTY_EVENT_TS = ('empty_event_ts', "Пропущено обязательное значение event_ts", DQDimension.COMPLETENESS, ('event_ts',), CleanType.ZEROING)
    EMPTY_DEVICE_TYPE = ('empty_device_type', "Пропущено обязательное значение device_type", DQDimension.COMPLETENESS, ('device_type',), CleanType.ZEROING)
    EMPTY_IP_ADDRESS = ('empty_ip_address', "Пропущено обязательное значение ip_address", DQDimension.COMPLETENESS, ('ip_address',), CleanType.ZEROING)
    EMPTY_GEO_COUNTRY = ('empty_geo_country', "Пропущено обязательное значение geo_country", DQDimension.COMPLETENESS, ('geo_country',), CleanType.ZEROING)
    EMPTY_GEO_CITY = ('empty_geo_city', "Пропущено обязательное значение geo_city", DQDimension.COMPLETENESS, ('geo_city',), CleanType.ZEROING)
    EMPTY_CHANNEL = ('empty_channel', "Пропущено обязательное значение channel", DQDimension.COMPLETENESS, ('channel',), CleanType.ZEROING)
    # Completeness — обязательные поля только для транзакций
    EMPTY_AMOUNT_RUB = ('empty_amount_rub', "Пропущено обязательное значение amount_rub при типе операции transaction",
                        DQDimension.COMPLETENESS, ('amount_rub',), CleanType.ZEROING)
    EMPTY_CURRENCY = ('empty_currency', "Пропущено обязательное значение currency при типе операции transaction",
                      DQDimension.COMPLETENESS, ('currency',), CleanType.ZEROING)
    EMPTY_MERCHANT_CATEGORY = ('empty_merchant_category', "Пропущено обязательное значение merchant_category при типе операции transaction",
                               DQDimension.COMPLETENESS, ('merchant_category',), CleanType.ZEROING)
    EMPTY_MERCHANT_COUNTRY = ('empty_merchant_country', "Пропущено обязательное значение merchant_country при типе операции transaction",
                              DQDimension.COMPLETENESS, ('merchant_country',), CleanType.ZEROING)
    EMPTY_CARD_LAST4 = ('empty_card_last4', "Пропущено обязательное значение card_last4 при типе операции transaction",
                        DQDimension.COMPLETENESS, ('card_last4',), CleanType.ZEROING)
    # Completeness — обязательные поля только для сессий
    EMPTY_SESSION_START_TS = ('empty_session_start_ts', "Пропущено обязательное значение session_start_ts при типе операции session",
                              DQDimension.COMPLETENESS, ('session_start_ts',), CleanType.ZEROING)
    EMPTY_SESSION_END_TS = ('empty_session_end_ts', "Пропущено обязательное значение session_end_ts при типе операции session",
                            DQDimension.COMPLETENESS, ('session_end_ts',), CleanType.ZEROING)
    EMPTY_LOGIN_SUCCESS = ('empty_login_success', "Пропущено обязательное значение login_success при типе операции session",
                           DQDimension.COMPLETENESS, ('login_success',), CleanType.ZEROING)
    EMPTY_AUTH_METHOD = ('empty_auth_method', "Пропущено обязательное значение auth_method при типе операции session",
                         DQDimension.COMPLETENESS, ('auth_method',), CleanType.ZEROING)
    EMPTY_FLAG_REASON = ('empty_flag_reason', 'Пропущено обязательное значение flag_reason при is_flagged == true',
                         DQDimension.COMPLETENESS, ('flag_reason',), CleanType.ZEROING)
    # VALIDITY
    INVALID_EVENT_TYPE = ('invalid_event_type', "Значение event_type не входит в допустимые типы событий",
                          DQDimension.VALIDITY, ('event_type',), CleanType.DELETE)
    INVALID_FORMAT_DATE = ("invalid_format_date", "Некорректный формат данных времени event_ts", DQDimension.VALIDITY, ('event_ts',), CleanType.ZEROING)
    INVALID_SESSION_START_TS = ('invalid_session_start_ts', "Некорректный формат session_start_ts",
                                DQDimension.VALIDITY, ('session_start_ts',), CleanType.ZEROING)
    INVALID_SESSION_END_TS = ('invalid_session_end_ts', "Некорректный формат session_end_ts",
                              DQDimension.VALIDITY, ('session_end_ts',), CleanType.ZEROING)
    INVALID_IP_ADDRESS = ("invalid_ip_address", "Некорректный формат ip-адреса", DQDimension.VALIDITY, ('ip_address',), CleanType.ZEROING)
    INVALID_AMOUNT_RUB = ("invalid_amount_rub", "Выход за пределы допустимых значений amount_rub", DQDimension.VALIDITY, ('amount_rub',), CleanType.ZEROING)
    INVALID_CURRENCY = ("invalid_currency", "Некорректный формат значения currency", DQDimension.VALIDITY, ('currency',), CleanType.CORRECTION)
    INVALID_MERCHANT_CATEGORY = ("invalid_merchant_category", "Некорректный формат merchant_category",
                                 DQDimension.VALIDITY, ('merchant_category',), CleanType.CORRECTION)
    INVALID_CARD_LAST4 = ("invalid_card_last4", "Некорректный формат card_last4", DQDimension.VALIDITY, ('card_last4',), CleanType.CORRECTION)
    INVALID_DEVICE_TYPE = ("invalid_device_type", "Некорректный формат device_type", DQDimension.VALIDITY, ('device_type',), CleanType.CORRECTION)
    INVALID_GEO_COUNTRY = ("invalid_geo_country", "Некорректный формат geo_country",
                           DQDimension.VALIDITY, ('geo_country',), CleanType.ZEROING)
    INVALID_CHANNEL = ("invalid_channel", "Значение channel не входит в допустимые каналы",
                       DQDimension.VALIDITY, ('channel',), CleanType.ZEROING)
    # CONSISTENCY
    INCONSISTENCY_FLAGGED = ('inconsistency_flagged_field', "Несогласованны поля is_flagged и flagged_reason",
                             DQDimension.CONSISTENCY, ('is_flagged', 'flagged_reason'), CleanType.IGNORE)
    INCONSISTENCY_TRANSACTION = ('inconsistency_transaction_field',
                                 "При типе операции transaction заполнены поля, соответствующие типу session",
                                 DQDimension.CONSISTENCY, ('event_type', 'session_start_ts', 'session_end_ts', 'login_success', 'auth_method'), CleanType.CORRECTION)
                                 #Приводим к тому, что это транзакция
    INCONSISTENCY_SESSION = ('inconsistency_session_field',
                             "При типе операции session заполнены поля, соответствующие типу transaction",
                             DQDimension.CONSISTENCY, ('event_type', 'amount_rub', 'currency', 'merchant_category', 'merchant_country', 'card_last4'), CleanType.CORRECTION)
                             #Приводим к тому, что это сессия
    INCONSISTENCY_SESSION_TIMESTAMPS = ('inconsistency_session_timestamps',
                                        "session_end_ts раньше session_start_ts",
                                        DQDimension.CONSISTENCY, ('session_start_ts', 'session_end_ts'), CleanType.CORRECTION)
    # UNIQUENESS
    DUPLICATE_FULL = ('full_duplicate', 'Наличие дубликатов строк', DQDimension.UNIQUENESS, (ALL,), CleanType.DELETE)
    DUPLICATE_EVENT_ID = ('event_id_duplicate', 'Не уникальный event_id при различных операциях',
                          DQDimension.UNIQUENESS, ('event_id',), CleanType.IGNORE)

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
        return self.value[2].value
    
    @property
    def column(self) -> tuple:
        """В какой колонке найдено ("currency" / ALL)"""
        return self.value[3]

    @property
    def clean_type(self) -> CleanType:
        return self.value[4].value
#TODO сами типы определяются DQ