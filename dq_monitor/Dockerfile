FROM python:3.11-slim

WORKDIR /app

# Сначала зависимости — слой кешируется, пока requirements.txt не меняется
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Потом код
COPY src/ ./src/
COPY app/ ./app/

# Streamlit по умолчанию на 8501
EXPOSE 8501

# --server.address=0.0.0.0 чтобы быть доступным извне контейнера
CMD ["streamlit", "run", "app/streamlit_app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
