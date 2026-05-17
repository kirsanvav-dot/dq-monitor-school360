import numpy as np
import streamlit as st
import pandas as pd
import plotly.express as px

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
    bargap=0.1
)

fig.update_yaxes(
    type="log",
    tickvals=[100, 500, 1000, 5000, 10000, 50000],
    ticktext=["100", "500", "1k", "5k", "10k", "50k"]
)

st.plotly_chart(fig)
# Дальше ваш код (начиная со строки 18 на фото)
df["event_ts_parsed"] = pd.to_datetime(df["event_ts"], errors="coerce")

# Преобразуем Series в DataFrame для удобной работы с цветами в Plotly
hourly = df["event_ts_parsed"].dt.hour.value_counts().sort_index().reset_index()
hourly.columns = ["hour", "event_count"]

# Создаем колонку с условием: ночь (0-5 часов) или день
hourly["time_of_day"] = hourly["hour"].apply(lambda x: "Ночь (Риск фрода)" if x < 6 else "Обычное время")

# Строим график, используя DataFrame и группировку по цвету
fig = px.bar(
    hourly,
    x="hour",
    y="event_count",
    color="time_of_day", # Задаем цвет по нашей новой колонке
    color_discrete_map={
        "Ночь (Риск фрода)": "#ff4b4b", # Красный/коралловый для ночи (в стиле Streamlit)
        "Обычное время": "#1f77b4"      # Стандартный синий для дня
    },
    labels={
        "hour": "Часы",
        "event_count": "Число событий",
        "time_of_day": "Период"
    }
)

# Делаем так, чтобы отображался каждый час на оси X (от 0 до 23)
fig.update_xaxes(tickmode='linear', dtick=1)

st.plotly_chart(fig)




top_categories = df["merchant_category"].value_counts(dropna=False).head(15)

fig = px.bar(
    x=top_categories.values,
    y=top_categories.index,
    orientation="h",
    labels={"x": "Транзакции", "y": "Категория"}
)

# Жестко обрезаем ось X на 18k
fig.update_xaxes(range=[0, 18000])

st.plotly_chart(fig)



events_by_type = df["event_type"].value_counts()
soft_colors = ['#1f77b4', '#10B981']
fig = px.pie(values=events_by_type.values, names=events_by_type.index, color_discrete_sequence=soft_colors)
fig.update_layout(
    font=dict(family="Arial, sans-serif", size=20),
    legend=dict(
        font=dict(size=20)
    )
)

st.plotly_chart(fig)