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


# --- КЕШИРОВАНИЕ ОБРАБОТКИ ---
@st.cache_data(show_spinner="Анализ данных для графиков...")
def get_eda_visual_data(df, mode):
    # 1. Суммы (Гистограмма)
    amounts = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
    amounts = amounts[amounts > 0]
    bins = [0, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 2000000, 5000000, 10000000, 20000000, np.inf]
    labels = ["0-1k", "1k-5k", "5k-10k", "10k-50k", "50k-100k", "100k-500k", "500k-1M", "1M-2M", "2M-5M", "5M-10M",
              "10M-20M", "20M+"]
    binned = pd.cut(amounts, bins=bins, labels=labels, ordered=True)

    # 2. Часы (Столбчатая)
    df_ts = pd.to_datetime(df["event_ts"], errors="coerce")
    hourly = df_ts.dt.hour.value_counts().sort_index().reset_index()
    hourly.columns = ["hour", "event_count"]

    # 3. Категории (Склеенные)
    try:
        from src.reference_data import MCC_ISO_TO_TEXT
        mcc_mapping = MCC_ISO_TO_TEXT
    except:
        mcc_mapping = {"5411": "grocery", "5812": "restaurant", "4900": "utilities"}

    df_mcc = df[['merchant_category']].copy()
    df_mcc['merchant_category'] = df_mcc['merchant_category'].astype(str).str.strip()
    df_mcc['is_error'] = df_mcc['merchant_category'].isin(mcc_mapping.keys())
    df_mcc['display_name'] = df_mcc['merchant_category'].replace(mcc_mapping)

    # Фильтр мусора и NA
    bad = ['nan', '<na>', 'none', 'nat', '']
    df_mcc = df_mcc[~df_mcc['display_name'].str.lower().isin(bad)]

    agg = df_mcc.groupby('display_name').agg(
        total=('is_error', 'count'),
        errors=('is_error', 'sum')
    ).reset_index()
    agg['correct'] = agg['total'] - agg['errors']
    agg = agg.sort_values('total').tail(15)

    # 4. Типы событий (Круговая)
    event_counts = df["event_type"].value_counts()

    return binned, labels, hourly, agg, event_counts


# --- ИНТЕРФЕЙС ---
if "df_dirty" not in st.session_state:
    st.warning("Загрузите данные на главной странице.")
    st.stop()

st.title("🔍 Разведочный анализ (EDA)")

# Переключатель Dirty/Clean
data_modes = ["Грязные данные (Dirty)"]
if "df_clean" in st.session_state:
    data_modes.append("Очищенные данные (Clean)")

selected_mode = st.radio("Просмотр данных в режиме:", data_modes, horizontal=True)
current_df = st.session_state["df_clean"] if "Clean" in selected_mode else st.session_state["df_dirty"]

# Получение данных из кеша
binned, amt_labels, hourly, agg_mcc, event_types = get_eda_visual_data(current_df, selected_mode)

# --- 1. ГРАФИК: СУММЫ ---
fig1 = px.histogram(x=binned, category_orders={"x": amt_labels},
                    labels={"x": "Сумма транзакции, ₽", "y": "Количество"})
fig1.update_layout(title="Зависимость суммы и количества транзакций",
                   font=dict(family="Arial", size=15), title_font=dict(size=22), bargap=0.1)
fig1.update_yaxes(type="log", gridcolor='lightgrey', title="Количество",
                  tickvals=[10, 100, 1000, 10000, 100000], ticktext=["10", "100", "1k", "10k", "100k"])
st.plotly_chart(fig1, use_container_width=True)

# --- 2. ГРАФИК: ЧАСЫ ---
hourly["Период"] = hourly["hour"].apply(lambda x: "Ночь (Риск фрода)" if x < 6 else "Обычное время")
fig2 = px.bar(hourly, x="hour", y="event_count", color="Период",
              color_discrete_map={"Ночь (Риск фрода)": "#ff4b4b", "Обычное время": "#1f77b4"},
              labels={"hour": "Часы", "event_count": "Количество событий"})
fig2.update_layout(title="Распределение транзакций по времени суток",
                   font=dict(family="Arial", size=15), title_font=dict(size=22))
st.plotly_chart(fig2, use_container_width=True)

# --- 3. ГРАФИК: КАТЕГОРИИ ---
fig3 = go.Figure()
fig3.add_trace(go.Bar(y=agg_mcc['display_name'], x=agg_mcc['correct'],
                      name='Текст (Верно)', orientation='h', marker_color='#1f77b4'))
fig3.add_trace(go.Bar(y=agg_mcc['display_name'], x=agg_mcc['errors'],
                      name='Цифры (Ошибка)', orientation='h', marker_color='#d62728'))
fig3.update_layout(barmode='stack', title='Топ-15 категорий: ошибки формата записи',
                   font=dict(family="Arial", size=15), title_font=dict(size=22),
                   xaxis_title="Количество транзакций", height=600)
st.plotly_chart(fig3, use_container_width=True)

# --- 4. ГРАФИК: КРУГОВАЯ ДИАГРАММА ---
fig4 = px.pie(values=event_types.values, names=event_types.index,
              color_discrete_sequence=['#1f77b4', '#10B981'], hole=0.6)
fig4.update_layout(title='Структура пользовательских действий',
                   font=dict(family="Arial", size=15), title_font=dict(size=22))
fig4.update_traces(textfont_size=18, insidetextfont=dict(size=18))
st.plotly_chart(fig4, use_container_width=True)

# Уведомление об остаточных ошибках (только для Clean режима)
if "Clean" in selected_mode and agg_mcc['errors'].sum() > 0:
    st.warning(
        f"💡 В очищенных данных осталось {int(agg_mcc['errors'].sum())} цифровых кодов. Это категории, которых нет в справочнике Cleaner.")