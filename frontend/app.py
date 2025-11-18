import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

st.set_page_config(
    page_title="MediaMeter",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============ Config ============

# FIXED FOR LOCAL DEVELOPMENT - Use localhost:8000
API_BASE_URL = "http://127.0.0.1:8000"
API_KEY = "dev_key_change_in_prod"

HEADERS = {
    "X-MM-Key": API_KEY,
    "Content-Type": "application/json",
}

PERIODS = {
    "Сегодня": "today",
    "Последние 24ч": "last_24h",
    "Последние 3ч": "last_3h",
    "Последние 7 дней": "last_7",
    "Последние 14 дней": "last_14",
    "Последние 30 дней": "last_30",
    "Последние 90 дней": "last_90",
    "Квартал": "qtd",
    "Год": "ytd",
    "За всё время": "all_time",
}

# ============ Sidebar ============

st.sidebar.title("📊 MediaMeter")
st.sidebar.markdown("---")

# Выбор персоны
try:
    response = requests.get(f"{API_BASE_URL}/v1/persons", timeout=10)
    if response.status_code == 200:
        persons = response.json()
        if persons:
            person_options = {p["name"]: p["id"] for p in persons}
            selected_person_name = st.sidebar.selectbox("Выбрать персону", list(person_options.keys()))
            selected_person_id = person_options[selected_person_name]
        else:
            st.sidebar.error("❌ Нет персон в БД")
            st.stop()
    else:
        st.sidebar.error(f"❌ Ошибка API: {response.status_code}")
        st.stop()
except Exception as e:
    st.sidebar.error(f"❌ Ошибка подключения: {str(e)}")
    st.stop()

# Выбор периода
selected_period_name = st.sidebar.selectbox("Период", list(PERIODS.keys()))
selected_period = PERIODS[selected_period_name]

st.sidebar.markdown("---")
st.sidebar.markdown("### Навигация")
page = st.sidebar.radio("Перейти к", ["Обзор", "Анализ", "Данные"])

# ============ Main Content ============

st.title(f"📰 {selected_person_name}")
st.markdown(f"**Период:** {selected_period_name}")

# Fetch metrics - WITH DEBUG INFO
@st.cache_data(ttl=300)
def fetch_metrics(person_id, period):
    try:
        print(f"\n[DEBUG] Fetching metrics...")
        print(f"  Person ID: {person_id}")
        print(f"  Period: {period}")
        print(f"  URL: {API_BASE_URL}/v1/metrics/{person_id}")
        print(f"  Headers: {HEADERS}")
        
        response = requests.get(
            f"{API_BASE_URL}/v1/metrics/{person_id}",
            params={"period": period},
            headers=HEADERS,
            timeout=10,
        )
        
        print(f"  Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Success! Data keys: {data.keys()}")
            return data
        else:
            error_text = response.text if response.text else "No error message"
            print(f"  ❌ Error: {response.status_code}")
            print(f"  Response: {error_text}")
            return None
    except Exception as e:
        print(f"  ❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

metrics = fetch_metrics(selected_person_id, selected_period)

if metrics is None:
    st.error("""
    ❌ **Не удалось загрузить метрики!**
    
    **Что проверить:**
    1. ✅ Backend запущен? Должно быть окно с текстом "Uvicorn running on http://0.0.0.0:8000"
    2. ✅ Две Command Prompt окна открыты? (Backend + Streamlit)
    3. ✅ Нет ошибок в окне Backend?
    
    **Debug информация:**
    - API URL: `{API_BASE_URL}/v1/metrics/{selected_person_id}`
    - Person ID: `{selected_person_id}`
    - Period: `{selected_period}`
    - API Key: `{API_KEY}`
    
    **Что делать:**
    1. Посмотри на окно Backend - там должны быть новые логи
    2. Скопируй все ошибки из Backend окна
    3. Дай мне скриншот окна Backend
    """)
    st.stop()

# ============ PAGE: Overview ============

if page == "Обзор":
    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Упоминания",
            metrics["mentions"]["total"],
            delta=metrics["mentions"]["focus"],
            help="Всего / В фокусе",
        )
    
    with col2:
        st.metric(
            "Уникальные источники",
            metrics["reach"]["unique_sources"],
            help="Кол-во уникальных источников",
        )
    
    with col3:
        st.metric(
            "Охват (Views)",
            f"{metrics['reach']['total_reach']:,}",
            help="Общий охват упоминаний",
        )
    
    with col4:
        sentiment = metrics["sentiment"]
        net_sentiment = sentiment["net_sentiment"]
        color = "🟢" if net_sentiment > 0 else "🔴" if net_sentiment < 0 else "⚪"
        st.metric(
            "Net Sentiment",
            f"{net_sentiment:+.2f}",
            help=f"Позитив: {sentiment['pos_share']:.0%} | Негатив: {sentiment['neg_share']:.0%}",
        )
    
    st.markdown("---")
    
    # Sentiment Distribution
    col1, col2 = st.columns(2)
    
    with col1:
        sentiment_data = metrics["sentiment"]
        sentiment_df = pd.DataFrame({
            "Тональность": ["Позитив", "Негатив", "Нейтраль"],
            "Количество": [
                sentiment_data["positive"],
                sentiment_data["negative"],
                sentiment_data["neutral"],
            ],
        })
        
        fig = px.pie(
            sentiment_df,
            values="Количество",
            names="Тональность",
            color_discrete_map={"Позитив": "#22c55e", "Негатив": "#ef4444", "Нейтраль": "#94a3b8"},
            title="Распределение тональности",
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Velocity
        velocity = metrics["velocity"]
        speed_data = {
            "Метрика": ["Скорость/час", "Ускорение"],
            "Значение": [velocity["velocity_per_hour"], velocity["acceleration"]],
        }
        speed_df = pd.DataFrame(speed_data)
        
        fig = go.Figure(data=[
            go.Bar(
                x=speed_df["Метрика"],
                y=speed_df["Значение"],
                marker_color=["#3b82f6", "#f59e0b"],
            )
        ])
        fig.update_layout(title="Скорость и ускорение", height=300)
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Top Sources
    col1, col2 = st.columns(2)
    
    with col1:
        top_sources = metrics["top_sources"]
        if top_sources:
            sources_df = pd.DataFrame(top_sources)
            st.subheader("🔝 Топ источники")
            st.dataframe(sources_df[["source_title", "mentions", "views"]], use_container_width=True)
        else:
            st.info("📊 Нет данных об источниках")
    
    with col2:
        top_topics = metrics["top_topics"]
        if top_topics:
            topics_df = pd.DataFrame(top_topics)
            st.subheader("🏷️ Топ темы")
            st.dataframe(topics_df, use_container_width=True)
        else:
            st.info("📊 Нет данных о темах")


# ============ PAGE: Analysis ============

elif page == "Анализ":
    st.subheader("🤖 Аналитика с ChatGPT")
    st.markdown("Получайте автоматические insights и ответы на вопросы")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("📊 Анализ тональности"):
            with st.spinner("Анализирую..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/v1/analysis/sentiment/{selected_person_id}",
                        params={"period": selected_period},
                        headers=HEADERS,
                    )
                    if response.status_code == 200:
                        analysis = response.json()
                        st.success("✅ Анализ готов")
                        st.markdown(analysis.get("analysis", "Нет анализа"))
                    else:
                        st.error(f"❌ Ошибка анализа: {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Ошибка: {str(e)}")
    
    with col2:
        if st.button("📈 Анализ всплесков"):
            with st.spinner("Анализирую..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/v1/analysis/spikes/{selected_person_id}",
                        params={"period": selected_period},
                        headers=HEADERS,
                    )
                    if response.status_code == 200:
                        analysis = response.json()
                        st.success("✅ Анализ готов")
                        st.markdown(analysis.get("analysis", "Нет анализа"))
                    else:
                        st.error(f"❌ Ошибка анализа: {response.status_code}")
                except Exception as e:
                    st.error(f"❌ Ошибка: {str(e)}")
    
    st.markdown("---")
    
    st.subheader("❓ Задай вопрос")
    question = st.text_area("Введи свой вопрос об аналитике:")
    
    if st.button("Получить ответ"):
        if not question:
            st.warning("⚠️ Введи вопрос")
        else:
            with st.spinner("ChatGPT думает..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/v1/analysis",
                        json={
                            "question": question,
                            "person_id": selected_person_id,
                            "period": selected_period,
                        },
                        headers=HEADERS,
                    )
                    if response.status_code == 200:
                        result = response.json()
                        st.success("✅ Ответ готов")
                        st.markdown(result.get("answer", "Нет ответа"))
                    else:
                        st.error("❌ Ошибка запроса")
                except Exception as e:
                    st.error(f"❌ Ошибка: {str(e)}")


# ============ PAGE: Raw Data ============

elif page == "Данные":
    st.subheader("📋 Сырые данные")
    st.markdown("Таблица всех упоминаний для персоны")
    
    # Placeholder для таблицы
    placeholder_data = {
        "Дата": [datetime.now() - timedelta(days=i) for i in range(5)],
        "Источник": ["Telegram", "News", "Social", "Blog", "Twitter"],
        "Заголовок": ["Новость 1", "Новость 2", "Новость 3", "Новость 4", "Новость 5"],
        "Тональность": ["Позитив", "Негатив", "Нейтраль", "Позитив", "Негатив"],
        "Views": [1000, 2500, 500, 3000, 1200],
    }
    st.dataframe(pd.DataFrame(placeholder_data), use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**v1.0.0** | Made with ❤️")
