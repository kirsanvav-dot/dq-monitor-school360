"""
Антифрод-правила: rule-based детектор подозрительных транзакций.

🔲 ЭТОТ МОДУЛЬ ВАШ — ANTIFRAUD ENGINEER.

────────────────────────────────────────────────────────────────────
ЧТО МЫ ХОТИМ ПОЛУЧИТЬ

Класс или функция, которая принимает очищенный DataFrame, применяет
3 базовых антифрод-правила и возвращает:
  — тот же DataFrame с двумя новыми колонками:
      is_fraud_predicted (bool)  — итоговый вердикт (OR по всем правилам)
      triggered_rules (string)   — список сработавших правил через запятую
  — список результатов по каждому правилу (id, имя, сколько сработало)

Эти структуры нужны для:
  — отображения в UI (страница Antifraud Demo)
  — расчёта confusion matrix через src/metrics.py (она готова)

────────────────────────────────────────────────────────────────────
3 БАЗОВЫХ ПРАВИЛА (минимум для защиты)

R1 — Карусель
  Условие: >5 транзакций одного клиента за окно 10 минут
  Логика: серии мелких переводов с одной карты — признак тестирования
          или вывода через множество мелких операций
  Реализация (одна из возможных):
    1. Отфильтровать transaction-события с валидным client_id и event_ts
    2. Отсортировать по (client_id, event_ts)
    3. Внутри каждого client_id применить rolling-окно 10 мин по count
    4. Пометить все транзакции, попавшие в окно с count >= 6
  Подсказка:
    df.set_index('event_ts').groupby('client_id').rolling('10min')['event_id'].count()
  Аккуратно с возвратом индекса — потребуется reset_index.

R2 — Ночные крупные выводы
  Условие: event_type='transaction', час 01:00–04:00, amount_rub > 50_000
  Самое простое правило — фильтр по трём условиям.
  df['event_ts'] = pd.to_datetime(df['event_ts'], errors='coerce')
  df['event_ts'].dt.hour.between(1, 3)  # часы 1, 2, 3 = 01:00–03:59

R3 — Рисковые категории
  Условие: merchant_category in {'crypto_exchange', 'gambling',
                                  'wire_transfer_abroad'}
           И amount_rub > 50_000 (порог обсудите)
  Логика: после кражи деньги выводят туда, откуда их не вернуть —
          крипта, зарубежные счета, азартные игры.

────────────────────────────────────────────────────────────────────
БОНУСНЫЕ ПРАВИЛА (если останется время — стретч)

R4 — Невозможная геолокация
  Две транзакции одного клиента из разных стран за <30 минут.
  Усиление: формула Haversine для расстояния между городами.
  Если «требуемая скорость» > 1000 км/ч — точно фрод.

R5 — Серия неудачных логинов + крупная транзакция
  3+ session-события с login_success=False подряд от одного клиента,
  затем transaction > 50_000 ₽ от того же клиента в течение 15 минут.

────────────────────────────────────────────────────────────────────
АРХИТЕКТУРНЫЕ ПОДСКАЗКИ

  1. Каждое правило — отдельная функция/метод: (df) -> pd.Series[bool]
     длины len(df), где True означает «правило сработало для этой строки».

  2. Engine собирает результаты всех правил, считает OR, заполняет
     колонку triggered_rules именами сработавших правил.

  3. Для каждого правила храните: id ('R1_carousel'), имя ('Карусель'),
     описание, количество срабатываний, примеры event_id (для UI).

────────────────────────────────────────────────────────────────────
КАК ЭТО ИСПОЛЬЗУЕТСЯ В UI

    from src.antifraud_rules import RuleEngine
    engine = RuleEngine()
    df_predicted, rule_results = engine.run_all(df_cleaned)
    # df_predicted['is_fraud_predicted'] — итоговый вердикт
    # rule_results — список объектов с метриками по каждому правилу

Спроектируйте API так, чтобы получить именно такой вызов.
"""

from abc import ABC, abstractmethod
import pandas as pd


class BaseRule(ABC):
    rule_id: str
    name: str
    description: str
    triggered_count: int

    @abstractmethod
    def use_rule(self, df: pd.DataFrame) -> "pd.Series[bool]":
        """
        Применяет правило к таблице и возвращает маску — столбец булов,
        показывающий, какие строки удовлетворили правилу.

        Args:
            df: таблица для применения правила

        Returns:
            pd.Series[bool]: маска срабатывания правила
        """
        pass

    def return_examples(self, df: pd.DataFrame, mask: "pd.Series[bool]", n: int = 5) -> list[str]:
        """
        Возвращает список примеров event_id, для которых выполнено правило.

        Args:
            df: таблица данных
            mask: маска срабатывания правила
            n: сколько примеров вывести

        Returns:
            list[str]: список event_id
        """
        count = mask.sum()
        if count == 0:
            return []
        return df[mask].sample(min(n, count))["event_id"].to_list()


class NightWithdrawalRule(BaseRule):
    """
    Правило по опасным ночным транзакциям.
    Опасными считаются транзакции, совершённые во время 01:00:00–03:59:59
    и на сумму больше 50 000.
    """
    rule_id: str = "R2"
    name: str = "night withdrawal"
    description: str = "Detects large overnight transactions"
    triggered_count: int = 0

    def use_rule(self, df: pd.DataFrame) -> "pd.Series[bool]":
        column = pd.to_datetime(df['event_ts'], errors='coerce')
        is_night = column.dt.hour.between(1, 3)
        is_large_sum = df['amount_rub'] > 50000
        is_transaction = df['event_type'] == 'transaction'
        ans = is_night & is_large_sum & is_transaction
        self.triggered_count = ans.sum()
        return ans
