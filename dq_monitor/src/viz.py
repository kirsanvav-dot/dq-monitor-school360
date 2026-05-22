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
        xaxis=dict(title="Процент качества данных, %", range=[0, 105], tickfont=dict(size=14)),
        yaxis=dict(title="", tickfont=dict(size=14)),
        height=300,
        margin=dict(l=20, r=20, t=60, b=40),
        font=dict(family="Arial, sans-serif", size=15, color="black"),
        title_font=dict(size=22, family="Arial, sans-serif")
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_cleaning_actions(log_df: pd.DataFrame):
    """Отрисовка круговой диаграммы и бар-чарта по результатам очистки."""
    if log_df.empty:
        st.info("Лог очистки пуст.")
        return

    # Мэппинг технических названий на русский для графиков
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
        # Круговая диаграмма действий
        action_summary = vis_df.groupby("Метод")["rows_affected"].sum().reset_index()
        fig_pie = px.pie(
            action_summary,
            names="Метод",
            values="rows_affected",
            title="Структура методов очистки",
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_layout(
            font=dict(family="Arial, sans-serif", size=15),
            title_font=dict(size=22)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Горизонтальный бар-чарт по описаниям проблем
        fig_bar = px.bar(
            vis_df,
            x="rows_affected",
            y="description",
            color="Метод",
            orientation="h",
            title="Строк затронуто каждым правилом",
            labels={"rows_affected": "Количество строк", "description": "Тип проблемы"}
        )
        fig_bar.update_layout(
            font=dict(family="Arial, sans-serif", size=15),
            title_font=dict(size=22),
            yaxis={'categoryorder': 'total ascending', 'title': ''}
        )
        st.plotly_chart(fig_bar, use_container_width=True)


def plot_dq_score_radar(scores: Dict[str, float]):
    """Радар-чарт по 4 измерениям DQ. На осях — английский по требованию."""
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
    fig.update_traces(fill='toself', line_color='#1f77b4', marker=dict(size=10))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=12)),
            angularaxis=dict(tickfont=dict(size=14))
        ),
        title="Радар качества данных",
        font=dict(family="Arial, sans-serif", size=15, color="black"),
        title_font=dict(size=22, family="Arial, sans-serif")
    )
    return fig


def plot_issues_breakdown(report_df: pd.DataFrame):
    """Гистограмма количества найденных проблем по категориям."""
    if report_df.empty:
        return go.Figure()

    dim_map = {
        "Completeness": "Полнота",
        "Validity": "Валидность",
        "Consistency": "Согласованность",
        "Uniqueness": "Уникальность"
    }

    summary_df = report_df.copy()
    if "dimension" in summary_df.columns:
        summary_df["dimension"] = summary_df["dimension"].replace(dim_map)

    summary = summary_df.groupby("dimension").size().reset_index(name="count")

    fig = px.bar(
        summary, x="dimension", y="count",
        title="Проблемы по категориям качества",
        labels={"dimension": "Измерение DQ", "count": "Количество типов ошибок"},
        color_discrete_sequence=['#1f77b4']
    )
    fig.update_layout(
        font=dict(family="Arial, sans-serif", size=15),
        title_font=dict(size=22),
        xaxis_title="Измерение DQ",
        yaxis_title="Кол-во типов проблем"
    )
    return fig


def show_full_cleaning_report(log_df: pd.DataFrame, total_before: int, total_after: int):
    """Сводный отчет по очистке для Streamlit."""
    st.markdown("### 📊 Анализ очистки")
    c1, c2, c3 = st.columns(3)
    c1.metric("Было строк", f"{total_before:,}")
    c2.metric("Стало строк", f"{total_after:,}")
    c3.metric("Удалено", f"{total_before - total_after:,}", delta_color="inverse")

    st.divider()
    plot_cleaning_actions(log_df)
    st.divider()

    st.subheader("📋 Детальный лог")
    tbl = log_df.rename(columns={
        "clean_action": "Действие",
        "dimension": "Измерение",
        "issue_type": "Код",
        "description": "Описание",
        "rows_affected": "Изменено строк"
    })
    st.dataframe(tbl, use_container_width=True, hide_index=True)


def plot_confusion_matrix(cm_dict: dict, title: str):
    """Отрисовка Heatmap для антифрод-демо."""
    # TN, FP, FN, TP
    z = [
        [cm_dict['tn'], cm_dict['fn']],  # Норма
        [cm_dict['fp'], cm_dict['tp']]  # Фрод
    ]
    x = ['Реально Норма', 'Реально Фрод']
    y = ['Вердикт: НОРМА', 'Вердикт: ФРОД']

    annotations = [
        [f"Правильно: {cm_dict['tn']}<br>(TN)", f"Пропущено: {cm_dict['fn']}<br>(FN)"],
        [f"Ложно: {cm_dict['fp']}<br>(FP)", f"ПОЙМАНО: {cm_dict['tp']}<br>(TP)"]
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z, x=x, y=y,
        text=annotations,
        texttemplate="%{text}",
        colorscale='Blues',
        showscale=False
    ))

    fig.update_layout(
        title=title,
        font=dict(family="Arial, sans-serif", size=14),
        title_font=dict(size=20),
        height=400,
        xaxis_title="Истинное положение дел",
        yaxis_title="Решение системы",
        margin=dict(l=20, r=20, t=60, b=20)
    )
    return fig