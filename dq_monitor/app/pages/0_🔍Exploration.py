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


# --- КЕШИРОВАНИЕ ---
@st.cache_data(show_spinner="Анализ данных для графиков...")
def get_eda_visual_data(df, mode):
    # 1. Суммы
    amounts = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
    amounts = amounts[amounts > 0]
    bins = [0, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 2000000, 5000000, 10000000, 20000000, np.inf]
    labels = ["0-1k", "1k-5k", "5k-10k", "10k-50k", "50k-100k", "100k-500k", "500k-1M", "1M-2M", "2M-5M", "5M-10M",
              "10M-20M", "20M+"]
    binned = pd.cut(amounts, bins=bins, labels=labels, ordered=True)

    # 2. Часы
    df_ts = pd.to_datetime(df["event_ts"], errors="coerce")
    hourly_counts = df_ts.dt.hour.value_counts().sort_index()
    hourly = pd.DataFrame({"hour": hourly_counts.index, "event_count": hourly_counts.values})

    # 3. Категории
    try:
        from src.reference_data import MCC_ISO_TO_TEXT
        mcc_mapping = MCC_ISO_TO_TEXT
    except:
        mcc_mapping = {"5411": "grocery", "5812": "restaurant", "4900": "utilities"}

    df_mcc = df[['merchant_category']].copy()
    df_mcc['merchant_category'] = df_mcc['merchant_category'].astype(str).str.strip()
    df_mcc['is_error'] = df_mcc['merchant_category'].isin(mcc_mapping.keys())
    df_mcc['display_name'] = df_mcc['merchant_category'].replace(mcc_mapping)
    bad = ['nan', '<na>', 'none', 'nat', '']
    df_mcc = df_mcc[~df_mcc['display_name'].str.lower().isin(bad)]

    agg = df_mcc.groupby('display_name').agg(total=('is_error', 'count'), errors=('is_error', 'sum')).reset_index()
    agg['correct'] = agg['total'] - agg['errors']
    agg = agg.sort_values('total').tail(15)

    # 4. Валюты
    curr_series = df["currency"].value_counts(dropna=False).head(10)
    curr_counts = pd.DataFrame({"currency": curr_series.index, "count": curr_series.values})
    valid_list = {"RUB", "USD", "EUR"}
    curr_counts["Статус"] = curr_counts["currency"].apply(
        lambda x: "Валидная" if str(x).upper() in valid_list else "Аномалия")

    # 5. ГОРОДА
    geo = df["geo_city"].replace(["", "nan", "None", "<NA>", "NaN"], np.nan).fillna("Данные отсутствуют")
    city_series = geo.value_counts().head(20)
    city_counts = pd.DataFrame({"Город": city_series.index, "Количество событий": city_series.values})
    city_counts["Тип"] = city_counts["Город"].apply(lambda x: "Ошибка DQ" if x == "Данные отсутствуют" else "Корректно")

    # 6. Типы событий
    event_counts = df["event_type"].value_counts()

    # --- 7. КОГОРТНАЯ МАТРИЦА (КАРУСЕЛЬ) ---
    tx_only = df[(df['event_type'] == 'transaction') & (df['client_id'].notna()) & (df['client_id'] != '')].copy()
    tx_only['ts'] = pd.to_datetime(tx_only['event_ts'], errors='coerce')
    tx_only = tx_only.dropna(subset=['ts'])

    # Выделяем час для группировки
    tx_only['date_hour'] = tx_only['ts'].dt.floor('h')  # Группируем по конкретному часу конкретного дня
    tx_only['hour_of_day'] = tx_only['ts'].dt.hour

    # Считаем, сколько транзакций сделал клиент за 1 час
    velocity = tx_only.groupby(['client_id', 'date_hour', 'hour_of_day']).size().reset_index(name='tx_count')

    # Разбиваем на когорты интенсивности
    v_bins = [0, 1, 2, 5, 10, np.inf]
    v_labels = ["1 тр/час", "2 тр/час", "3-5 тр/час", "6-10 тр/час (Риск)", ">10 тр/час (Карусель)"]
    velocity['cohort'] = pd.cut(velocity['tx_count'], bins=v_bins, labels=v_labels)

    # Сводим в матрицу: Часы (Y) на Когорты (X)
    matrix = velocity.groupby(['hour_of_day', 'cohort'], observed=False).size().unstack(fill_value=0)

    # Гарантируем порядок колонок
    for col in v_labels:
        if col not in matrix.columns:
            matrix[col] = 0
    matrix = matrix[v_labels]

    # Форматируем индексы часов для красоты оси Y
    matrix.index = [f"{int(h):02d}:00" for h in matrix.index]

    return binned, labels, hourly, agg, curr_counts, city_counts, event_counts, matrix


# --- ИНТЕРФЕЙС ---
if "df_dirty" not in st.session_state:
    st.warning("Загрузите данные на главной странице.")
    st.stop()

st.title("🔍 Разведочный анализ (EDA)")

data_modes = ["Грязные данные (Dirty)"]
if "df_clean" in st.session_state:
    data_modes.append("Очищенные данные (Clean)")

selected_mode = st.radio("Просмотр данных в режиме:", data_modes, horizontal=True)
current_df = st.session_state["df_clean"] if "Clean" in selected_mode else st.session_state["df_dirty"]

binned, amt_labels, hourly, agg_mcc, curr_data, city_data, event_types, carousel_matrix = get_eda_visual_data(
    current_df, selected_mode)

# --- 1. СУММЫ ---
fig1 = px.histogram(x=binned, category_orders={"x": amt_labels}, labels={"x": "Сумма транзакции, ₽", "y": "Количество"})
fig1.update_layout(title="Зависимость суммы и количества транзакций", font=dict(family="Arial", size=15),
                   title_font=dict(size=22), bargap=0.1)
fig1.update_yaxes(type="log", gridcolor='lightgrey', title="Количество", tickvals=[10, 100, 1000, 10000, 100000],
                  ticktext=["10", "100", "1k", "10k", "100k"])
st.plotly_chart(fig1, use_container_width=True)

# --- 2. ЧАСЫ ---
hourly["Период"] = hourly["hour"].apply(lambda x: "Ночь (Риск фрода)" if x < 6 else "Обычное время")
fig2 = px.bar(hourly, x="hour", y="event_count", color="Период",
              color_discrete_map={"Ночь (Риск фрода)": "#ff4b4b", "Обычное время": "#1f77b4"},
              labels={"hour": "Часы", "event_count": "Количество событий"})
fig2.update_layout(title="Распределение транзакций по времени суток", font=dict(family="Arial", size=15),
                   title_font=dict(size=22))
st.plotly_chart(fig2, use_container_width=True)

# --- 3. КОГОРТНАЯ МАТРИЦА (КАРУСЕЛЬ) ---
st.markdown("<br>", unsafe_allow_html=True)

# Используем логарифм для цветов (чтобы подсветить даже 5 каруселей на фоне 100 000 обычных),
# но выводим точный текст
z_colors = np.log1p(carousel_matrix.values)

fig7 = go.Figure(data=go.Heatmap(
    z=z_colors,
    x=carousel_matrix.columns,
    y=carousel_matrix.index,
    text=carousel_matrix.values,
    texttemplate="%{text}",
    colorscale='YlOrRd',  # Цветовая схема: Желтый -> Оранжевый -> Красный
    showscale=False  # Убираем шкалу, так как цвет логарифмический и запутает зрителя
))

fig7.update_layout(
    title="Когортная матрица интенсивности (Паттерн «Карусель»)",
    font=dict(family="Arial", size=15),
    title_font=dict(size=22),
    xaxis_title="Интенсивность (транзакций у 1 клиента за 1 час)",
    yaxis_title="Время суток",
    height=600,
    margin=dict(t=60, b=40)
)
# Переворачиваем ось Y, чтобы 00:00 было сверху
fig7.update_yaxes(autorange="reversed")

st.plotly_chart(fig7, use_container_width=True)

# --- 4. КАТЕГОРИИ ---
fig3 = go.Figure()
fig3.add_trace(go.Bar(y=agg_mcc['display_name'], x=agg_mcc['correct'], name='Текст (Верно)', orientation='h',
                      marker_color='#1f77b4'))
fig3.add_trace(go.Bar(y=agg_mcc['display_name'], x=agg_mcc['errors'], name='Цифры (Ошибка)', orientation='h',
                      marker_color='#d62728'))
fig3.update_layout(barmode='stack', title='Топ-15 категорий: ошибки формата записи', font=dict(family="Arial", size=15),
                   title_font=dict(size=22), xaxis_title="Количество транзакций", height=600)
st.plotly_chart(fig3, use_container_width=True)

# --- 5. ГОРОДА ---
st.markdown("<br>", unsafe_allow_html=True)
fig6 = px.bar(city_data, y="Город", x="Количество событий", color="Тип", orientation="h",
              color_discrete_map={"Корректно": "#1f77b4", "Ошибка DQ": "#ef4444"},
              title="Топ-20 городов (подсветка пропусков данных)")
fig6.update_layout(font=dict(family="Arial", size=15), title_font=dict(size=22), height=600,
                   yaxis={'categoryorder': 'total ascending'}, legend_title_text="Тип",
                   xaxis_title="Количество событий", yaxis_title=None)
st.plotly_chart(fig6, use_container_width=True)

# --- НИЖНЯЯ СЕТКА ---
col_left, col_right = st.columns(2)
with col_left:
    fig4 = px.pie(values=event_types.values, names=event_types.index, color_discrete_sequence=['#1f77b4', '#34d399'],
                  hole=0.6)
    fig4.update_layout(title='Структура действий', font=dict(family="Arial", size=15), title_font=dict(size=22))
    fig4.update_traces(textfont_size=16, insidetextfont=dict(size=16))
    st.plotly_chart(fig4, use_container_width=True)

with col_right:
    fig5 = px.bar(curr_data, x="currency", y="count", color="Статус",
                  color_discrete_map={"Валидная": "#0ea5e9", "Аномалия": "#ef4444"},
                  labels={"currency": "Валюта", "count": "Количество", "Статус": "Тип"},
                  title="Анализ используемых валют")
    fig5.update_layout(font=dict(family="Arial", size=15), title_font=dict(size=22))
    st.plotly_chart(fig5, use_container_width=True)

if "Clean" in selected_mode and agg_mcc['errors'].sum() > 0:
    st.warning(f"💡 В очищенных данных осталось {int(agg_mcc['errors'].sum())} цифровых кодов. Проверьте справочник.")