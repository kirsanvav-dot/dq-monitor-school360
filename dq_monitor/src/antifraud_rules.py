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
from math import radians, sin, cos, sqrt, asin


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
    R1: Правило по частым транзакциям.
    Если пользователь совершил >= 6 транзакция за <= 10 минут,
    то блокируются все транзакции, попавшие в 10-минутное окно.
    """
    def __init__(self):
      self.rule_id: str = "R1"
      self.name: str = "Carousel"
      self.description: str = "Detects large counts of events"
      self.triggered_count: int = 0

    def use_rule(self, df: pd.DataFrame) -> "pd.Series[bool]":
      is_transaction = df['event_type'] == 'transaction'
      df['event_ts_dt'] = pd.to_datetime(df['event_ts'], errors='coerce')
      is_valid_time = df['event_ts_dt'].notna()
      filtred_df = df[
          df['client_id'].notna() & 
          is_valid_time & 
          is_transaction
      ].copy()
      filtred_df.sort_values(['client_id', 'event_ts_dt'], inplace=True)
      mask = pd.Series(False, index=df.index)
      for client_id, group in filtred_df.groupby('client_id'):
          times = group['event_ts_dt'].values
          countries = group['geo_country'].values
          indices = group.index.values
          start = 0
          for end in range(len(group)):
              while (times[end] - times[start]) / np.timedelta64(1, 's') > 600:
                  start += 1
              if end - start >= 5:
                  mask.loc[indices[start:end+1]] = True
      self.triggered_count = mask.sum()
      df.drop(columns=['event_ts_dt'], inplace=True)
      return mask

class NightWithdrawalRule(BaseRule):
    """
    R2: Правило по опасным ночным транзакциям.
    Опасными считаются транзакции, совершённые во время 01:00:00–03:59:59
    и на сумму больше 50 000.
    """
    def __init__(self):
      self.rule_id: str = "R2"
      self.name: str = "Night withdrawal"
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
    R3: Правило по опасным категориям.
    Опасными категориями считаются crypto_exchange, gambling, wire_transfer_abroad
    """
    def __init__(self):
      self.rule_id: str = "R3"
      self.name: str = "Risced category"
      self.description: str = "Detects large risced category"
      self.triggered_count: int = 0
    
    def use_rule(self, df: pd.DataFrame) -> "pd.Series[bool]":
        is_RiscedCategory = df['merchant_category'].isin({'crypto_exchange', 'gambling', 'wire_transfer_abroad'})
        is_LargeSum = df['amount_rub'] > 50000
        ans = is_RiscedCategory & is_LargeSum
        self.triggered_count = ans.sum()
        return ans

class ImpossibleGeoRule(BaseRule):
    """
    R4: Правило по транзакциям с невозможной геолокацией.
    Помечаются фродом все транзакции от пользователя, попавшие в 30-минутное окно,
    если выполнилось одно из условий:
    1) Транзакции были произведены из разных стран
    2) (Усиление Haversine) Требуемая скорость > 1000 км/ч
    TODO
    1) Помечать фродом только вторую транзакцию - из нестандартной геолокации
    2) Искать пары транзакций с разными городами (и любым временем)
    с "требуемой скоростью" > 1000 км/ч и помечать только вторую
    """
    cities_coords = { # координаты городов
    'Moscow': (55.7558, 37.6173),
    'Novosibirsk': (55.0188, 82.9335),
    'Yekaterinburg': (56.8389, 60.6057),
    'Krasnodar': (45.0355, 38.9753),
    'Saint Petersburg': (59.9343, 30.3351),
    'Samara': (53.1959, 50.1002),
    'Kazan': (55.7961, 49.1064),
    'Sochi': (43.5855, 39.7231),
    'Nizhny Novgorod': (56.2965, 43.9361),
    'Ufa': (54.7348, 55.9578),
    'Yerevan': (40.1792, 44.4991),
    'Astana': (51.1694, 71.4491),
    'Limassol': (34.6786, 33.0413),
    'Istanbul': (41.0082, 28.9784),
    'Dubai': (25.2048, 55.2708),
    'Tbilisi': (41.7151, 44.8271)
    }

    def __init__(self):
      self.rule_id: str = "R4"
      self.name: str = "Impossible geolocations"
      self.description: str = "Detects transactions with impossible geolocation"
      self.triggered_count: int = 0

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
      """Расстояние в км между двумя точками"""
      R = 6371  # радиус Земли в км
      lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
      dlat = lat2 - lat1
      dlon = lon2 - lon1
      a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
      c = 2 * asin(sqrt(a))
      return R * c

    def calculate_speed(self, item1: pd.Series, item2: pd.Series):
      """Вычисляет скорость между двумя городами"""
      city1 = item1['geo_city']
      city2 = item2['geo_city']
      coord1 = self.cities_coords[city1]
      coord2 = self.cities_coords[city2]
      distance = self.haversine(coord1[0], coord1[1], coord2[0], coord2[1])
      delta_time = abs(item1['event_ts_dt'] - item2['event_ts_dt'])
      delta_time = delta_time / np.timedelta64(1, 'h')
      if delta_time < 0.001:
          if city1 != city2:
              return float('INF')
          else:
              return 0
      return distance / delta_time

    def is_strange_speed(self, window):
      """Проверяет аномальную скорость в окне"""
      window = window[window['geo_city'].notna()]
      if any([
          (self.calculate_speed(window.iloc[i], window.iloc[i+1]) > 1000)
          for i in range(len(window)-1)
          ]):
          return True

    def use_rule(self, df):
        is_transaction = df['event_type'] == 'transaction'
        df['event_ts_dt'] = pd.to_datetime(df['event_ts'], errors='coerce')
        is_valid_time = df['event_ts_dt'].notna()
        filtred_df = df[
            df['client_id'].notna() &
            df['geo_country'].notna() &
            is_valid_time &
            is_transaction
        ].copy()
        filtred_df.sort_values(['client_id', 'event_ts_dt'], inplace=True)
        mask = pd.Series(False, index=df.index)
        for _, group in filtred_df.groupby('client_id'):
            times = group['event_ts_dt'].values
            countries = group['geo_country'].values
            indices = group.index.values
            start = 0
            for end in range(len(group)):
                while (times[end] - times[start]) / np.timedelta64(1, 's') > 1800:
                    start += 1
                if end > start:
                    window_countries = countries[start:end+1]
                    if len(np.unique(window_countries)) > 1:
                        mask.loc[indices[start:end+1]] = True
                    else:
                        if self.is_strange_speed(group.iloc[start:end+1]):
                            mask.loc[indices[start:end+1]] = True
        df['is_fraud_R4'] = mask
        df.drop(columns=['event_ts_dt'], inplace=True)
        self.triggered_count = mask.sum()
        return mask
    
    def test_haversine(self, df):
        real_fraud = pd.read_csv('dq_monitor/data/ground_truth/fraud_labels.csv')
        count_TP = 0; count_hv = 0
        is_transaction = df['event_type'] == 'transaction'
        df['event_ts_dt'] = pd.to_datetime(df['event_ts'], errors='coerce')
        is_valid_time = df['event_ts_dt'].notna()
        filtred_df = df[
            df['client_id'].notna() &
            df['geo_country'].notna() &
            is_valid_time &
            is_transaction
        ].copy()
        filtred_df.sort_values(['client_id', 'event_ts_dt'], inplace=True)
        mask = pd.Series(False, index=df.index)
        for _, group in filtred_df.groupby('client_id'):
            times = group['event_ts_dt'].values
            countries = group['geo_country'].values
            indices = group.index.values
            start = 0
            for end in range(len(group)):
                while (times[end] - times[start]) / np.timedelta64(1, 's') > 1800:
                    start += 1
                if end > start:
                    window_countries = countries[start:end+1]
                    if len(np.unique(window_countries)) > 1:
                        mask.loc[indices[start:end+1]] = True
                    else:
                        if self.is_strange_speed(group.iloc[start:end+1]):
                            mask.loc[indices[start:end+1]] = True
                            part_group = group.iloc[start:end+1]
                            print(part_group[['event_id', 'client_id', 'event_ts', 'geo_city']])
                            part_real_fraud = real_fraud[ real_fraud['event_id'].isin(part_group['event_id']) ]
                            print(real_fraud[ real_fraud['event_id'].isin(part_group['event_id']) ])
                            count_TP += (part_real_fraud['is_fraud_real'] == True).sum()
                            count_hv += len(part_group)
        df['is_fraud_R4'] = mask
        df.drop(columns=['event_ts_dt'], inplace=True)
        self.triggered_count = mask.sum()
        print()
        print(f"Количество True Positive в усилении Haversine: {count_TP}")
        print(f"Всего найдено фрода в усилении Haversine: {count_hv}")

class BruteForceTransactionRule(BaseRule):
    """
    R5: Правило по большому числу безуспешных сессий с большой транзакцией.
    Если один пользователь в течение 15 минут 3 раза неудачно авторизировался
    и сделал транзакцию на сумму >50'000, то помечаем фродом и сессии, и транзакции.
    """
    def __init__(self):
      self.rule_id: str = "R5"
      self.name: str = "Brute force transaction "
      self.description: str = "Detects brute force transactions"
      self.triggered_count: int = 0
    
    def use_rule(self, df):
        df['event_ts_dt'] = pd.to_datetime(df['event_ts'], errors='coerce')
        is_valid_time = df['event_ts_dt'].notna()
        filtred_df = df[
            df['client_id'].notna() & 
            is_valid_time
        ].copy()
        filtred_df.sort_values(['client_id', 'event_ts_dt'], inplace=True)
        mask = pd.Series(False, index=df.index)
        for client_id, group in filtred_df.groupby('client_id'):
            event_types = group['event_type'].values
            login_success = group['login_success'].values
            amounts = group['amount_rub'].values
            times = group['event_ts_dt'].values
            indices = group.index.values
            count_false_login = 0
            false_login_positions = []
            start = 0
            for end in range(len(group)):
                if event_types[end] == "session" and not login_success[end]:
                    count_false_login += 1
                    false_login_positions.append(end)
                while (times[end] - times[start]) / np.timedelta64(1, 's') > 900:
                    if event_types[start] == "session" and not login_success[start]:
                        count_false_login -= 1
                        false_login_positions.pop(0)
                    start += 1
                # проверяем на выполнимость BruteForceTransactionRule
                if count_false_login >= 3:
                    if event_types[end] == 'transaction' and amounts[end] > 50000:
                        mask.loc[indices[end]] = True
                        mask.loc[indices[false_login_positions]] = True
        df.drop(columns=['event_ts_dt'], inplace=True)
        self.triggered_count = mask.sum()
        return mask

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
        for rule in [CarouselRule(), NightWithdrawalRule(), RiscedCategoryRule(), ImpossibleGeoRule(), BruteForceTransactionRule()]:
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

# rule4 = ImpossibleGeoRule()
# rule4.test_haversine(df)
# print(rule4.return_examples(df, mask, 10))
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

