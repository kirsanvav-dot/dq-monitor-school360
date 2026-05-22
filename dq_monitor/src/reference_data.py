"""
Справочные данные для очистки. Часть значений здесь уже готова,
часть — оставлена пустой намеренно: это решения, которые команда
должна принять и обосновать сама.

────────────────────────────────────────────────────────────────────
ЧТО ЗДЕСЬ ЛЕЖИТ

  MCC_ISO_TO_TEXT       ✅ готовый справочник ISO 4217 → текстовая
                           категория мерчанта.
                           Это объективное знание (международный стандарт),
                           не требует от вас «изобретения» — просто берите
                           и используйте.

  VALID_DEVICE_TYPES    ✅ список валидных значений device_type.

  CURRENCY_MAPPING      🔲 ПУСТО — заполняете сами.
                           Вам предстоит изучить, какие нестандартные
                           значения встречаются в колонке currency, и
                           решить, как с каждым поступать.

────────────────────────────────────────────────────────────────────
КАК ИСПОЛЬЗОВАТЬ В cleaner.py

    from src.reference_data import MCC_ISO_TO_TEXT, CURRENCY_MAPPING

    # Пример для merchant_category:
    df["merchant_category"] = df["merchant_category"].replace(MCC_ISO_TO_TEXT)

    # Пример для currency (после того, как вы заполните CURRENCY_MAPPING):
    df["currency"] = df["currency"].replace(CURRENCY_MAPPING)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Any

#   data/geoip/GeoLite2-City.mmdb
GEOIP_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "geoip" / "GeoLite2-City.mmdb"


def open_geoip_reader() -> Optional[Any]:
    """Открывает GeoLite2-City, если файл БД есть. Иначе None (только lookup по витрине)."""
    if not GEOIP_DB_PATH.is_file():
        return None
    try:
        import geoip2.database
        return geoip2.database.Reader(str(GEOIP_DB_PATH))
    except Exception:
        return None


def city_from_geoip(reader: Any, ip: str) -> Optional[str]:
    """Город по IP через MaxMind GeoLite2 (англоязычные названия)."""
    if reader is None:
        return None
    try:
        response = reader.city(ip)
        name = response.city.name
        return name if name else None
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════
# ✅ MCC — Merchant Category Codes (ISO 18245 / стандарт платёжных систем)
# ════════════════════════════════════════════════════════════════════
#
# Готовый справочник. В нашем датасете в одном месяце (см. сами,
# в каком — это часть DQ-проблем) категории мерчантов приходят как
# 4-значные ISO-коды вместо человеко-читаемого текста.
#
# Это известная проблема в банковских данных: legacy-системы хранят MCC
# как числовые коды, а новые витрины ожидают строковые имена.
# Решение — обратный маппинг.

MCC_ISO_TO_TEXT: dict[str, str] = {
    # Повседневные траты
    "5411": "grocery",
    "5812": "restaurant",
    "5541": "gas_station",
    "4111": "transport",

    # Покупки
    "5732": "electronics",
    "5651": "clothing",
    "5969": "online_shopping",

    # Услуги
    "7832": "entertainment",
    "8011": "healthcare",
    "8220": "education",
    "4900": "utilities",

    # Финансовые операции
    "6011": "atm_withdrawal",

    # Рисковые категории (используются в антифрод-правиле R3)
    "6051": "crypto_exchange",
    "7995": "gambling",
    "4829": "wire_transfer_abroad",
}

# Список всех валидных текстовых категорий — пригодится для check_validity
# в profiler.py: всё, что не входит в этот список И не входит в ключи
# MCC_ISO_TO_TEXT — невалидная категория.
VALID_MERCHANT_CATEGORIES: set[str] = set(MCC_ISO_TO_TEXT.values())


# ════════════════════════════════════════════════════════════════════
# ✅ Device Type — валидные значения
# ════════════════════════════════════════════════════════════════════
#
# На бэкенде есть три валидных типа устройства. Всё остальное (NaN,
# пустая строка, что-то другое) — DQ-проблема. Пустую строку нужно
# привести к NaN; команда решает, что делать с другими аномалиями.

VALID_DEVICE_TYPES: set[str] = {"mobile", "desktop", "atm"}


# ════════════════════════════════════════════════════════════════════
# 🔲 Currency — ВАШ СПРАВОЧНИК
# ════════════════════════════════════════════════════════════════════
#
# Здесь намеренно пусто. Это не «недоделанный код», это часть работы
# DQ-аналитика — построить маппинг самостоятельно. Почему так:
#
#   1. На защите вас спросят: «почему вы 'USDD' трактуете как 'USD', а
#      не как ошибку?» Если вы скопировали готовый словарь — вы не
#      сможете ответить. Если вы построили его сами — у вас есть
#      аргумент по каждой записи.
#
#   2. В реальной работе банковского аналитика никто не даёт «вот
#      справочник, чисти по нему». Аналитик сам смотрит данные, сам
#      решает, что является опечаткой, а что — реальной аномалией.
#
# ────────────────────────────────────────────────────────────────────
# КАК ПОСТРОИТЬ
#
# Шаг 1. Посмотрите все встречающиеся значения:
#
#     df["currency"].value_counts(dropna=False).head(20)
#
# Вы увидите топ значений с количеством. Большинство будет 'RUB' —
# это норма. Остальное — аномалии разных видов.
#
# Шаг 2. Для каждого аномального значения задайте себе три вопроса:
#
#   а) Это явная опечатка с очевидным восстановлением?
#      Пример: 'rub' → 'RUB' (просто другой регистр).
#
#   б) Это валидный код в другом стандарте?
#      Пример: '810' — это ISO 4217 numeric для российского рубля.
#      Решите: восстанавливаете в 'RUB' (доверяете) или удаляете
#      строку (не наш формат)? Зафиксируйте позицию.
#
#   в) Это значение, которое нельзя восстановить однозначно?
#      Пример: '$' — это USD? CAD? AUD? Если у вас банк российский
#      и 99% операций в RUB, разумно считать $ как USD, но это
#      решение, не факт.
#
# Шаг 3. Заполните CURRENCY_MAPPING ниже. Пишите комментарий к каждой
# записи, почему вы так решили — это пригодится для защиты.
#
# Шаг 4. Что делать с теми значениями, которые вы не смогли уверенно
# восстановить? Варианты:
#    — оставить как есть и пометить severity=high в DQ-отчёте
#    — заменить на NaN и удалить строку в cleaner'е
#    — заменить на 'UNKNOWN' и продолжить работу
# Это тоже командное решение. В реальном банке выбрали бы 1 или 3
# (терять данные дорого), но для учебного проекта любой обоснованный
# вариант ок.
#
# ────────────────────────────────────────────────────────────────────
# ЗАПОЛНИТЕ:

CURRENCY_MAPPING: dict[str, str] = {
    "rub": "RUB",  # опечатка, нижний регистр
    "RUR": "RUB",  # устаревший код, был в России до 1998
    "810": "RUB",
    # код для русского рубля, в наших данных использовался для переводов внутри страны, кроме 0.000% операций, дописать после очистки данных
    "$": "USD",
    # так как по анализу направлений операций, транзакции осуществлялись между странами, использующими $ как обозначение для USD
    "USDD": "USD"  # опечатка
}

# После того как заполните CURRENCY_MAPPING, не забудьте обсудить:
#
# 1. Что считаем валидным итогом? Скорее всего, набор из {RUB, USD, EUR}
#    — но обоснуйте, что других валют в банке быть не может.
#
# 2. Что делать с пустой строкой '' в currency? Это NaN или просто
#    отсутствие значения? На бэкенде это разные сущности.

VALID_CURRENCIES: set[str] = {"RUB", "USD", "EUR"}


# ════════════════════════════════════════════════════════════════════
# ✅ Event Type — допустимые типы событий
# ════════════════════════════════════════════════════════════════════
VALID_EVENT_TYPES: set[str] = {"transaction", "session"}


# ════════════════════════════════════════════════════════════════════
# ✅ Channel — допустимые каналы взаимодействия
# ════════════════════════════════════════════════════════════════════
#
# Четыре канала, зафиксированных в бэкенде:
#   app    — мобильное приложение
#   web    — веб-интерфейс (браузер)
#   atm    — банкомат
#   branch — отделение банка
VALID_CHANNELS: set[str] = {"app", "web", "atm", "branch"}


# ════════════════════════════════════════════════════════════════════
# ✅ Geo Country — допустимый формат кода страны (ISO 3166-1 alpha-2)
# ════════════════════════════════════════════════════════════════════
#
# Валидируем по паттерну: ровно 2 заглавные буквы латиницы (RU, US, DE …).
# Использовать regex в profiler.py: r'^[A-Z]{2}$'
# Справочник ISO 3166-1 alpha-2 не вносим целиком — проверяем только формат,
# поскольку полный список стран (249 кодов) меняется редко и в датасете нет
# экзотических значений, требующих перечисления.
GEO_COUNTRY_PATTERN = (
    'Afghanistan',
    'Albania',
    'Algeria',
    'Andorra',
    'Angola',
    'Antigua and Barbuda',
    'Argentina',
    'Armenia',
    'Australia',
    'Austria',
    'Azerbaijan',
    'Bahamas',
    'Bahrain',
    'Bangladesh',
    'Barbados',
    'Belarus',
    'Belgium',
    'Belize',
    'Benin',
    'Bhutan',
    'Bolivia',
    'Bosnia and Herzegovina',
    'Botswana',
    'Brazil',
    'Brunei',
    'Bulgaria',
    'Burkina Faso',
    'Burundi',
    'Cabo Verde',
    'Cambodia',
    'Cameroon',
    'Canada',
    'Central African Republic',
    'Chad',
    'Chile',
    'China',
    'Colombia',
    'Comoros',
    'Congo',
    'Costa Rica',
    'Cote d\'Ivoire',
    'Croatia',
    'Cuba',
    'Cyprus',
    'Czech Republic',
    'Denmark',
    'Djibouti',
    'Dominica',
    'Dominican Republic',
    'Ecuador',
    'Egypt',
    'El Salvador',
    'Equatorial Guinea',
    'Eritrea',
    'Estonia',
    'Eswatini',
    'Ethiopia',
    'Fiji',
    'Finland',
    'France',
    'Gabon',
    'Gambia',
    'Georgia',
    'Germany',
    'Ghana',
    'Greece',
    'Grenada',
    'Guatemala',
    'Guinea',
    'Guinea-Bissau',
    'Guyana',
    'Haiti',
    'Honduras',
    'Hungary',
    'Iceland',
    'India',
    'Indonesia',
    'Iran',
    'Iraq',
    'Ireland',
    'Israel',
    'Italy',
    'Jamaica',
    'Japan',
    'Jordan',
    'Kazakhstan',
    'Kenya',
    'Kiribati',
    'Korea, North',
    'Korea, South',
    'Kosovo',
    'Kuwait',
    'Kyrgyzstan',
    'Laos',
    'Latvia',
    'Lebanon',
    'Lesotho',
    'Liberia',
    'Libya',
    'Liechtenstein',
    'Lithuania',
    'Luxembourg',
    'Madagascar',
    'Malawi',
    'Malaysia',
    'Maldives',
    'Mali',
    'Malta',
    'Marshall Islands',
    'Mauritania',
    'Mauritius',
    'Mexico',
    'Micronesia',
    'Moldova',
    'Monaco',
    'Mongolia',
    'Montenegro',
    'Morocco',
    'Mozambique',
    'Myanmar',
    'Namibia',
    'Nauru',
    'Nepal',
    'Netherlands',
    'New Zealand',
    'Nicaragua',
    'Niger',
    'Nigeria',
    'North Macedonia',
    'Norway',
    'Oman',
    'Pakistan',
    'Palau',
    'Palestine',
    'Panama',
    'Papua New Guinea',
    'Paraguay',
    'Peru',
    'Philippines',
    'Poland',
    'Portugal',
    'Qatar',
    'Romania',
    'Russia',
    'Rwanda',
    'Saint Kitts and Nevis',
    'Saint Lucia',
    'Saint Vincent and the Grenadines',
    'Samoa',
    'San Marino',
    'Sao Tome and Principe',
    'Saudi Arabia',
    'Senegal',
    'Serbia',
    'Seychelles',
    'Sierra Leone',
    'Singapore',
    'Slovakia',
    'Slovenia',
    'Solomon Islands',
    'Somalia',
    'South Africa',
    'South Sudan',
    'Spain',
    'Sri Lanka',
    'Sudan',
    'Suriname',
    'Sweden',
    'Switzerland',
    'Syria',
    'Taiwan',
    'Tajikistan',
    'Tanzania',
    'Thailand',
    'Timor-Leste',
    'Togo',
    'Tonga',
    'Trinidad and Tobago',
    'Tunisia',
    'Turkey',
    'Turkmenistan',
    'Tuvalu',
    'Uganda',
    'Ukraine',
    'UAE',
    'United Kingdom',
    'United States',
    'Uruguay',
    'Uzbekistan',
    'Vanuatu',
    'Vatican City',
    'Venezuela',
    'Vietnam',
    'Yemen',
    'Zambia',
    'Zimbabwe'
)
