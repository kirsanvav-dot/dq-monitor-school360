"""
Очистка данных: применение правил к грязному датасету.

🔲 ЭТО МОДУЛЬ КОМАНДЫ BACKEND + DQ ANALYST.

В этом файле — контракт публичного API. Реализацию пишете сами.

Главный концепт: каждое правило очистки — отдельная операция.
Включается/выключается через CleaningConfig. Это нужно для UI:
пользователь страницы Cleaning сам решает, что чистить.

ВАЖНО: команда должна понимать разницу между УДАЛИТЬ и ВОССТАНОВИТЬ.
  - currency 'rub' → восстанавливаем в 'RUB' (это очевидная опечатка)
  - merchant_category '5411' → восстанавливаем в 'grocery' (ISO mapping)
  - client_id is NULL → удаляем строку (нет id = строка бесполезна)
  - amount_rub > 10_000_000 → удаляем (явно ошибка)
Это решение проектное, обсудите с DQ Analyst и обоснуйте на защите.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class CleaningConfig:
    """Настройки очистки. Каждый флаг — выкл/вкл одно правило.

    Команда расширяет этот список по мере реализации правил. Имена
    флагов используются на странице Cleaning как чекбоксы.
    """
    remove_duplicates: bool = True
    drop_missing_client_id: bool = True
    parse_dates_drop_invalid: bool = True
    fix_currency_typos: bool = True
    fix_mcc_iso_codes: bool = True
    fix_device_type_empty: bool = True
    drop_invalid_amounts: bool = True
    drop_invalid_ips: bool = False  # не критично для антифрод-правил
    fix_flag_inconsistency: bool = True
    fix_session_transaction_leak: bool = True


@dataclass
class CleaningStep:
    """Результат одного шага очистки. Лог для UI и для презентации."""
    name: str
    rows_before: int
    rows_after: int
    rows_modified: int = 0  # для шагов, которые не удаляют, а исправляют

    @property
    def rows_removed(self) -> int:
        return self.rows_before - self.rows_after


@dataclass
class CleaningLog:
    """Лог всего пайплайна очистки — для отображения в UI."""
    steps: list[CleaningStep] = field(default_factory=list)
    initial_rows: int = 0
    final_rows: int = 0

    def add(self, step: CleaningStep) -> None:
        self.steps.append(step)

    def to_dataframe(self) -> pd.DataFrame:
        if not self.steps:
            return pd.DataFrame(columns=[
                "name", "rows_before", "rows_after", "rows_removed", "rows_modified",
            ])
        return pd.DataFrame([
            {
                "name": s.name,
                "rows_before": s.rows_before,
                "rows_after": s.rows_after,
                "rows_removed": s.rows_removed,
                "rows_modified": s.rows_modified,
            } for s in self.steps
        ])


class DataCleaner:
    """Запускает все включённые шаги очистки последовательно.

    Контракт публичного API:
        cleaner = DataCleaner()
        cleaned_df, log = cleaner.clean(df, CleaningConfig())

    Возвращает кортеж (очищенный DataFrame, CleaningLog).
    """

    def clean(
        self,
        df: pd.DataFrame,
        config: CleaningConfig | None = None,
    ) -> tuple[pd.DataFrame, CleaningLog]:
        """Применить включённые в config правила и вернуть результат.

        Returns:
            (очищенный DataFrame, CleaningLog с записью по каждому шагу).
        """
        # TODO команде:
        #   1. Реализовать каждое правило как метод/функцию, принимающую df
        #      и возвращающую (cleaned_df, CleaningStep).
        #   2. В clean() — последовательно вызвать включённые в config правила,
        #      накопить шаги в CleaningLog.
        #   3. Порядок шагов важен: сначала удаляем мусор, потом восстанавливаем.
        #
        # Что должно быть реализовано минимум:
        #   - remove_duplicates: drop_duplicates()
        #   - drop_missing_client_id: учесть и NaN, и пустую строку
        #   - parse_dates_drop_invalid: pd.to_datetime(errors='coerce') + dropna
        #   - drop_invalid_amounts: NaN, < 0, > 10_000_000 (порог обсудите)
        #   - fix_currency_typos: маппинг 'rub'→'RUB', '$'→'USD' и т.д.
        #     Используйте справочник. Это шаг ВОССТАНОВЛЕНИЯ.
        #   - fix_mcc_iso_codes: обратный маппинг '5411'→'grocery'.
        #     ISO 4217 numeric → текстовая категория.
        #   - fix_device_type_empty: '' → NaN
        #   - fix_flag_inconsistency: решение командное — см. MENTOR_CHECKLIST
        #   - fix_session_transaction_leak: обнулить "чужие" поля по event_type
        raise NotImplementedError(
            "DataCleaner.clean не реализован. "
            "Реализуйте правила очистки и сборку пайплайна."
        )
