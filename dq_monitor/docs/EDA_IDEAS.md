# EDA Ideas — что построить на странице Exploration

Этот документ для **Frontend / Viz**. Идеи графиков, которые можно
сделать **сразу же в первый день**, не дожидаясь, пока остальные модули
будут готовы. Все они используют только сырой `events_dirty.csv`.

## Зачем это

EDA (Exploratory Data Analysis, разведочный анализ) — стандартная первая
фаза работы аналитика. Цель: посмотреть данные глазами, найти аномалии,
сформировать гипотезы. На защите страница с EDA — это **отдельный плюс**:
жюри видит, что команда не сразу побежала чистить, а сначала изучила,
что вообще пришло.

## Как организовать

Создайте новую страницу `app/pages/0_📈_Exploration.py` (нолик в начале,
чтобы появилась первой после главной). Используйте `from src.viz import ...`
для общих функций — но новые графики можно держать прямо в файле страницы,
если они специфичны для EDA.

Все идеи ниже работают на загруженном `st.session_state["df_dirty"]`.

## Идеи графиков

### 🟢 Базовые (день 1) — берите 3 из этого списка

**1. Распределение сумм транзакций (log scale)**
```python
import plotly.express as px
import pandas as pd

df = st.session_state["df_dirty"]
amounts = pd.to_numeric(df["amount_rub"], errors="coerce").dropna()
amounts = amounts[amounts > 0]  # отрицательные — это закладка, отдельно
fig = px.histogram(x=amounts, nbins=80, log_y=True,
                   labels={"x": "Сумма транзакции, ₽"})
st.plotly_chart(fig)
```
Что увидите: хвост распределения, типичная сумма транзакции, выбросы.
Можно вывести вторую гистограмму **только отрицательных** — это уже
видимая DQ-проблема.

**2. Активность по часам суток**
```python
df["event_ts_parsed"] = pd.to_datetime(df["event_ts"], errors="coerce")
hourly = df["event_ts_parsed"].dt.hour.value_counts().sort_index()
fig = px.bar(x=hourly.index, y=hourly.values,
             labels={"x": "Час дня", "y": "Число событий"})
st.plotly_chart(fig)
```
Покажет ночной провал и дневной пик. Особенный момент: ночные часы
(1-4) — это домашняя территория правила R2 «ночные крупные выводы».

**3. Топ-10 категорий мерчантов**
```python
top_categories = df["merchant_category"].value_counts(dropna=False).head(15)
fig = px.bar(x=top_categories.values, y=top_categories.index,
             orientation="h",
             labels={"x": "Транзакций", "y": "Категория"})
st.plotly_chart(fig)
```
Тут будет видна закладка #9: вперемешку с `grocery` появятся цифровые
коды типа `5411` — это и есть ISO-коды вместо текста.

**4. Доля транзакций vs сессий**
```python
events_by_type = df["event_type"].value_counts()
fig = px.pie(values=events_by_type.values, names=events_by_type.index)
st.plotly_chart(fig)
```
Простой пирог — показывает структуру данных. Хорошо смотрится рядом с
сводкой на главной странице.

### 🟡 Средней сложности (день 2)

**5. Тепловая карта «час × день недели»**
```python
df["hour"] = df["event_ts_parsed"].dt.hour
df["weekday"] = df["event_ts_parsed"].dt.day_name()
pivot = df.pivot_table(index="weekday", columns="hour",
                       values="event_id", aggfunc="count")
fig = px.imshow(pivot, aspect="auto")
st.plotly_chart(fig)
```
Сразу видно паттерны: будни vs выходные, утренние/вечерние пики.
Если есть «провал» в одну конкретную ночь — это закладка про аварию
в проде.

**6. Распределение топ-валют (включая аномалии)**
```python
currencies = df["currency"].value_counts(dropna=False).head(10)
# Помечаем валидные vs аномальные
valid = {"RUB", "USD", "EUR"}
colors = ["green" if c in valid else "red" for c in currencies.index]
fig = px.bar(x=currencies.index.astype(str), y=currencies.values,
             color=colors)
st.plotly_chart(fig)
```
**Это очень сильный график для защиты:** видно живьём, как качество
данных нарушается — `'rub'`, `'810'`, `'$'` будут красными.

**7. География транзакций**
```python
geo = df["geo_city"].value_counts(dropna=False).head(20)
fig = px.bar(x=geo.values, y=geo.index, orientation="h")
st.plotly_chart(fig)
```
Видно топ городов + NaN на видном месте (это закладка #6 — пропуски
в geo_city на 12%).

**8. Доля транзакций с is_flagged=True по часам**
```python
flagged_by_hour = df[df["event_type"] == "transaction"].groupby(
    df["event_ts_parsed"].dt.hour
)["is_flagged"].mean()
fig = px.bar(x=flagged_by_hour.index, y=flagged_by_hour.values,
             labels={"x": "Час", "y": "Доля флагованных"})
st.plotly_chart(fig)
```
Видно, в какое время старая система банка чаще «срабатывает».
Это **не правда о фроде**, но интересный контекст.

### 🔵 Продвинутые (день 3 или после возвращения)

**9. Скаттер: сумма vs время для подозрительных категорий**
```python
risky = df[df["merchant_category"].isin(
    ["crypto_exchange", "gambling", "wire_transfer_abroad"])]
risky_clean = risky.dropna(subset=["amount_rub", "event_ts_parsed"])
fig = px.scatter(risky_clean, x="event_ts_parsed", y="amount_rub",
                 color="merchant_category", log_y=True)
st.plotly_chart(fig)
```

**10. Когортный анализ клиентов**
Сгруппировать клиентов по числу транзакций, посмотреть распределение.
Видно, есть ли клиенты-«монстры» с тысячами транзакций — это могут
быть карусели.

**11. Sankey-диаграмма: канал → устройство → результат**
```python
# Сложнее в реализации, но впечатляюще выглядит на защите
import plotly.graph_objects as go
# ... используйте go.Sankey
```

## Что не делать

- **Не пытайтесь сделать все 11 графиков.** 3-5 хороших лучше 10 случайных.
- **Не дублируйте DQ Report.** Эта страница про данные «как есть»,
  не про найденные проблемы.
- **Не используйте matplotlib в Streamlit без нужды.** Plotly — интерактивный,
  пользователь может зумить, фильтровать, наводить мышь. Это сильнее
  смотрится на защите.

## Что показать на защите

При прогоне сценария на защите страница EDA не основная (главная сцена —
Antifraud Demo), но хороший момент **показать её перед DQ Report**:
«Сначала мы посмотрели, что вообще в данных. Уже здесь видны три
аномалии: ISO-коды в категориях, странные значения в валютах, дыра
в активности по конкретной дате. Подробный аудит — на следующей странице».

Этот flow создаёт ощущение **последовательной аналитической работы**,
а не «открыли и сразу всё чистим».

## Если совсем нет идей

Сделайте 3 первых графика из «Базовые» — этого достаточно. Лучше три
хорошо сделанных, чем семь сделанных кое-как.
