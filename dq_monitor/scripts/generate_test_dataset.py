"""
Скрипт генерации тестовых датасетов для DQ Monitor.

КАК ИСПОЛЬЗОВАТЬ
─────────────────
Запустить из корня проекта:

    python scripts/generate_test_dataset.py

По умолчанию создаст три датасета в data/test_datasets/:
  • low_severity/    — лёгкий случай: мало фрода, мало DQ-проблем
  • medium_severity/ — реалистичная нагрузка
  • high_severity/   — нагрузочный режим

Каждая папка содержит:
  raw/events_dirty.csv          — грязный датасет (для команды)
  ground_truth/events_clean.csv — эталон (для оценки)
  ground_truth/fraud_labels.csv — метки фрода (для расчёта метрик)

ЗАЧЕМ ЭТО НУЖНО
────────────────
Для защиты: показать, что DQ Monitor работает не только на одном CSV
от ментора, но на любом валидном датасете. На демо удобно переключаться
между low/medium/high — видно, что система стабильна.

ПАРАМЕТРЫ ФУНКЦИИ generate_events
──────────────────────────────────
  seed             — зерно генератора (одинаковый seed → одинаковые данные)
  n_transactions   — сколько событий сгенерировать
  n_clients        — сколько уникальных клиентов
  fraud_intensity  — 'low' / 'medium' / 'high'
  dq_severity      — 'none' / 'low' / 'medium' / 'high'
  output_dir       — куда сохранить CSV-файлы

Подробнее — в dq_monitor/docs/SYNTHETIC_DATA.md
"""
from pathlib import Path
import sys

# Добавляем корень проекта в путь, чтобы импорт работал из любого места
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.synthetic_data import generate_events


def main():
    base = Path("data/test_datasets")

    print("=" * 60)
    print("Генерирую low-severity датасет...")
    print("=" * 60)
    df_d, df_c, labels = generate_events(
        seed=101,
        n_transactions=30_000,
        n_clients=6_000,
        fraud_intensity="low",
        dq_severity="low",
        output_dir=base / "low_severity",
    )
    print(f"  Строк: {len(df_d):,}, фрода: {labels['is_fraud_real'].sum():,}")

    print()
    print("=" * 60)
    print("Генерирую medium-severity датасет...")
    print("=" * 60)
    df_d, df_c, labels = generate_events(
        seed=202,
        n_transactions=50_000,
        n_clients=10_000,
        fraud_intensity="medium",
        dq_severity="medium",
        output_dir=base / "medium_severity",
    )
    print(f"  Строк: {len(df_d):,}, фрода: {labels['is_fraud_real'].sum():,}")

    print()
    print("=" * 60)
    print("Генерирую high-severity датасет...")
    print("=" * 60)
    df_d, df_c, labels = generate_events(
        seed=303,
        n_transactions=80_000,
        n_clients=15_000,
        fraud_intensity="high",
        dq_severity="high",
        output_dir=base / "high_severity",
    )
    print(f"  Строк: {len(df_d):,}, фрода: {labels['is_fraud_real'].sum():,}")

    print()
    print("=" * 60)
    print("ГОТОВО")
    print("=" * 60)
    print(f"Все датасеты сохранены в {base}/")
    print("Загружайте их в DQ Monitor через главную страницу приложения.")


if __name__ == "__main__":
    main()
