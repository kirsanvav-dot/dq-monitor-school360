import pytest
import pandas as pd
from src.dq_scorer import (
    compute_dq_score, 
    get_unique_affected_rows, 
    calculate_dimension_score, 
    calculate_uniqueness_score,
    ISSUE_COMPLETENESS,
    ISSUE_UNIQUENESS
)
from src.profiler import Report, DQIssue
from src.constant_issue import IssueType
@pytest.fixture
def sample_df():
    # Мокаем простой датафрейм. Строки 3, 4, 5 — полные дубликаты.
    data = {
        'event_id': ['evt_1', 'evt_2', 'evt_3', 'evt_4', 'evt_4', 'evt_4'],
        'amount_rub': [100, 200, 300, 400, 400, 400]
    }
    return pd.DataFrame(data)

def test_get_unique_affected_rows():
    """Тест проверяет, что строки склеиваются в уникальное множество (set) без дублей"""
    issues = [
        DQIssue(issue_type=IssueType.EMPTY_EVENT_ID, affected_indices=pd.Index([0, 1])),
        DQIssue(issue_type=IssueType.EMPTY_CLIENT_ID, affected_indices=pd.Index([1, 2])),
        # Это другая категория, она не должна попасть в выборку, если мы фильтруем по COMPLETENESS
        DQIssue(issue_type=IssueType.INVALID_FORMAT_DATE, affected_indices=pd.Index([3]))
    ]
    
    unique_rows = get_unique_affected_rows(issues, ISSUE_COMPLETENESS)
    
    # Ожидаем, что уникальные индексы это 0, 1, 2 (строка 1 была в обоих issue, но учлась один раз)
    assert set(unique_rows) == {0, 1, 2}

def test_calculate_dimension_score():
    """Тест расчёта скора для обычного измерения"""
    issues = [
        DQIssue(issue_type=IssueType.EMPTY_EVENT_ID, affected_indices=pd.Index([0, 1])),
        DQIssue(issue_type=IssueType.EMPTY_CLIENT_ID, affected_indices=pd.Index([1, 2]))
    ]
    
    # Всего строк 10. Затронуты 0, 1, 2 (3 уникальные строки).
    # Скор = 1 - (3 / 10) = 0.7
    score, affected = calculate_dimension_score(10, issues, ISSUE_COMPLETENESS)
    
    # Используем pytest.approx для сравнения float
    assert score == pytest.approx(0.7)
    assert set(affected) == {0, 1, 2}

def test_calculate_uniqueness_score(sample_df):
    """Тест расчёта скора для уникальности с вычетом оригинальных строк (дубликаты влияют как n-1)"""
    issues = [
        DQIssue(issue_type=IssueType.DUPLICATE_FULL, affected_indices=pd.Index([3, 4, 5]))
    ]
    
    # Всего строк 6. Из 3 строк дубликатов (3,4,5) уникальная комбинация 1. 
    # Лишних строк (excess_count) = 3 - 1 = 2
    # Скор = 1 - (2 / 6) = 0.66666...
    score, duplicate_indices = calculate_uniqueness_score(6, issues, ISSUE_UNIQUENESS, sample_df)
    
    # Используем pytest.approx для сравнения float
    assert score == pytest.approx(1 - (2 / 6))
    assert set(duplicate_indices) == {3, 4, 5}

def test_compute_dq_score(sample_df):
    """Интеграционный тест подсчёта всех баллов"""
    issues = [
        # Completeness: затронуты 0, 1 (2 строки)
        DQIssue(issue_type=IssueType.EMPTY_EVENT_ID, affected_indices=pd.Index([0, 1])),
        # Validity: затронуты 1, 2 (2 строки)
        DQIssue(issue_type=IssueType.INVALID_FORMAT_DATE, affected_indices=pd.Index([1, 2])),
        # Uniqueness: затронуты 3, 4, 5 (3 строки, из них 2 лишние)
        DQIssue(issue_type=IssueType.DUPLICATE_FULL, affected_indices=pd.Index([3, 4, 5]))
    ]
    
    report = Report(total_rows=6, issues=issues)
    score = compute_dq_score(sample_df, report)
    
    # Сравнения через pytest.approx:
    # Completeness: 2 проблемы на 6 строк = 1 - (2/6)
    assert score.completeness == pytest.approx(1 - (2 / 6))
    
    # Validity: 2 проблемы на 6 строк = 1 - (2/6)
    assert score.validity == pytest.approx(1 - (2 / 6))
    
    # Consistency: нет ошибок
    assert score.consistency == pytest.approx(1.0)
    
    # Uniqueness: 2 лишних дубликата на 6 строк = 1 - (2/6)
    assert score.uniqueness == pytest.approx(1 - (2 / 6))
    
    # Total Score: объединяем индексы.
    # Completeness (0, 1) | Validity (1, 2) | Uniqueness (3, 4, 5) -> Всего уникальных "грязных" строк: 0, 1, 2, 3, 4, 5
    # По текущей логике total_score = 1 - (len({0..5}) / 6) = 1 - (6/6) = 0.0
    assert score.total == pytest.approx(0.0)

def test_compute_dq_score_empty_df():
    """Тест на пустом датасете (все скоры должны быть 1.0)"""
    df = pd.DataFrame()
    report = Report(total_rows=0, issues=[])
    score = compute_dq_score(df, report)
    
    assert score.completeness == pytest.approx(1.0)
    assert score.validity == pytest.approx(1.0)
    assert score.consistency == pytest.approx(1.0)
    assert score.uniqueness == pytest.approx(1.0)
    assert score.total == pytest.approx(1.0)

def test_to_dict():
    """Проверяем, что to_dict отдаёт нужный словарь для отрисовки графиков"""
    issues = []
    report = Report(total_rows=10, issues=issues)
    df = pd.DataFrame({'id': range(10)})
    
    score = compute_dq_score(df, report)
    score_dict = score.to_dict()
    
    assert score_dict == {
        "completeness": 1.0,
        "validity": 1.0,
        "consistency": 1.0,
        "uniqueness": 1.0
    }