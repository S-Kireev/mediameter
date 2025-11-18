FROM python:3.11-slim

WORKDIR /app

# Установить зависимости системы
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Скопировать requirements и установить Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скопировать весь проект
COPY . .

# Переменные окружения по умолчанию
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=postgresql://user:password@localhost/mediameter

# Команда по умолчанию - запуск Backend
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
