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
import numpy as np

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
    
    @property
    def as_dict(self):
        return {'rule_id':self.rule_id, 'name':self.name, 'triggered_count':self.triggered_count}

class CarouselRule(BaseRule):
    """
    Карусель - если много операций (>5) от одного клиента
    за короткое время (<= 10 минут), то это фрод.
    """
    def __init__(self):
      self.rule_id: str = "R1"
      self.name: str = "Carousel"
      self.description: str = "Detects large counts of events"
      self.triggered_count: int = 0
    def use_rule(self, df: pd.DataFrame) -> "pd.Series[bool]":
      # Фильтруем: только транзакции с известным клиентом и валидной датой
      is_transaction = df['event_type'] == 'transaction'
      df['event_ts_dt'] = pd.to_datetime(df['event_ts'], errors='coerce')
      is_valid_time = df['event_ts_dt'].notna()
      filtred_df = df[
          df['client_id'].notna() & 
          is_valid_time & 
          is_transaction
      ].copy()
      # Сортируем по клиенту и времени (индексы НЕ сбрасываем – это важно!)
      filtred_df.sort_values(['client_id', 'event_ts_dt'], inplace=True)
      # Итоговая маска для исходного df
      mask = pd.Series(False, index=df.index)
      # Обрабатываем каждого клиента отдельно
      for _, group in filtred_df.groupby('client_id'):
          times = group['event_ts_dt'].values      # numpy array datetime64
          indices = group.index.values             # оригинальные индексы из df 
          start = 0
          for end in range(len(group)):
              # Двигаем левую границу окна, пока разница > 10 минут
              while (times[end] - times[start]) / np.timedelta64(1, 's') > 600:
                  start += 1
              # Проверяем окно, если в нём больше 5 элементов
              if end - start >= 5:
                  mask.loc[indices[start:end+1]] = True
      self.triggered_count = mask.sum()
      df.drop(columns=['event_ts_dt'], inplace=True)
      return mask

class NightWithdrawalRule(BaseRule):
    """
    Правило по опасным ночным транзакциям.
    Опасными считаются транзакции, совершённые во время 01:00:00–03:59:59
    и на сумму больше 50 000.
    """
    def __init__(self):
      self.rule_id: str = "R2"
      self.name: str = "night withdrawal"
      self.description: str = "Detects large overnight transactions"
      self.triggered_count: int = 0

    def use_rule(self, df: pd.DataFrame) -> "pd.Series[bool]":
        column = pd.to_datetime(df['event_ts'], errors='coerce')
        is_night = column.dt.hour.between(1, 3)
        is_LargeSum = df['amount_rub'] > 50000
        is_transaction = df['event_type'] == 'transaction'
        ans = is_night & is_LargeSum & is_transaction
        self.triggered_count = ans.sum()
        return ans

class RiscedCategoryRule(BaseRule):
    """
    Правило по опасным категориям.
    Опасными категориями считаются crypto_exchange, gambling, wire_transfer_abroad
    """
    def __init__(self):
      self.rule_id: str = "R3"
      self.name: str = "risced category"
      self.description: str = "Detects large risced category"
      self.triggered_count: int = 0
    
    def use_rule(self, df: pd.DataFrame) -> "pd.Series[bool]":
        is_RiscedCategory = df['merchant_category'].isin({'crypto_exchange', 'gambling', 'wire_transfer_abroad'})
        is_LargeSum = df['amount_rub'] > 50000
        ans = is_RiscedCategory & is_LargeSum
        self.triggered_count = ans.sum()
        return ans

class RuleEngine():
    """
    Основной класс - движок для правил.
    Выводит таблицу с дополнительным столбцами is_fraud_predicted и triggered_rules
    и выводит информацию о задейственных правилах.
    """
    def run_all(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list]:
        total_mask = pd.Series(False, index=df.index)
        triggered_rules = pd.Series('', index=df.index)
        rules_info = []
        for rule in [CarouselRule(), NightWithdrawalRule(), RiscedCategoryRule()]:
          mask_rule = rule.use_rule(df)
          rule_str = pd.Series(',', index=df.index).where(total_mask&mask_rule, '') + \
            pd.Series(rule.rule_id, index=df.index).where(mask_rule, '')
          total_mask |= mask_rule
          triggered_rules += rule_str
          rules_info.append(rule.as_dict)
        new_df = pd.concat([df, total_mask, triggered_rules], axis=1).rename(columns={0:'is_fraud_predicted', 1:'triggered_rules'})
        return (new_df, rules_info)

# экспериментирую, тестирую
# from data_loader import load_events
# df = load_events('dq_monitor/data/raw/events_dirty.csv')

# engine = RuleEngine()
# ans1,ans2 = engine.run_all(df)

# print("Часть итоговой таблицы:")
# print(ans1[ans1['is_fraud_predicted']].sample(25))
# print()
# print("Данные относительно каждого правила:")
# print(ans2)
# print()

# df = load_events('test_data_strange_timestamps.csv')
# rule1 = CarouselRule()
# mask = rule1.use_rule(df)
# print(mask)

