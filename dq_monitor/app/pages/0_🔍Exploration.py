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

# --- ПРОДВИНУТАЯ ТИПОГРАФИКА (ARIAL) ---
st.markdown("""
<style>
    html, body, [class*="css"], p, div, span, label, li {
        font-family: 'Arial', sans-serif !important;
        font-size: 15px !important;
        color: #334155;
    }
    h1 { font-size: 28px !important; font-weight: 700 !important; color: #0f172a !important; }
    h2 { font-size: 22px !important; font-weight: 600 !important; color: #1e293b !important; margin-top: 1.5rem !important; }
</style>
""", unsafe_allow_html=True)

GLOBAL_FONT = dict(family="Arial, sans-serif", size=14, color="#334155")

# --- КЕШИРОВАНИЕ ОБРАБОТКИ ---
@st.cache_data(show_spinner="Анализ данных...")
def get_eda_visual_data(df, mode):
    # 1. СУММЫ
    amounts_raw = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
    bins = [-np.inf, -10000, -1000, 0, 1000, 5000, 10000, 50000, 100000, 500000, 1000000, 2000000, 5000000, 10000000, 20000000, np.inf]
    labels_sum = ["<-10k (Аномалия)", "-10k до -1k (Аномалия)", "-1k до 0 (Аномалия)", "0-1k", "1k-5k", "5k-10k", "10k-50k", "50k-100k", "100k-500k", "500k-1M", "1M-2M", "2M-5M", "5M-10M", "10M-20M", "20M+"]
    binned_sums = pd.cut(amounts_raw, bins=bins, labels=labels_sum, ordered=True)
    sums_df = pd.DataFrame({'Сумма': binned_sums})
    sums_df['Тип'] = sums_df['Сумма'].apply(lambda x: "Аномалия" if "(Аномалия)" in str(x) else "Норма")
    amounts_agg = sums_df.groupby(['Сумма', 'Тип'], observed=False).size().reset_index(name='Количество')

    # 2. ЧАСЫ
    df_ts = pd.to_datetime(df["event_ts"], errors="coerce")
    hourly_counts = df_ts.dt.hour.value_counts().sort_index()
    hourly = pd.DataFrame({"hour": hourly_counts.index, "event_count": hourly_counts.values})

    # 3. КАТЕГОРИИ
    try:
        from src.reference_data import MCC_ISO_TO_TEXT
        mcc_mapping = MCC_ISO_TO_TEXT
    except:
        mcc_mapping = {"5411": "grocery", "5812": "restaurant", "4900": "utilities"}
    df_mcc = df[['merchant_category']].copy()
    df_mcc['merchant_category'] = df_mcc['merchant_category'].astype(str).str.strip()
    df_mcc['is_error'] = df_mcc['merchant_category'].isin(mcc_mapping.keys())
    df_mcc['display_name'] = df_mcc['merchant_category'].replace(mcc_mapping)
    bad_labels = ['nan', '<na>', 'none', 'nat', '']
    df_mcc = df_mcc[~df_mcc['display_name'].str.lower().isin(bad_labels)]
    agg_mcc = df_mcc.groupby('display_name').agg(total=('is_error', 'count'), errors=('is_error', 'sum')).reset_index()
    agg_mcc['correct'] = agg_mcc['total'] - agg_mcc['errors']
    agg_mcc = agg_mcc.sort_values('total').tail(15)

    # 4. КАРУСЕЛЬ
    tx_only = df[(df['event_type'] == 'transaction') & (df['client_id'].notna()) & (df['client_id'] != '')].copy()
    tx_only['ts'] = pd.to_datetime(tx_only['event_ts'], errors='coerce')
    tx_only = tx_only.dropna(subset=['ts'])
    tx_only['hour_of_day'] = tx_only['ts'].dt.hour
    tx_only['date_hour'] = tx_only['ts'].dt.floor('h')
    velocity = tx_only.groupby(['client_id', 'date_hour', 'hour_of_day']).size().reset_index(name='tx_count')
    v_bins, v_labels = [0, 1, 2, 5, 10, np.inf], ["1 тр/час", "2 тр/час", "3-5 тр/час", "6-10 тр/час", ">10 тр/час"]
    velocity['cohort'] = pd.cut(velocity['tx_count'], bins=v_bins, labels=v_labels)
    matrix = velocity.groupby(['hour_of_day', 'cohort'], observed=False).size().unstack(fill_value=0)
    for col in v_labels:
        if col not in matrix.columns: matrix[col] = 0
    matrix = matrix[v_labels]
    matrix.index = [f"{int(h):02d}:00" for h in matrix.index]

    # 5. ГОРОДА
    geo = df["geo_city"].replace(["", "nan", "None", "<NA>", "NaN"], np.nan).fillna("Данные отсутствуют")
    city_series = geo.value_counts().head(20)
    city_counts = pd.DataFrame({"Город": city_series.index, "Количество": city_series.values})
    city_counts["Тип"] = city_counts["Город"].apply(lambda x: "Ошибка DQ" if x == "Данные отсутствуют" else "Корректно")

    # 6. ВАЛЮТЫ И ТИПЫ
    event_counts = df["event_type"].value_counts()
    curr_series = df["currency"].value_counts(dropna=False).head(10)
    curr_counts = pd.DataFrame({"currency": curr_series.index, "count": curr_series.values})
    valid_list = {"RUB", "USD", "EUR"}
    curr_counts["Статус"] = curr_counts["currency"].apply(lambda x: "Валидная" if str(x).upper() in valid_list else "Аномалия")

    return amounts_agg, labels_sum, hourly, agg_mcc, matrix, city_counts, event_counts, curr_counts

# --- ИНТЕРФЕЙС ---
if "df_dirty" not in st.session_state:
    st.warning("Загрузите данные на главной странице.")
    st.stop()

st.title("🔍 Разведочный анализ данных (EDA)")

modes = ["Грязные данные (Dirty)"]
if "df_clean" in st.session_state: modes.append("Очищенные данные (Clean)")
selected_mode = st.radio("Режим данных:", modes, horizontal=True)
current_df = st.session_state["df_clean"] if "Clean" in selected_mode else st.session_state["df_dirty"]

amounts_agg, amt_labels, hourly, agg_mcc, carousel_matrix, city_data, event_types, curr_data = get_eda_visual_data(current_df, selected_mode)

# --- 1. ГРАФИК: СУММЫ ---
st.subheader("1. Анализ сумм транзакций (детализация аномалий)")
fig1 = px.bar(amounts_agg, x="Сумма", y="Количество", color="Тип",
             color_discrete_map={"Норма": "#1f77b4", "Аномалия": "#ef4444"},
             category_orders={"Сумма": amt_labels}, labels={"Сумма": "Диапазон суммы, ₽"})
fig1.update_layout(font=GLOBAL_FONT, bargap=0.1, height=450, showlegend=False)
fig1.update_yaxes(type="log", gridcolor='lightgrey', title="Количество", tickvals=[10, 100, 1000, 10000, 100000], ticktext=["10", "100", "1k", "10k", "100k"])
fig1.update_xaxes(tickangle=-30)
st.plotly_chart(fig1, use_container_width=True)

# --- 2. ГРАФИК: ЧАСЫ ---
st.subheader("2. Временная активность")
hourly["Период"] = hourly["hour"].apply(lambda x: "Ночь (Риск фрода)" if x < 6 else "Обычное время")
fig2 = px.bar(hourly, x="hour", y="event_count", color="Период",
              color_discrete_map={"Ночь (Риск фрода)": "#ff4b4b", "Обычное время": "#1f77b4"},
              labels={"hour": "Час суток", "event_count": "Число событий"})
fig2.update_layout(font=GLOBAL_FONT, height=400)
st.plotly_chart(fig2, use_container_width=True)

# --- 3. ГРАФИК: КАРУСЕЛЬ ---
st.subheader("3. Когортная матрица интенсивности (Поиск карусели)")
z_colors = np.log1p(carousel_matrix.values)
fig3 = go.Figure(data=go.Heatmap(z=z_colors, x=carousel_matrix.columns, y=carousel_matrix.index,
                                 text=carousel_matrix.values, texttemplate="%{text}",
                                 colorscale='YlOrRd', showscale=False))
fig3.update_layout(font=GLOBAL_FONT, height=550, yaxis={'autorange': "reversed"})
st.plotly_chart(fig3, use_container_width=True)

# --- 4. ГРАФИК: КАТЕГОРИИ ---
st.subheader("4. Анализ категорий (MCC)")
fig4 = go.Figure()
fig4.add_trace(go.Bar(y=agg_mcc['display_name'], x=agg_mcc['correct'], name='Текст (Верно)', orientation='h', marker_color='#1f77b4'))
fig4.add_trace(go.Bar(y=agg_mcc['display_name'], x=agg_mcc['errors'], name='Цифры (Ошибка)', orientation='h', marker_color='#ef4444'))
fig4.update_layout(barmode='stack', font=GLOBAL_FONT, height=550, xaxis_title="Кол-во транзакций")
st.plotly_chart(fig4, use_container_width=True)

# --- 5. ГРАФИК: ГОРОДА ---
st.subheader("5. Географическое распределение")
fig5 = px.bar(city_data, y="Город", x="Количество", color="Тип", orientation="h",
              color_discrete_map={"Корректно": "#1f77b4", "Ошибка DQ": "#ef4444"},
              labels={"Количество": "Число событий"})
fig5.update_layout(font=GLOBAL_FONT, height=550, yaxis={'categoryorder': 'total ascending'})
st.plotly_chart(fig5, use_container_width=True)

# --- 6. НИЖНЯЯ СЕТКА (ВАЛЮТЫ И ТИПЫ) ---
c_l, c_r = st.columns(2)
with c_l:
    st.subheader("6. Структура событий")
    fig6 = px.pie(values=event_types.values, names=event_types.index, color_discrete_sequence=['#1f77b4', '#34d399'], hole=0.6)
    fig6.update_layout(font=GLOBAL_FONT)
    st.plotly_chart(fig6, use_container_width=True)
with c_r:
    st.subheader("7. Используемые валюты")
    fig7 = px.bar(curr_data, x="currency", y="count", color="Статус",
                  color_discrete_map={"Валидная": "#0ea5e9", "Аномалия": "#ef4444"},
                  labels={"currency": "Валюта", "count": "Количество"})
    fig7.update_layout(font=GLOBAL_FONT)
    st.plotly_chart(fig7, use_container_width=True)

if "Clean" in selected_mode and agg_mcc['errors'].sum() > 0:
    st.warning(f"💡 В очищенных данных осталось {int(agg_mcc['errors'].sum())} цифровых кодов.")