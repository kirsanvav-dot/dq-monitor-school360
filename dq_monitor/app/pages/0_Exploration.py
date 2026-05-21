import numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

# --- Настройка путей (чтобы не было ModuleNotFoundError) ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Загрузка данных
if "df_dirty" not in st.session_state:
    # Используем относительный путь от корня проекта или абсолютный, если файл там
    try:
        df = pd.read_csv(r"dq_monitor\data\raw\events_dirty.csv")
    except:
        # Фолбек для разных окружений
        df = pd.read_csv("data/raw/events_dirty.csv")
    st.session_state["df_dirty"] = df

df = st.session_state["df_dirty"]

# --- Стилизация страницы ---
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)

st.title("🔍 Разведочный анализ данных")

# --- ГРАФИК 1: ГИСТОГРАММА СУММ ---
amounts = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
amounts = amounts[amounts > 0]
bins = [0, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 2000000, 5000000, 10000000, 20000000, np.inf]
labels = ["0-1k", "1k-5k", "5k-10k", "10k-50k", "50k-100k", "100k-500k", "500k-1M", "1M-2M", "2M-5M", "5M-10M", "10M-20M", "20M+"]
binned = pd.cut(amounts, bins=bins, labels=labels, ordered=True)

fig1 = px.histogram(
    x=binned,
    category_orders={"x": labels},
    labels={"x": "Сумма транзакции, ₽", "y": "Количество транзакций"}
)
fig1.update_layout(
    yaxis_title="Количество транзакций",
    bargap=0.1,
    title='Зависимость суммы и количества транзакций',
    font=dict(family="Arial, sans-serif", size=15),
    title_font=dict(size=22)
)
fig1.update_yaxes(
    type="log",
    tickvals=[100, 500, 1000, 5000, 10000, 50000],
    ticktext=["100", "500", "1k", "5k", "10k", "50k"]
)
st.plotly_chart(fig1, use_container_width=True)

# --- ГРАФИК 2: РАСПРЕДЕЛЕНИЕ ПО ЧАСАМ ---
df["event_ts_parsed"] = pd.to_datetime(df["event_ts"], errors="coerce")
hourly = df["event_ts_parsed"].dt.hour.value_counts().sort_index().reset_index()
hourly.columns = ["hour", "event_count"]
hourly["time_of_day"] = hourly["hour"].apply(lambda x: "Ночь (Риск фрода)" if x < 6 else "Обычное время")

fig2 = px.bar(
    hourly, x="hour", y="event_count", color="time_of_day",
    color_discrete_map={"Ночь (Риск фрода)": "#ff4b4b", "Обычное время": "#1f77b4"},
    labels={"hour": "Часы", "event_count": "Число событий", "time_of_day": "Период"}
)
fig2.update_layout(
    title='Распределение транзакций относительно времени суток',
    font=dict(family="Arial, sans-serif", size=15),
    title_font=dict(size=22),
    yaxis_title="Число событий"
)
fig2.update_xaxes(tickmode='linear', dtick=1)
st.plotly_chart(fig2, use_container_width=True)

# --- ГРАФИК 3: ТОП-15 КАТЕГОРИЙ (ИСПРАВЛЕННЫЙ ФИЛЬТР) ---
mcc_mapping = {
    "5411": "grocery", "5812": "restaurant", "5541": "gas_station",
    "4111": "transport", "5732": "electronics", "5651": "clothing",
    "5969": "online_shopping", "7832": "entertainment", "8011": "healthcare",
    "8220": "education", "4900": "utilities", "6011": "atm_withdrawal",
    "6051": "crypto_exchange", "7995": "gambling", "4829": "wire_transfer_abroad",
}

df1 = df.copy()
# Сначала помечаем ошибки, потом заменяем коды на текст
df1['is_error'] = df1['merchant_category'].astype(str).isin(mcc_mapping.keys())
df1['merchant_category'] = df1['merchant_category'].astype(str).replace(mcc_mapping)

# ФИКС: Убираем все виды пустых значений (nan, <NA>, None, пустые строки)
bad_labels = ['nan', '<na>', 'none', 'nat', '']
df1 = df1[
    df1['merchant_category'].notna() &
    (~df1['merchant_category'].astype(str).str.lower().isin(bad_labels))
]

# Считаем топ-15 БЕЗ пустых значений
top_cats = df1['merchant_category'].value_counts().head(15).index

agg = (
    df1[df1['merchant_category'].isin(top_cats)]
    .groupby('merchant_category')['is_error']
    .agg(total='count', errors='sum')
    .reset_index()
)
agg['correct'] = agg['total'] - agg['errors']
agg = agg.sort_values('total', ascending=True)

fig3 = go.Figure()
fig3.add_trace(go.Bar(
    y=agg['merchant_category'], x=agg['correct'], name='Корректно (текст)',
    orientation='h', marker=dict(color='#1f77b4')
))
fig3.add_trace(go.Bar(
    y=agg['merchant_category'], x=agg['errors'], name='Ошибка кодировки (цифры)',
    orientation='h', marker=dict(color='#d62728')
))

fig3.update_layout(
    barmode='stack',
    title='Топ-15 категорий: доля транзакций с ошибочной кодировкой',
    xaxis_title='Количество транзакций',
    yaxis_title='Категория',
    legend=dict(title='Формат записи', font=dict(size=14)),
    height=500,
    font=dict(family="Arial, sans-serif", size=15),
    title_font=dict(size=22)
)
st.plotly_chart(fig3, use_container_width=True)

# --- ГРАФИК 4: КРУГОВАЯ ДИАГРАММА ---
events_by_type = df["event_type"].value_counts()
fig4 = px.pie(
    values=events_by_type.values, names=events_by_type.index,
    color_discrete_sequence=['#1f77b4', '#10B981'], hole=0.6
)
fig4.update_layout(
    title='Структура пользовательских действий',
    font=dict(family="Arial, sans-serif", size=15),
    title_font=dict(size=22)
)
fig4.update_traces(textfont_size=18, insidetextfont=dict(size=18))
st.plotly_chart(fig4, use_container_width=True)