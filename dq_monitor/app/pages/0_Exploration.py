import numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Загрузка из файла (можно и через uploader)
if "df_dirty" not in st.session_state:
    df = pd.read_csv(r"dq_monitor\data\raw\events_dirty.csv")   # ← вот здесь указывается путь
    st.session_state["df_dirty"] = df

# Дальше ваш код
df = st.session_state["df_dirty"]
amounts = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
amounts = amounts[amounts > 0]
bins = [
    0,
    1_000,
    5_000,
    10_000,
    50_000,
    100_000,
    500_000,
    1_000_000,
    2_000_000,
    5_000_000,
    10_000_000,
    20_000_000,
    np.inf
]

labels = [
    "0-1k",
    "1k-5k",
    "5k-10k",
    "10k-50k",
    "50k-100k",
    "100k-500k",
    "500k-1M",
    "1M-2M",
    "2M-5M",
    "5M-10M",
    "10M-20M",
    "20M+"
]

binned = pd.cut(amounts, bins=bins, labels=labels, ordered=True)

fig = px.histogram(
    x=binned,
    #log_y=True,
    category_orders={"x": labels},
    labels={
        "x": "Сумма транзакции, ₽",
        "y": "Количество транзакций"
    }
)

fig.update_layout(
    yaxis_title="Количество транзакций",
    bargap=0.1,
    title='Зависимость суммы и количества транзакций',
    font=dict(family="Arial, sans-serif", size=15, color="black"),
    title_font=dict(size=22, family="Arial, sans-serif"),
    xaxis_title_font=dict(size=16),
    yaxis_title_font=dict(size=16),
    legend_font=dict(size=14)
)

fig.update_yaxes(
    type="log",
    tickvals=[100, 500, 1000, 5000, 10000, 50000],
    ticktext=["100", "500", "1k", "5k", "10k", "50k"],
    tickfont=dict(size=14)
)
fig.update_xaxes(tickfont=dict(size=14))

st.plotly_chart(fig)

# Второй график: распределение по часам
df["event_ts_parsed"] = pd.to_datetime(df["event_ts"], errors="coerce")

hourly = df["event_ts_parsed"].dt.hour.value_counts().sort_index().reset_index()
hourly.columns = ["hour", "event_count"]
hourly["time_of_day"] = hourly["hour"].apply(lambda x: "Ночь (Риск фрода)" if x < 6 else "Обычное время")

fig = px.bar(
    hourly,
    x="hour",
    y="event_count",
    color="time_of_day",
    color_discrete_map={
        "Ночь (Риск фрода)": "#ff4b4b",
        "Обычное время": "#1f77b4"
    },
    labels={
        "hour": "Часы",
        "event_count": "Число событий",
        "time_of_day": "Период"
    }
)

fig.update_layout(
    title='Распределение числа транзакций относительно времени суток',
    font=dict(family="Arial, sans-serif", size=15),
    title_font=dict(size=22),
    xaxis_title_font=dict(size=16),
    yaxis_title_font=dict(size=16),
    legend_font=dict(size=14),
    yaxis_title="Число событий"
)
fig.update_xaxes(tickmode='linear', dtick=1, tickfont=dict(size=14))
fig.update_yaxes(tickfont=dict(size=14))

st.plotly_chart(fig)

# Третий график: топ-15 категорий с ошибками кодировки
mcc_mapping = {
    "5411": "grocery",
    "5812": "restaurant",
    "5541": "gas_station",
    "4111": "transport",
    "5732": "electronics",
    "5651": "clothing",
    "5969": "online_shopping",
    "7832": "entertainment",
    "8011": "healthcare",
    "8220": "education",
    "4900": "utilities",
    "6011": "atm_withdrawal",
    "6051": "crypto_exchange",
    "7995": "gambling",
    "4829": "wire_transfer_abroad",
}
df1=df.copy()
df1['is_error'] = df1['merchant_category'].astype(str).isin(mcc_mapping.keys())
df1['merchant_category'] = df1['merchant_category'].astype(str).replace(mcc_mapping)

df1 = df1[
    df1['merchant_category'].notna() &
    (df1['merchant_category'].astype(str).str.lower() != 'nan')
]
top_cats = (
    df1['merchant_category']
    .value_counts(dropna=False)
    .head(15)
    .index
)

mask = df1['merchant_category'].isin(top_cats)
agg = (
    df1.loc[mask]
    .groupby('merchant_category')['is_error']
    .agg(total='count', errors='sum')
    .reset_index()
)
agg['correct'] = agg['total'] - agg['errors']
agg = agg.sort_values('total', ascending=True)

fig = go.Figure()

fig.add_trace(go.Bar(
    y=agg['merchant_category'],
    x=agg['correct'],
    name='Корректно (текст)',
    orientation='h',
    marker=dict(color='#1f77b4'),
    hovertemplate='%{y}: %{x} корректных<extra></extra>'
))

fig.add_trace(go.Bar(
    y=agg['merchant_category'],
    x=agg['errors'],
    name='Ошибка кодировки (цифры)',
    orientation='h',
    marker=dict(color='#d62728'),
    hovertemplate='%{y}: %{x} с ошибкой кодировки<extra></extra>'
))

fig.update_layout(
    barmode='stack',
    title='Топ-15 категорий: доля транзакций с ошибочной кодировкой',
    xaxis_title='Количество транзакций',
    yaxis_title='Категория',
    legend=dict(title='Формат записи', font=dict(size=14)),
    height=500,
    font=dict(family="Arial, sans-serif", size=15),
    title_font=dict(size=22, family="Arial, sans-serif"),
    xaxis_title_font=dict(size=16),
    yaxis_title_font=dict(size=16)
)

fig.update_xaxes(tickfont=dict(size=14))
fig.update_yaxes(tickfont=dict(size=14))

st.plotly_chart(fig)

# Четвёртый график: круговая диаграмма
events_by_type = df["event_type"].value_counts()
soft_colors = ['#1f77b4', '#10B981']
fig = px.pie(
    values=events_by_type.values,
    names=events_by_type.index,
    color_discrete_sequence=soft_colors,
    hole=0.6
)

fig.update_layout(
    title='Структура пользовательских действий',
    font=dict(family="Arial, sans-serif", size=15),
    title_font=dict(size=22),
    legend=dict(font=dict(size=16))
)


fig.update_traces(
    textfont_size=18,
    textposition='inside',
    insidetextfont=dict(size=18)
)

st.plotly_chart(fig)