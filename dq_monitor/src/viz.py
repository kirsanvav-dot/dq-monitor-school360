"""
Переиспользуемые графики на plotly.

Все функции принимают данные и возвращают plotly.graph_objects.Figure.
Никаких прямых вызовов streamlit здесь — иначе модуль становится
непереиспользуемым и нетестируемым.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def plot_dq_score_radar(scores: dict, title: str = "DQ Score") -> go.Figure:
    """Радар по 4 измерениям качества данных.

    Args:
        scores: dict вида {"completeness": 0.95, "validity": 0.88, ...}
        title: заголовок графика.
    """
    dimensions = ["completeness", "validity", "consistency", "uniqueness"]
    values = [scores.get(d, 0) for d in dimensions]
    # Радар замыкается — нужно повторить первое значение в конце
    values_closed = values + [values[0]]
    labels_closed = [d.capitalize() for d in dimensions] + [dimensions[0].capitalize()]

    fig = go.Figure(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            line_color="#1f77b4",
        )
    )
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        showlegend=False,
        title=title,
        height=400,
    )
    return fig


def plot_dq_score_comparison(before: dict, after: dict) -> go.Figure:
    """Сравнение DQ-score до и после очистки. Один из ключевых слайдов защиты."""
    dimensions = ["completeness", "validity", "consistency", "uniqueness"]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="До очистки",
        x=dimensions,
        y=[before.get(d, 0) for d in dimensions],
        marker_color="#d62728",
    ))
    fig.add_trace(go.Bar(
        name="После очистки",
        x=dimensions,
        y=[after.get(d, 0) for d in dimensions],
        marker_color="#2ca02c",
    ))
    fig.update_layout(
        barmode="group",
        yaxis_title="DQ Score",
        yaxis_range=[0, 1.05],
        height=400,
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def plot_confusion_matrix(cm_dict: dict, title: str) -> go.Figure:
    """Confusion matrix как heatmap.

    Args:
        cm_dict: словарь с ключами tp, fp, fn, tn (как из ConfusionMatrix.to_dict()).
        title: заголовок (например, "Грязные данные").
    """
    matrix = [
        [cm_dict["tn"], cm_dict["fp"]],
        [cm_dict["fn"], cm_dict["tp"]],
    ]
    labels = [
        [f"TN<br>{cm_dict['tn']:,}", f"FP<br>{cm_dict['fp']:,}"],
        [f"FN<br>{cm_dict['fn']:,}", f"TP<br>{cm_dict['tp']:,}"],
    ]
    fig = go.Figure(go.Heatmap(
        z=matrix,
        x=["Predicted: not fraud", "Predicted: fraud"],
        y=["Real: not fraud", "Real: fraud"],
        text=labels,
        texttemplate="%{text}",
        colorscale="Blues",
        showscale=False,
    ))
    fig.update_layout(title=title, height=350)
    return fig


def plot_issues_breakdown(issues_df: pd.DataFrame) -> go.Figure:
    """Топ DQ-проблем по числу затронутых строк.

    Args:
        issues_df: DataFrame с колонками 'issue_type', 'dimension', 'rows_affected'.
    """
    if issues_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="Проблемы не найдены", showarrow=False)
        return fig

    sorted_df = issues_df.sort_values("rows_affected", ascending=True).tail(15)
    fig = px.bar(
        sorted_df,
        x="rows_affected",
        y="issue_type",
        color="dimension",
        orientation="h",
        labels={"rows_affected": "Затронуто строк", "issue_type": ""},
        height=500,
    )
    fig.update_layout(legend=dict(orientation="h", y=1.1))
    return fig


def plot_transactions_timeline(df: pd.DataFrame, granularity: str = "D") -> go.Figure:
    """Таймлайн активности — число транзакций по дням/часам.

    Помогает увидеть аномальные пики и провалы в данных.
    """
    df = df.copy()
    df["event_ts_parsed"] = pd.to_datetime(df["event_ts"], errors="coerce")
    txn = df[(df["event_type"] == "transaction") & df["event_ts_parsed"].notna()]
    counts = txn.set_index("event_ts_parsed").resample(granularity).size()

    fig = px.line(
        x=counts.index, y=counts.values,
        labels={"x": "Время", "y": "Транзакций"},
        height=350,
    )
    return fig


def plot_amount_distribution(df: pd.DataFrame) -> go.Figure:
    """Распределение сумм транзакций — лог-шкала, чтобы хвост был виден."""
    amounts = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
    amounts = amounts[amounts > 0]
    if amounts.empty:
        return go.Figure()
    fig = px.histogram(
        x=amounts, nbins=80, log_y=True,
        labels={"x": "Сумма, ₽"}, height=350,
    )
    return fig
