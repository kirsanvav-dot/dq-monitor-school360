"""
Антифрод-правила: rule-based детектор подозрительных транзакций.

🔲 ЭТО МОДУЛЬ КОМАНДЫ ANTIFRAUD ENGINEER.

В этом файле — контракт публичного API. Реализацию пишете сами.

Архитектурный принцип: каждое правило — отдельная функция/метод,
возвращающая pd.Series[bool] длины len(df). True = правило сработало.
RuleEngine собирает все правила и формирует общий вердикт.

Базовых правил из ТЗ — 3. Бонусных — 2. Минимум для проекта — 3 правила,
но бонусные дают команде сильный материал для защиты.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class RuleResult:
    """Результат работы одного правила. Используется в UI и для метрик.

    Attributes:
        rule_id: короткий машиночитаемый id, например 'R1_carousel'.
        rule_name: человеко-читаемое имя для UI.
        description: описание сути правила.
        triggered_count: сколько строк правило отметило как фрод.
        triggered_event_ids: до 100 примеров id для UI (опционально).
    """
    rule_id: str
    rule_name: str
    description: str
    triggered_count: int
    triggered_event_ids: list[str] = field(default_factory=list)


class RuleEngine:
    """Запускает все правила и формирует итоговое предсказание.

    Контракт публичного API:
        engine = RuleEngine()
        df_predicted, rule_results = engine.run_all(df_cleaned)

    Где df_predicted содержит как минимум:
      - оригинальные колонки df_cleaned
      - is_fraud_predicted: bool — итоговый вердикт (OR по всем правилам)
      - triggered_rules: string — список сработавших правил через запятую

    А rule_results — list[RuleResult], по одному на правило.
    """

    def run_all(
        self,
        df: pd.DataFrame,
    ) -> tuple[pd.DataFrame, list[RuleResult]]:
        """Применить все правила и собрать единый вердикт.

        Returns:
            (df с добавленными колонками is_fraud_predicted и triggered_rules,
             список RuleResult по каждому правилу).
        """
        # TODO команде:
        #   1. Реализовать минимум 3 базовых правила из ТЗ:
        #      R1 (карусель), R2 (ночные крупные выводы), R3 (рисковые категории).
        #   2. Каждое правило — функция: (df) -> pd.Series[bool] длины len(df).
        #   3. В run_all() — применить все правила, собрать общий вердикт OR,
        #      записать какие правила сработали для каждой строки.
        #   4. Бонусные правила (если время остаётся):
        #      R4: невозможная геолокация (Haversine или просто разные страны
        #          за короткое окно).
        #      R5: серия неудачных логинов + крупная транзакция в 15 минут.
        #
        # Технические подсказки:
        #   - Распарсите event_ts перед использованием в правилах:
        #       df["event_ts"] = pd.to_datetime(df["event_ts"], errors="coerce")
        #   - Для R1 (карусель) посмотрите groupby + rolling по времени:
        #       df.set_index('event_ts').groupby('client_id')
        #         .rolling('10min')['event_id'].count()
        #     Будьте аккуратны с возвратом индекса.
        #   - Для R2 — фильтр по df["event_ts"].dt.hour и amount_rub.
        #   - Для R3 — isin(["crypto_exchange", "gambling", "wire_transfer_abroad"])
        #     + порог по сумме.
        raise NotImplementedError(
            "RuleEngine.run_all не реализован. "
            "Реализуйте минимум 3 базовых правила и сборку вердикта."
        )
