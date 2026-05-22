import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict


def plot_dq_score_comparison(score_before: float, score_after: float):
    """Отрисовка сравнения Score до и после очистки."""
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=["До очистки", "После очистки"],
        x=[score_before, score_after],
        orientation='h',
        marker=dict(color=["#EF553B", "#00CC96"]),
        text=[f"{score_before:.1f}%", f"{score_after:.1f}%"],
        textposition='auto',
    ))
    fig.update_layout(
        title="📊 Динамика качества данных (DQ-Score)",
        xaxis=dict(title="Уровень качества, %", range=[0, 105], tickfont=dict(size=14)),
        yaxis=dict(title="", tickfont=dict(size=14)),
        height=300,
        margin=dict(l=20, r=20, t=60, b=40),
        font=dict(family="Arial, sans-serif", size=15, color="black"),
        title_font=dict(size=22, family="Arial, sans-serif")
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_cleaning_actions(log_df: pd.DataFrame):
    """Отрисовка графиков по результатам очистки."""
    if log_df.empty:
        return

    action_translation = {
        "correction": "Исправление",
        "zeroing": "Зануление (NaN)",
        "delete": "Удаление строк",
        "ignore": "Пропущено"
    }

    vis_df = log_df.copy()
    vis_df["Метод"] = vis_df["clean_action"].map(action_translation).fillna(vis_df["clean_action"])

    col1, col2 = st.columns(2)
    with col1:
        action_summary = vis_df.groupby("Метод")["rows_affected"].sum().reset_index()
        fig_pie = px.pie(action_summary, names="Метод", values="rows_affected", title="Структура методов очистки")
        fig_pie.update_layout(font=dict(family="Arial", size=15), title_font=dict(size=22))
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        fig_bar = px.bar(vis_df, x="rows_affected", y="description", color="Метод",
                         orientation="h", title="Исправления по правилам",
                         labels={"rows_affected": "Количество", "description": "Тип проблемы"})
        fig_bar.update_layout(font=dict(family="Arial", size=15), title_font=dict(size=22),
                              yaxis={'categoryorder': 'total ascending', 'title': ''},
                              xaxis={'title': 'Количество'})
        st.plotly_chart(fig_bar, use_container_width=True)


def plot_dq_score_radar(scores: Dict[str, float]):
    """Радар-чарт. На осях английский по требованию."""
    translate = {
        "completeness": "Completeness",
        "validity": "Validity",
        "consistency": "Consistency",
        "uniqueness": "Uniqueness"
    }

    df = pd.DataFrame(dict(
        r=list(scores.values()),
        theta=[translate.get(k, k) for k in scores.keys()]
    ))

    fig = px.line_polar(df, r='r', theta='theta', line_close=True)
    fig.update_traces(fill='toself', line_color='#1f77b4')
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        title="Радар качества данных",
        font=dict(family="Arial", size=15),
        title_font=dict(size=22)
    )
    return fig


def plot_issues_breakdown(report_df: pd.DataFrame):
    """Гистограмма проблем. Категории — английский, оси — русский."""
    if report_df.empty: return go.Figure()

    summary = report_df.groupby("dimension").size().reset_index(name="count")
    fig = px.bar(summary, x="dimension", y="count", title="Проблемы по категориям качества",
                 labels={"dimension": "Измерение DQ", "count": "Количество"},
                 color_discrete_sequence=['#1f77b4'])
    fig.update_layout(
        font=dict(family="Arial", size=15),
        title_font=dict(size=22),
        yaxis_title="Количество"
    )
    return fig


def show_full_cleaning_report(log_df: pd.DataFrame, total_before: int, total_after: int):
    """Сводный отчет по очистке. Нумерация с 1, центрирование."""
    st.markdown("### 📊 Анализ очистки")
    c1, c2, c3 = st.columns(3)
    c1.metric("Было строк", f"{total_before:,}")
    c2.metric("Стало строк", f"{total_after:,}")
    c3.metric("Удалено", f"{total_before - total_after:,}", delta_color="inverse")

    st.divider()
    plot_cleaning_actions(log_df)
    st.divider()

    st.subheader("📋 Детальный лог")

    # Очистка колонок
    cols_to_drop = [c for c in ['column'] if c in log_df.columns]
    tbl = log_df.drop(columns=cols_to_drop).rename(columns={
        "clean_action": "Действие",
        "dimension": "Измерение",
        "issue_type": "Код",
        "description": "Описание",
        "rows_affected": "Изменено строк"
    })

    # Нумерация с 1
    tbl.index = range(1, len(tbl) + 1)

    # Вывод таблицы с центрированием
    st.table(tbl.style.set_properties(**{'text-align': 'center'}))


def plot_confusion_matrix(cm_dict: dict, title: str):
    """Матрица ошибок для демо. Русский язык в осях."""
    z = [[cm_dict['tn'], cm_dict['fn']], [cm_dict['fp'], cm_dict['tp']]]
    x = ['Реально Норма', 'Реально Фрод']
    y = ['Вердикт: НОРМА', 'Вердикт: ФРОД']

    annotations = [
        [f"Правильно: {cm_dict['tn']}<br>(TN)", f"Пропущено: {cm_dict['fn']}<br>(FN)"],
        [f"Ложно: {cm_dict['fp']}<br>(FP)", f"ПОЙМАНО: {cm_dict['tp']}<br>(TP)"]
    ]

    fig = go.Figure(data=go.Heatmap(z=z, x=x, y=y, text=annotations, texttemplate="%{text}",
                                    colorscale='Blues', showscale=False))

    fig.update_layout(
        title=title,
        font=dict(family="Arial", size=14),
        title_font=dict(size=20),
        xaxis_title="Истина",
        yaxis_title="Предсказание"
    )
    return fig