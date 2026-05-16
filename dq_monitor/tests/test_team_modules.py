"""Шаблон тестов для модулей команды.

🔲 ЭТО ШАБЛОН. По мере реализации src/profiler.py, src/cleaner.py,
src/antifraud_rules.py пишите сюда тесты.

Хороший тест:
  - использует фикстуру с ИЗВЕСТНЫМ ожидаемым результатом
  - проверяет ОДНУ конкретную вещь
  - имеет говорящее имя test_<что_проверяем>_<при_каких_условиях>

Примеры идей на тесты — см. ниже, все помечены @pytest.mark.skip.
Раскомментируйте и реализуйте по мере готовности модулей.

См. tests/test_data_loader.py и tests/test_metrics.py как образцы
рабочих тестов на готовые модули.
"""
import pandas as pd
import pytest

# from src.profiler import DataProfiler, DQReport
# from src.cleaner import DataCleaner, CleaningConfig
# from src.antifraud_rules import RuleEngine
# from src.dq_scorer import compute_dq_score


# ---------- Profiler ----------------------------------------------------

@pytest.mark.skip(reason="TODO: реализовать после DataProfiler.profile")
def test_profiler_finds_missing_client_id(small_dirty_df):
    """В small_dirty_df ровно 1 пропуск в client_id (см. conftest.py).

    Profiler должен вернуть issue с column='client_id', rows_affected=1.
    """
    # report = DataProfiler().profile(small_dirty_df)
    # client_issues = [i for i in report.issues if i.column == "client_id"]
    # assert len(client_issues) == 1
    # assert client_issues[0].rows_affected == 1
    pass


@pytest.mark.skip(reason="TODO: реализовать после DataProfiler.profile")
def test_profiler_finds_invalid_ip(small_dirty_df):
    """В small_dirty_df ровно 1 битый IP."""
    pass


@pytest.mark.skip(reason="TODO: реализовать после DataProfiler.profile")
def test_profiler_finds_currency_typo(small_dirty_df):
    """В small_dirty_df ровно 1 опечатка 'rub' в currency."""
    pass


# ---------- Cleaner -----------------------------------------------------

@pytest.mark.skip(reason="TODO: реализовать после DataCleaner.clean")
def test_cleaner_removes_duplicates(small_dirty_df):
    """1 дубликат в small_dirty_df должен быть удалён."""
    # cleaned, log = DataCleaner().clean(small_dirty_df, CleaningConfig())
    # assert len(cleaned) == len(small_dirty_df) - 1
    pass


@pytest.mark.skip(reason="TODO: реализовать после DataCleaner.clean")
def test_cleaner_fixes_currency_typo(small_dirty_df):
    """После очистки 'rub' должно стать 'RUB'."""
    # cleaned, _ = DataCleaner().clean(small_dirty_df, CleaningConfig())
    # assert "rub" not in cleaned["currency"].dropna().unique()
    pass


# ---------- RuleEngine --------------------------------------------------

@pytest.mark.skip(reason="TODO: реализовать после RuleEngine.run_all")
def test_rule_night_withdrawal_detects_synthetic_case():
    """Подкладываем явный ночной крупный вывод — правило R2 должно сработать."""
    pass


# ---------- DQ Scorer ---------------------------------------------------

@pytest.mark.skip(reason="TODO: реализовать после compute_dq_score")
def test_dq_score_perfect_data_returns_1():
    """На датасете без проблем score должен быть 1.0 по всем измерениям."""
    pass


@pytest.mark.skip(reason="TODO: реализовать после compute_dq_score")
def test_dq_score_in_range():
    """Score должен быть в диапазоне [0, 1] на любом датасете."""
    pass
