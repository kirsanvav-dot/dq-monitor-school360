import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict

# --- БАЗОВЫЙ ШРИФТ ДЛЯ ВСЕХ ГРАФИКОВ ---
GLOBAL_FONT = dict(family="Arial, sans-serif", size=14, color="#334155")
TITLE_FONT = dict(family="Arial Black, Arial, sans-serif", size=20, color="#0f172a")


def plot_dq_score_comparison(score_before: float, score_after: float):
    y_labels = ["После очистки", "До очистки"]
    x_values = [score_after, score_before]
    colors = ["#0ea5e9", "#1e293b"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=y_labels, x=x_values, orientation='h',
        marker=dict(color=colors, line=dict(color='white', width=2)),
        text=[f"{score_after:.1f}%", f"{score_before:.1f}%"],
        texttemplate="   %{text}", textposition='outside', cliponaxis=False,
        textfont=dict(family="Arial", size=15, color="#0f172a", weight="bold")
    ))

    fig.update_layout(
        title="📊 Динамика качества данных (DQ-Score)",
        font=GLOBAL_FONT, title_font=TITLE_FONT,
        xaxis=dict(title="Уровень качества, %", range=[0, 120], tickfont=dict(size=14), showgrid=True,
                   gridcolor='rgba(203, 213, 225, 0.5)', zeroline=False),
        yaxis=dict(tickfont=dict(size=16, color="black", family="Arial Black")),
        plot_bgcolor="rgba(241, 245, 249, 0.5)", paper_bgcolor="white",
        height=320, margin=dict(l=20, r=40, t=80, b=40), bargap=0.35
    )
    st.plotly_chart(fig, use_container_width=True)


def shorten_description(desc: str) -> str:
    desc = desc.replace("Пропущено обязательное значение ", "Пропуск: ")
    desc = desc.replace("Некорректный формат данных времени ", "Формат: ")
    desc = desc.replace("Некорректный формат значения ", "Формат: ")
    desc = desc.replace("Некорректный формат ", "Формат: ")
    desc = desc.replace("Выход за пределы допустимых значений ", "Аномалия: ")
    desc = desc.replace("Несогласованны поля ", "Рассинхрон: ")
    desc = desc.replace("При типе операции transaction заполнены поля, соответствующие типу session",
                        "Поля сессии в транзакции")
    desc = desc.replace("При типе операции session заполнены поля, соответствующие типу transaction",
                        "Поля транзакции в сессии")
    desc = desc.replace(" при типе операции transaction", "")
    desc = desc.replace(" при типе операции session", "")
    desc = desc.replace(" при is_flagged == true", "")
    return desc


def plot_cleaning_actions(log_df: pd.DataFrame):
    if log_df.empty: return
    action_translation = {"correction": "Исправление", "zeroing": "Зануление (NaN)", "delete": "Удаление строк",
                          "ignore": "Пропущено"}
    color_map = {"Исправление": "#2563eb", "Зануление (NaN)": "#38bdf8", "Удаление строк": "#ef4444",
                 "Пропущено": "#94a3b8"}

    vis_df = log_df.copy()
    vis_df["Метод"] = vis_df["clean_action"].map(action_translation).fillna(vis_df["clean_action"])
    vis_df["short_desc"] = vis_df["description"].apply(shorten_description)

    col1, col2 = st.columns(2)
    with col1:
        action_summary = vis_df.groupby("Метод")["rows_affected"].sum().reset_index()
        fig_pie = px.pie(action_summary, names="Метод", values="rows_affected", title="Структура методов очистки",
                         color="Метод", color_discrete_map=color_map)
        fig_pie.update_layout(font=GLOBAL_FONT, title_font=TITLE_FONT)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        fig_bar = px.bar(vis_df, x="rows_affected", y="short_desc", color="Метод", orientation="h",
                         title="Исправления по правилам",
                         labels={"rows_affected": "Количество", "short_desc": "Проблема"}, color_discrete_map=color_map)
        fig_bar.update_layout(font=GLOBAL_FONT, title_font=TITLE_FONT,
                              yaxis={'categoryorder': 'total ascending', 'title': '', 'tickfont': dict(size=13)},
                              xaxis=dict(title='Количество', tickangle=0))
        st.plotly_chart(fig_bar, use_container_width=True)


def plot_dq_score_radar(scores: Dict[str, float]):
    translate = {"completeness": "Completeness", "validity": "Validity", "consistency": "Consistency",
                 "uniqueness": "Uniqueness"}
    df = pd.DataFrame(dict(r=list(scores.values()), theta=[translate.get(k, k) for k in scores.keys()]))

    fig = px.line_polar(df, r='r', theta='theta', line_close=True)
    fig.update_traces(fill='toself', line_color='#1f77b4')
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=12)),
                   angularaxis=dict(tickfont=dict(size=15, weight="bold"))),
        title="Радар качества данных", font=GLOBAL_FONT, title_font=TITLE_FONT
    )
    return fig


def plot_issues_breakdown(report_df: pd.DataFrame):
    if report_df.empty: return go.Figure()
    summary = report_df.groupby("dimension").size().reset_index(name="count")
    fig = px.bar(summary, x="dimension", y="count", title="Проблемы по категориям качества",
                 labels={"dimension": "Измерение DQ", "count": "Количество"}, color_discrete_sequence=['#1f77b4'])
    fig.update_layout(font=GLOBAL_FONT, title_font=TITLE_FONT, xaxis=dict(tickfont=dict(size=15, weight="bold")),
                      yaxis=dict(title="Количество", tickangle=0))
    return fig


def show_full_cleaning_report(log_df: pd.DataFrame, total_before: int, total_after: int):
    st.markdown("### 📊 Анализ очистки")
    c1, c2, c3 = st.columns(3)
    c1.metric("Было строк", f"{total_before:,}")
    c2.metric("Стало строк", f"{total_after:,}")
    c3.metric("Удалено", f"{total_before - total_after:,}", delta_color="inverse")

    st.divider()
    plot_cleaning_actions(log_df)
    st.divider()
    st.subheader("📋 Детальный лог")

    cols_to_drop = [c for c in ['column'] if c in log_df.columns]
    tbl = log_df.drop(columns=cols_to_drop).rename(
        columns={"clean_action": "Действие", "dimension": "Измерение", "issue_type": "Код", "description": "Описание",
                 "rows_affected": "Изменено строк"})
    action_translation = {"correction": "Исправление", "zeroing": "Зануление (NaN)", "delete": "Удаление",
                          "ignore": "Пропущено"}
    tbl["Действие"] = tbl["Действие"].map(action_translation).fillna(tbl["Действие"])

    tbl.index = range(1, len(tbl) + 1)
    st.table(tbl.style.set_properties(**{'text-align': 'center'}))


def plot_confusion_matrix(cm_dict: dict, title: str):
    z = [[cm_dict['tn'], cm_dict['fn']], [cm_dict['fp'], cm_dict['tp']]]
    x = ['Реально Норма', 'Реально Фрод']
    y = ['Вердикт: НОРМА', 'Вердикт: ФРОД']
    annotations = [[f"Правильно: {cm_dict['tn']}<br>(TN)", f"Пропущено: {cm_dict['fn']}<br>(FN)"],
                   [f"Ложно: {cm_dict['fp']}<br>(FP)", f"ПОЙМАНО: {cm_dict['tp']}<br>(TP)"]]

    fig = go.Figure(
        data=go.Heatmap(z=z, x=x, y=y, text=annotations, texttemplate="%{text}", textfont=dict(family="Arial", size=16),
                        colorscale='Blues', showscale=False))
    fig.update_layout(title=title, font=GLOBAL_FONT, title_font=TITLE_FONT, xaxis_title="Истина",
                      yaxis_title="Предсказание", height=400, xaxis=dict(tickfont=dict(size=14, weight="bold")),
                      yaxis=dict(tickfont=dict(size=14, weight="bold")))
    return fig