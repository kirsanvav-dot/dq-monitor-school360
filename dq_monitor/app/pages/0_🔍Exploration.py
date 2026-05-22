import numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
from pathlib import Path

# --- НАСТРОЙКА ПУТЕЙ ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

st.set_page_config(page_title="Разведочный анализ", layout="wide")

# Глобальные стили Arial 15/22
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: Arial, sans-serif !important; font-size: 15px !important; }
    h1 { font-size: 22px !important; font-weight: bold !important; }
</style>
""", unsafe_allow_html=True)


# --- КЕШИРОВАНИЕ ЗАГРУЗКИ И ОБРАБОТКИ ---
@st.cache_data(show_spinner="Подготовка данных для анализа...")
def load_and_prepare_eda():
    # 1. Загрузка
    path = r"dq_monitor\data\raw\events_dirty.csv"
    try:
        df = pd.read_csv(path)
    except:
        df = pd.read_csv("data/raw/events_dirty.csv")

    # 2. Подготовка для гистограммы сумм
    amounts = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
    amounts = amounts[amounts > 0]
    bins = [0, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 2000000, 5000000, 10000000, 20000000, np.inf]
    labels = ["0-1k", "1k-5k", "5k-10k", "10k-50k", "50k-100k", "100k-500k", "500k-1M", "1M-2M", "2M-5M", "5M-10M",
              "10M-20M", "20M+"]
    binned = pd.cut(amounts, bins=bins, labels=labels, ordered=True)

    # 3. Подготовка для часового графика
    df_ts = df.copy()
    df_ts["event_ts_parsed"] = pd.to_datetime(df_ts["event_ts"], errors="coerce")
    hourly = df_ts["event_ts_parsed"].dt.hour.value_counts().sort_index().reset_index()
    hourly.columns = ["hour", "event_count"]

    # 4. Подготовка для категорий (Склеивание цифр и текста)
    mcc_mapping = {
        "5411": "grocery", "5812": "restaurant", "5541": "gas_station",
        "4111": "transport", "5732": "electronics", "5651": "clothing",
        "5969": "online_shopping", "7832": "entertainment", "8011": "healthcare",
        "8220": "education", "4900": "utilities", "6011": "atm_withdrawal",
        "6051": "crypto_exchange", "7995": "gambling", "4829": "wire_transfer_abroad",
    }
    df_mcc = df.copy()
    df_mcc['merchant_category'] = df_mcc['merchant_category'].astype(str).str.strip()
    df_mcc['is_error'] = df_mcc['merchant_category'].isin(mcc_mapping.keys())
    df_mcc['merchant_category'] = df_mcc['merchant_category'].replace(mcc_mapping)

    bad_labels = ['nan', '<na>', 'none', 'nat', '']
    df_mcc = df_mcc[~df_mcc['merchant_category'].str.lower().isin(bad_labels)]

    agg_mcc = df_mcc.groupby('merchant_category').agg(
        total=('is_error', 'count'),
        errors=('is_error', 'sum')
    ).reset_index()
    agg_mcc['correct'] = agg_mcc['total'] - agg_mcc['errors']
    agg_mcc = agg_mcc.sort_values('total', ascending=True).tail(15)

    return df, binned, labels, hourly, agg_mcc


df, binned, amount_labels, hourly, agg_mcc = load_and_prepare_eda()
st.session_state["df_dirty"] = df

st.title("🔍 Разведочный анализ данных (Exploration)")

# --- ГРАФИК 1: СУММЫ (Исправлена ось Y) ---
fig1 = px.histogram(
    x=binned,
    category_orders={"x": amount_labels},
    labels={"x": "Сумма транзакции, ₽", "y": "Количество"}
)

fig1.update_layout(
    title='Зависимость суммы и количества транзакций',
    font=dict(family="Arial", size=15),
    title_font=dict(size=22),
    bargap=0.1, height=500
)

fig1.update_yaxes(
    type="log",
    title="Количество",
    tickvals=[10, 100, 1000, 10000, 100000],
    ticktext=["10", "100", "1k", "10k", "100k"],
    gridcolor='lightgrey'
)
st.plotly_chart(fig1, use_container_width=True)

# --- ГРАФИК 2: ЧАСЫ ---
hourly["Период"] = hourly["hour"].apply(lambda x: "Ночь (Риск фрода)" if x < 6 else "Обычное время")
fig2 = px.bar(
    hourly, x="hour", y="event_count", color="Период",
    color_discrete_map={"Ночь (Риск фрода)": "#ff4b4b", "Обычное время": "#1f77b4"},
    labels={"hour": "Часы", "event_count": "Количество событий"}
)
fig2.update_layout(
    title='Распределение транзакций относительно времени суток',
    font=dict(family="Arial", size=15),
    title_font=dict(size=22),
    yaxis_title="Количество событий"
)
fig2.update_xaxes(tickmode='linear', dtick=1)
st.plotly_chart(fig2, use_container_width=True)

# --- ГРАФИК 3: КАТЕГОРИИ (Склеенные) ---
fig3 = go.Figure()
fig3.add_trace(go.Bar(y=agg_mcc['merchant_category'], x=agg_mcc['correct'], name='Текст (Верно)', orientation='h',
                      marker_color='#1f77b4'))
fig3.add_trace(
    go.Bar(y=agg_mcc['merchant_category'], x=agg_mcc['errors'], name='Цифры (Ошибка кодировки)', orientation='h',
           marker_color='#d62728'))

fig3.update_layout(
    barmode='stack', title='Топ-15 категорий: ошибки формата записи',
    font=dict(family="Arial", size=15), title_font=dict(size=22),
    xaxis_title="Количество транзакций", yaxis_title="Категория",
    legend=dict(title='Формат записи', font=dict(size=14)),
    height=600, margin=dict(l=150)
)
st.plotly_chart(fig3, use_container_width=True)

# --- ГРАФИК 4: КРУГОВАЯ ---
events_by_type = df["event_type"].value_counts()
fig4 = px.pie(values=events_by_type.values, names=events_by_type.index,
              color_discrete_sequence=['#1f77b4', '#10B981'], hole=0.6)
fig4.update_layout(title='Структура пользовательских действий',
                   font=dict(family="Arial", size=15), title_font=dict(size=22))
st.plotly_chart(fig4, use_container_width=True)