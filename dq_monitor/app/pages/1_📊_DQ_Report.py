"""DQ Report — обзор найденных проблем качества данных (режим ручного тестирования)."""
import sys
from os import write
from pathlib import Path
import pandas as pd

#from dq_monitor.src.profiler import rows_affected

#from dq_monitor.src.constant_issue import IssueType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="DQ Report", page_icon="📊", layout="wide")
st.title("📊 DQ Report")

if "df_dirty" not in st.session_state:
    st.warning("Сначала загрузите датасет на главной странице.")
    st.stop()
from src.constant_issue import IssueType
# Импортируем все классы — даже если внутри есть ошибки, они проявятся только при вызове методов
from src.profiler import DataProfiler, Report, DQIssue
from src.dq_scorer import compute_dq_score
from src.viz import plot_dq_score_radar, plot_issues_breakdown

# ------------------------------------------------------------------
# Дальше код закомментирован до полной готовности модулей.
# Чтобы проверить конкретный класс, раскомментируйте нужные строки
# или используйте временные st.write() прямо здесь.
# ------------------------------------------------------------------
#from src/profiler.py import Report

report = Report(
    total_rows=5,
    issues=[
        # COMPLETENESS (Пустые значения)
        DQIssue(issue_type=IssueType.EMPTY_EVENT_ID, affected_indices=pd.Index([1])),
        DQIssue(issue_type=IssueType.EMPTY_CLIENT_ID, affected_indices=pd.Index([2, 3])),
        DQIssue(issue_type=IssueType.EMPTY_EVENT_TS, affected_indices=pd.Index([4])),
        DQIssue(issue_type=IssueType.EMPTY_DEVICE_TYPE, affected_indices=pd.Index([5, 6, 7]), ),
        DQIssue(issue_type=IssueType.EMPTY_GEO_CITY, affected_indices=pd.Index([8, 9]), ),
        DQIssue(issue_type=IssueType.EMPTY_AMOUNT_RUB, affected_indices=pd.Index([10]), ),
        DQIssue(issue_type=IssueType.EMPTY_CURRENCY, affected_indices=pd.Index([11, 12]), ),
        DQIssue(issue_type=IssueType.EMPTY_FLAG_REASON, affected_indices=pd.Index([13]), ),

        # VALIDITY (Некорректный формат)
        DQIssue(issue_type=IssueType.INVALID_FORMAT_DATE, affected_indices=pd.Index([14, 15]), ),
        DQIssue(issue_type=IssueType.INVALID_IP_ADDRESS, affected_indices=pd.Index([16]), ),
        DQIssue(issue_type=IssueType.INVALID_AMOUNT_RUB, affected_indices=pd.Index([17, 18, 19]), ),
        DQIssue(issue_type=IssueType.INVALID_CURRENCY, affected_indices=pd.Index([20, 21]), ),
        DQIssue(issue_type=IssueType.INVALID_MERCHANT_CATEGORY, affected_indices=pd.Index([22]), ),
        DQIssue(issue_type=IssueType.INVALID_CARD_LAST4, affected_indices=pd.Index([23, 24]), ),
        DQIssue(issue_type=IssueType.INVALID_DEVICE_TYPE, affected_indices=pd.Index([25]), ),

        # CONSISTENCY (Противоречивость)
        DQIssue(issue_type=IssueType.INCONSISTENCY_FLAGGED, affected_indices=pd.Index([26, 27]),),
        DQIssue(issue_type=IssueType.INCONSISTENCY_TRANSACTION, affected_indices=pd.Index([28]),),
        DQIssue(issue_type=IssueType.INCONSISTENCY_SESSION, affected_indices=pd.Index([29, 30, 31]),),

        # UNIQUENESS (Дубликаты)
        DQIssue(issue_type=IssueType.DUPLICATE_FULL, affected_indices=pd.Index([32, 33]),),
        DQIssue(issue_type=IssueType.DUPLICATE_EVENT_ID, affected_indices=pd.Index([34, 35, 36]),)
    ]
)

# profiler = DataProfiler()
# report = profiler.profile(df)
# score = compute_dq_score(df, report)
#
# st.session_state["dq_report_before"] = report
# st.session_state["dq_score_before"] = score
#
# cols = st.columns(5)
# cols[0].metric("Total DQ Score", f"{score.total:.3f}")
# cols[1].metric("Completeness", f"{score.completeness:.3f}")
# cols[2].metric("Validity", f"{score.validity:.3f}")
# cols[3].metric("Consistency", f"{score.consistency:.3f}")
# cols[4].metric("Uniqueness", f"{score.uniqueness:.3f}")
#
# st.plotly_chart(plot_dq_score_radar(score.to_dict()))
# st.plotly_chart(plot_issues_breakdown(report.to_dataframe()))
# st.dataframe(report.to_dataframe())

# Пример временного ручного теста (раскомментируйте для проверки):
df = st.session_state["df_dirty"]
profiler = DataProfiler()
# просто покажет объект
#report = profiler.profile(df)
#report1=report.to_dataframe()
#report1.index[3]=''.join(report1.index[3])
#st.write(report1)
#st.dataframe(report.to_dataframe())
df_report = report.to_dataframe()

# 1. Удаляем столбец issue_type
if 'issue_type' in df_report.columns:
    df_report = df_report.drop(columns=['issue_type', 'rows_affected'])


# 2. Универсальная функция очистки от кортежей и скобок
def clean_cell(val):
    # А. Если это настоящий кортеж или список (как в памяти)
    if isinstance(val, (tuple, list, set)):
        return ", ".join([str(i) for i in val])

    # Б. Если это строка, которая выглядит как кортеж, например: "('event_id',)"
    if isinstance(val, str) and val.startswith("(") and val.endswith(")"):
        # Убираем круглые скобки
        cleaned = val.strip("()")
        # Убираем кавычки
        cleaned = cleaned.replace("'", "").replace('"', "")
        # Убираем запятую на конце (бывает, если в кортеже был всего 1 элемент)
        cleaned = cleaned.strip()
        if cleaned.endswith(","):
            cleaned = cleaned[:-1]
        return cleaned.strip()

    # В. Бонус: если в таблице есть объекты (например, DQDimension.COMPLETENESS),
    # достаем из них только имя (COMPLETENESS), чтобы таблица выглядела аккуратнее
    if hasattr(val, 'name'):
        return val.name

    return val


# Применяем очистку ко ВСЕМ ячейкам датафрейма.
# Для новых версий Pandas используется map, для старых — applymap
if hasattr(df_report, 'map'):
    df_report = df_report.map(clean_cell)
else:
    df_report = df_report.applymap(clean_cell)

# 3. Переводим названия колонок на русский
rename_dict = {
    'description': 'Описание проблемы',
    'dimension': 'Категория',
    'column': 'Затронутые столбцы',
    'columns': 'Затронутые столбцы',  # на случай, если называется во множ. числе
    'clean_type': 'Способ обработки',
    'rows_affected': 'Затронуто, кол-во',
    'percent_affected': 'Затронуто, %',
}

df_report = df_report.rename(columns=rename_dict)

df_report = df_report.reset_index(drop=True)
df_report.index = pd.RangeIndex(start=1, stop=len(df_report) + 1, step=1)

# 5. Принудительно форматируем проценты (оставляем 1 знак после точки)
# Если значение пустое (NaN), оставляем его как есть
if 'Затронуто, %' in df_report.columns:
    df_report['Затронуто, %'] = df_report['Затронуто, %'].apply(
        lambda x: f"{float(x):.1f}" if pd.notna(x) else x
    )

# 6. Оформляем таблицу через Pandas Styler и превращаем в HTML
html_table = (
    df_report.style
    .set_properties(**{
        'text-align': 'center',
        'vertical-align': 'middle'
    })
    .set_table_styles([
        # Центрируем заголовки столбцов
        {'selector': 'th', 'props': [('text-align', 'center')]},
        # Растягиваем таблицу на всю ширину контейнера
        {'selector': 'table', 'props': [('width', '100%')]},
        # Даем столбцу "Описание проблемы" больше места (если он идет первым после индекса)
        # nth-child(2) означает второй столбец (1-й это индекс)
        {'selector': 'th:nth-child(1)', 'props': [('width', '3%')]},
{'selector': 'th:nth-child(5)', 'props': [('width', '10%')]},
{'selector': 'th:nth-child(3)', 'props': [('width', '15%')]},
{'selector': 'th:nth-child(4)', 'props': [('width', '50%')]},
{'selector': 'th:nth-child(2)', 'props': [('width', '12%')]}
    ])
    .to_html()
)

# 7. Выводим готовую таблицу через поддержку HTML в Streamlit
st.markdown(html_table, unsafe_allow_html=True)