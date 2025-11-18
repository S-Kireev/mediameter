# 🚀 MediaMeter на Railway - Полная Инструкция

## ✅ ШАГ 1: Подготовка (5 минут)

### 1.1 Создай GitHub репозиторий

1. Перейди на https://github.com/new
2. Создай репозиторий `mediameter`
3. Склонируй его:

```bash
git clone https://github.com/YOUR_USERNAME/mediameter.git
cd mediameter
```

### 1.2 Подготовь файлы проекта

Структура проекта должна быть:

```
mediameter/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── config.py
│   └── services/
├── frontend/
│   ├── app.py
│   └── __init__.py
├── collectors/
│   ├── __init__.py
│   ├── rss_parser_v3.py
│   ├── telegram_bot_v2.py
│   ├── twitter_monitor_v2.py
│   └── collectors_utils_v2.py
├── requirements.txt
├── Dockerfile
├── railway.toml
├── .env.example
└── README.md
```

### 1.3 Скопируй файлы

```bash
# Скопируй всё из твоего проекта:
# - backend/ папку
# - frontend/ папку
# - requirements.txt
# - Dockerfile
# - railway.toml (создам ниже)

# Создай папку collectors
mkdir -p collectors
touch collectors/__init__.py
```

---

## ✅ ШАГ 2: Подготовь файлы для Railway

### 2.1 Создай railway.toml

Создай файл `railway.toml` в корне проекта:

```toml
[build]
builder = "dockerfile"
dockerfile = "./Dockerfile"

[deploy]
startCommand = "python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT"
restartPolicyCondition = "on-failure"
restartPolicyMaxRetries = 3
```

### 2.2 Создай .env.example

```bash
# Backend
DATABASE_URL=postgresql://user:password@localhost/mediameter
API_KEY=dev_key_change_in_prod
DEBUG=False

# RSS Collector
API_BASE_URL=http://localhost:8000
COLLECTION_INTERVAL=3600

# Telegram (пока закомментируй)
# TELEGRAM_API_ID=your_api_id
# TELEGRAM_API_HASH=your_api_hash
# TELEGRAM_BOT_TOKEN=your_bot_token

# Twitter (пока закомментируй)
# TWITTER_BEARER_TOKEN=your_bearer_token
```

### 2.3 Обнови requirements.txt

Используй файл который я создал выше (requirements.txt)

### 2.4 Обнови Dockerfile

Используй Dockerfile который я создал выше.

---

## ✅ ШАГ 3: Обнови collectors_utils.py

Замени старый файл на `collectors_utils_v2.py`:

```bash
cp collectors_utils_v2.py collectors/collectors_utils_v2.py
```

И в `rss_parser_v3.py` используется правильный импорт.

---

## ✅ ШАГ 4: Запушь в GitHub

```bash
git add .
git commit -m "Initial MediaMeter setup for Railway"
git push origin main
```

---

## ✅ ШАГ 5: Deploy на Railway

### 5.1 Зарегистрируйся на Railway

1. Перейди на https://railway.app
2. Нажми "Start a New Project"
3. Нажми "Deploy from GitHub repo"
4. Выбери свой репозиторий `mediameter`

### 5.2 Railway создаст PostgreSQL автоматически

Railway автоматически:
- ✅ Создаст PostgreSQL БД
- ✅ Установит переменные окружения
- ✅ Развернёт приложение
- ✅ Даст тебе URL

### 5.3 Проверь логи

В Railway → Project → Deployments → Logs

Должно быть:
```
✓ Application startup complete.
Uvicorn running on http://0.0.0.0:8000
```

---

## ✅ ШАГ 6: Протестируй Backend

Railway дал тебе URL, например: `https://mediameter-production.up.railway.app`

Открой в браузере:
```
https://mediameter-production.up.railway.app/docs
```

Должна загрузиться Swagger документация! ✅

---

## ✅ ШАГ 7: Добавь персон в БД

В Swagger UI → POST /v1/persons

```json
{
  "name": "Володимир Зеленський",
  "slug": "zelenskyy",
  "name_variants": ["Zelenskyy", "Zelensky"],
  "topics": ["politics", "ukraine"]
}
```

Нужно добавить несколько персон чтобы был что отслеживать!

---

## ✅ ШАГ 8: Запусти RSS Collector

### Вариант A: На Railway (рекомендую)

Создай отдельный сервис для RSS collector:

1. В Railway → Project → New Service → GitHub
2. Выбери снова свой репозиторий
3. Но в Build настройки установи:

```
Command: python collectors/rss_parser_v3.py
```

### Вариант B: Локально (для тестирования)

На своем ПК:

```bash
python collectors/rss_parser_v3.py
```

---

## ✅ ШАГ 9: Проверь Frontend

### Вариант A: Streamlit на Railway

Создай ещё один сервис:

```
Command: streamlit run frontend/app.py --server.port=$PORT --server.address=0.0.0.0
```

### Вариант B: Локально

```bash
streamlit run frontend/app.py
```

Открой http://localhost:8501

---

## 📊 ИТОГ: Архитектура на Railway

```
Railway Project
├── Backend Service (FastAPI)
│   └── PostgreSQL Database
├── Frontend Service (Streamlit) - опционально
└── Collector Service (RSS Parser) - опционально
```

Каждый сервис может быть включен/выключен независимо!

---

## 🔑 Переменные Окружения в Railway

Railway автоматически создаст:

- `DATABASE_URL` - для PostgreSQL
- `PORT` - для приложения

Ты добавляешь в Railway → Project Settings → Variables:

```
API_KEY=dev_key_change_in_prod
API_BASE_URL=https://твой-url.railway.app
COLLECTION_INTERVAL=3600
```

---

## 📱 Потом: Telegram Collector

Когда RSS будет работать, добавим Telegram:

1. Получишь API_ID и API_HASH от https://my.telegram.org
2. Добавишь в Railway Variables
3. Запустишь `telegram_bot_v2.py`

---

## 🐦 Потом: Twitter Collector

1. Получишь Bearer Token от https://developer.twitter.com
2. Добавишь в Railway Variables
3. Запустишь `twitter_monitor_v2.py`

---

## ✅ ПРОВЕРКА: Всё ли работает?

### Backend работает?
```
GET https://твой-url.railway.app/health
```
Должна быть: `{"status":"ok"}`

### RSS работает?
Запусти collector и смотри логи.

Должны быть статьи про твоих персон в БД.

### Фронтенд работает?
```
GET https://твой-streamlit-url.railway.app
```
Должен загрузиться дашборд!

---

## 🆘 Проблемы?

### Backend не загружается?
Смотри логи в Railway → Logs

Обычно ошибка с DATABASE_URL

### Collector не собирает данные?
Проверь что есть персоны в БД:
```
GET /v1/persons
```

### Frontend не подключается?
Обнови API_BASE_URL в frontend/app.py на реальный URL твоего backend на Railway

---

## 💰 Стоимость

Railway дарит **$5/месяц бесплатно**.

Обычно хватает для:
- ✅ Backend (0.5 вычисл. мощности)
- ✅ PostgreSQL (100MB памяти)
- ✅ 1 Collector (0.5 вычисл. мощности)

Если нужно больше - платишь ~$5 за доп. 100 RAM часов.

---

## 🎯 ПЛАН ДЕЙСТВИЙ:

1. ✅ Подготовь файлы локально
2. ✅ Запушь в GitHub
3. ✅ Deploy Backend на Railway (5 минут)
4. ✅ Добавь персон в БД (2 минуты)
5. ✅ Запусти RSS Collector на Railway (5 минут)
6. ✅ Запусти Streamlit Frontend (5 минут)
7. ✅ Проверь дашборд!

**Всего: ~30 минут!** 🚀
