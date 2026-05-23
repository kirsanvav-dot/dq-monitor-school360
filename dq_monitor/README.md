# DQ Monitor
## Цель проекта:

**Проверить гипотезу о влиянии чистоты данных на срабатывание base-rule антифрод системы.
Она разбивается на несколько подзадач:**

### Задачи, решаемые в проекте:

**1. Аудит качества данных и выявление проблем**
**2. Создание методов отчистки данных**
**3. Разработка движка антифрод системы** 
**4. Оценка работы антифрода на данных до и после очистки**
**5. Подготовка конкретных Бизнес-рекомендаций для дата-инженеров**



## Быстрый старт

### 0. Получение репозитория

```bash
git clone https://github.com/kirsanvav-dot/dq-monitor-school360.git
cd dq-monitor-school360
```

### 1. установить Python-зависимости, venv

Для полноценного запуска см. пункт 4 (в этом случае пункты 1-3 необязательны)
Необходимо иметь Python 3.11 (на других версиях совместимость не гарантируется) и настроить virtual environment 
(виртуальное окружение)

Создание venv:
```bash
python -m venv .venv
```

Включение venv:
**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```
Windows (PowerShell):
```PowerShell

.venv\Scripts\Activate.ps1
```

Windows (Git Bash), macOS, Linux:
```bash

source .venv/Scripts/activate   # Windows + Git Bash
source .venv/bin/activate       # macOS / Linux
```

дальнейшая работа происходит в активированном виртуальном окружении

Переход в рабочую дирректорию
```bash
cd dq_monitor
```

Установка зависимостей:

```bash
pip install -r requirements.txt
```

### 2. Убедиться, что готовые модули работают

```bash
pytest tests/
# Должно быть: 137 passed
```

### 3. Запустить приложение

```bash
streamlit run app/streamlit_app.py
# Открыть http://localhost:8501
```

### 4. Запустить через Docker

#### 4.1 Установка Docker

##### Windows / macOS

1. Скачать **Docker Desktop** с [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
2. Установить с настройками по умолчанию
3. После установки запустить Docker Desktop из приложений
4. В правом нижнем углу (Windows) или в строке меню (Mac) появится иконка
   с китом. Когда она перестанет анимироваться — Docker готов
5. Открыть терминал (на Windows — PowerShell или git-bash) и проверить:
   ```
   docker --version
   ```
   Должно появиться что-то вроде `Docker version 26.1.4, build...`

⚠️ **Важно для Windows:** если Docker просит включить WSL 2 — соглашайтесь
и следуйте инструкции. Это бесплатно, безопасно и нужно для работы Docker
на Windows.

⚠️ **Важно для Mac:** Docker Desktop требует ~3 ГБ места и заметно ест RAM
(2-4 ГБ). На макбуках с 8 ГБ может быть тесновато — закройте Chrome и
тяжёлые приложения перед запуском.

##### Linux

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io
sudo usermod -aG docker $USER   # чтобы запускать без sudo
# Выйти из сессии и зайти обратно

docker --version
```

#### 4.2 Сборка и запуск

В корне проекта (там, где Dockerfile):

##### Шаг 1: собрать образ
```bash
docker build -t dq-monitor .
```

Первый раз сборка займёт 2–5 минут (скачивается базовый образ Python и
ставятся библиотеки). Последующие сборки — 5–10 секунд, если меняли
только код.

В конце увидите что-то вроде `Successfully tagged dq-monitor:latest`.

##### Шаг 2: запустить контейнер
```bash
docker run --rm -p 8501:8501 -v $(pwd)/data:/app/data dq-monitor
```

⚠️ **На Windows вместо `$(pwd)/data`** используйте `%cd%/data` (CMD) или
`${PWD}/data` (PowerShell), либо абсолютный путь.

Streamlit запустится. Откройте в браузере **http://localhost:8501** — должно
открыться то же приложение, что и при локальном запуске.

##### Шаг 3: остановить контейнер

В терминале, где запущен docker run, нажмите `Ctrl+C`. Контейнер
остановится и удалится (потому что был флаг `--rm`).

При возникновении проблем — см. `docs/DOCKER_FOR_BEGINNERS.md`,
там 15-минутный туториал.

## Взаимодействие с приложением

### Загрузка данных
Загрузка данных производится на главной странице, в формате .csv
Ожидаемый формат данных (без него не будет произведена нагрузка)

| номер колонки | название |
|---------------|----------|
| 1 | event_id |
| 2 | client_id |
| 3 | event_type |
| 4 | event_ts |
| 5 | device_type |
| 6 | ip_address |
| 7 | geo_country |
| 8 | geo_city |
| 9 | channel |
| 10 | amount_rub |
| 11 | currency |
| 12 | merchant_category |
| 13 | merchant_country |
| 14 | card_last4 |
| 15 | is_flagged |
| 16 | flag_reason |
| 17 | session_start_ts |
| 18 | session_end_ts |
| 19 | login_success |
| 20 | auth_method |

### Дальнейшае взаимодействие
