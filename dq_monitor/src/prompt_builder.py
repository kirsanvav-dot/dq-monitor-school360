import pandas as pd
from src.profiler import Report
import src.metrics as metrics

def base_legend():
    legend = """
Ты являешься частью приложения. Сейчас приведу описание проекта.
# 🔍 DQ Monitor — Карточка проекта

> Данные для антифрода: от грязных логов до доказанного эффекта на бизнес

---

## Заказчик и проблема

Молодой необанк, антифрод-команда. Боль:

- Антифрод-правила работают плохо, фрод проходит
- Команда подозревает, что данные в хранилище **грязные**: пропуски, опечатки, рассогласования
- Никто не измерял, насколько грязь данных влияет на качество детекции фрода
- Дата-инженеры не знают, **где именно** проблема и **что чинить в первую очередь**

## Ваша миссия

Построить **DQ Monitor** — приложение, которое:

1. Принимает CSV с банковскими событиями
2. Находит DQ-проблемы по 4 измерениям качества
3. Чистит данные настраиваемым пайплайном
4. Прогоняет rule-based антифрод-правила на грязной и чистой версии
5. **Доказывает на цифрах**, сколько фрода пропускается из-за плохих данных

И главное — **сформулировать дата-инженерам банка** конкретные рекомендации, что чинить.

КОНЕЦ описания приложения.

Твоя цель превратить статистики, которые приведутся далее, в конкретные
изменения, которые дата-инженеры банка могут внести в pipeline. Точных параметров пайплайна нет. Поэтому допущений делай как можно меньше.
Известно, что пайплайн работает либо в онлайн, либо с небольшой задержкой.

Хорошая рекомендация:
- называет **конкретную проблему** в данных
- предлагает **конкретное техническое решение**
- оценивает **бизнес-эффект**

Плохая рекомендация: «нужно улучшить качество данных». Это вода.

Структура одной рекомендации:
- **Проблема:** что не так в данных (конкретно)
- **Влияние:** как это бьёт по бизнесу (например, по детекции фрода)
- **Решение:** что технически сделать дата-инженерам
- **Приоритет:** High / Medium / Low

Условие закончилось, сейчас будут всякие статистики.
"""
    return legend

def confusion_matrix_to_str(matrix: metrics.ConfusionMatrix) -> str:
    res = ""
    res += f"True positive: {matrix.tp}\n"
    res += f"False positive: {matrix.fp}\n"
    res += f"True negative: {matrix.tn}\n"
    res += f"False negative: {matrix.fn}\n"
    res += f"Accuracy: {matrix.accuracy}\n"
    res += f"Precision: {matrix.precision}\n"
    res += f"Recall: {matrix.recall}\n"
    res += f"F1: {matrix.f1}\n"
    return res

def build_prompt(merged_dirty: pd.DataFrame, merged_clean: pd.DataFrame, issues: Report):
    result = base_legend()

    # give sample of dirty data
    dataformat = """

Таблицы чистых и грязных данных состоят из следующих колонок:
1. Изначальные колонки:
   1. event_id -- уникальный код операции
   2. client_id -- уникальный код клиента
   3. event_type -- тип операции. Возможно transaction -- перевод, а может быть session -- вход в аккаунт.
   4. event_ts -- event timestamp
   5. device_type -- устройство, с которого происходит операция
   6. ip_address
   7. geo_country -- в какой стране находится пользователь
   8. geo_city -- в каком городе пользователь
   9. channel -- через что происходит операция. web -- браузерное приложение, app -- приложение, branch -- операция производится в отделении банка.
   10. is_flagged пометка от анти-фрод системы банка
   11. flag_reason причина пометки от анти-фрод системы банка
   Следущие колонки только для записей event_type == transaction
   12. amount_rub -- колличество переводимых рублей (иногда долларов)
   13. currency. Допустимы только RUB и USD
   14. merchant_category. Строковое поле категории продавца (MCC)
   15. merchant_country -- страна продавца
   16. card_last4 -- четыре последних цифры карты
   Следущие колонки только для записей event_type == session
   17. session_start_ts -- начало сессии
   18. session_end_ts -- конец сессии
   19. login_success -- успешность входа в аккаунт
   20. auth_method -- способ входа
2. Колонки от rule-based антифрод-правил (4 пункт устройства приложения)
   1. is_fraud_predicted пометка от rule-based антифрод-правил
   2. triggered_rules Какое правило сработало. R1 -- пользователь сделал > 5 операций за 10 минут
R2 -- крупная транзакция в ночное время, R3 -- крупная транзакция в рискованной категории,
R4 -- чтобы совершить транзакцию пользователю нужно двигаться со скоростью >1000 км/ч. (отслеживается по event_ts и geo_city),
R5 -- много неудачных попыток входа (event_type==session, login_success==False) а затем крупная транзакция
3. Ground truth
   1. is_fraud_real -- ground truth пометки

"""
    result += dataformat

    result += """

Случайные 10 строк из таблицы до очистки

"""
    result += f"Всего в таблице {len(merged_dirty)} строк\n\n"
    result += merged_dirty.sample(10).to_string()

    # give sample of clean data
    result += """

Случайные 10 строк из таблицы после очистки

"""
    result += f"Всего в таблице {len(merged_clean)} строк\n\n"
    result += merged_clean.sample(10).to_string()
    # give data issues
    issuesDf = issues.to_dataframe().drop(["dimension", "issue_type", "column", "rows_affected"], axis=1)
    result += "\n\nСводка по проблемам датасета\n\n"
    result += issuesDf.to_string()
    # give rules metrics

    dirtyConfusionMatrix = metrics.compute_confusion_matrix(merged_dirty["is_fraud_predicted"], merged_dirty["is_fraud_real"])
    cleanConfusionMatrix = metrics.compute_confusion_matrix(merged_clean["is_fraud_predicted"], merged_clean["is_fraud_real"])

    result += "\n\nМетрики rulebased на грязных данных\n\n"
    result += confusion_matrix_to_str(dirtyConfusionMatrix)

    result += "\n\nМетрики rulebased на чистых данных\n\n"
    result += confusion_matrix_to_str(cleanConfusionMatrix)
    
    return result