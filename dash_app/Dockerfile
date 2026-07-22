FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-dash.txt .
RUN pip install --no-cache-dir -r requirements-dash.txt

# Общие модули (те же что у Streamlit и api)
COPY checklist.py db.py storage.py ./
COPY dash_app/ ./dash_app/

EXPOSE 8050

# $PORT подставляет Railway; sh -c обязателен для expansion переменной
CMD ["sh", "-c", "gunicorn dash_app.app:server --bind 0.0.0.0:$PORT --workers 2"]
