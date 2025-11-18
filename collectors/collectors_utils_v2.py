"""
MediaMeter Collectors Utils v2
Обновлено для Railway + PostgreSQL
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import httpx
from datetime import datetime

# ============ DATABASE CONNECTION ============

# Получить DATABASE_URL из переменной окружения
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./mediameter.db"
)

# Для PostgreSQL нужно заменить postgres:// на postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Создать engine и SessionLocal
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ============ FUNCTIONS ============

def get_persons_from_db():
    """Загрузить активных персон из БД"""
    try:
        # Импортировать модели здесь чтобы избежать циклических зависимостей
        from backend.models import Person
        
        db = SessionLocal()
        try:
            persons = db.query(Person).filter(Person.active == True).all()
            person_names = [p.name for p in persons]
            
            if not person_names:
                print("⚠ Warning: No active persons in database!")
                return []
            
            print(f"✓ Loaded {len(person_names)} persons from database")
            return person_names
        finally:
            db.close()
    except Exception as e:
        print(f"❌ Error loading persons from DB: {e}")
        return []

async def send_to_api(mention_data, api_base_url, api_key):
    """Відправити упоминання на API"""
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                f"{api_base_url}/v1/ingest",
                json=mention_data,
                headers={
                    "X-MM-Key": api_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            
            if response.status_code == 200:
                result = response.json()
                return True, result.get('status', 'success')
            else:
                error_text = response.text if response.text else "Unknown error"
                return False, f"API Error {response.status_code}: {error_text}"
    except Exception as e:
        return False, str(e)

def extract_persons_from_text(text, persons_list):
    """Знайти персон у тексті"""
    if not text or not persons_list:
        return []
    
    found_persons = []
    text_lower = text.lower()
    
    for person in persons_list:
        person_lower = person.lower()
        if person_lower in text_lower:
            found_persons.append(person)
    
    return list(set(found_persons))

def analyze_sentiment(text):
    """Простий аналіз тональності (без зовнішніх бібліотек)"""
    if not text:
        return "neutral", 0.0
    
    positive_words = [
        "успіх", "успешно", "добре", "гарно", "вперед", "позитив", "молодець", 
        "браво", "отлично", "прекрасно", "хорошо", "отличный", "победа", "выигрыш",
        "молодец", "спасибо", "спасибо", "благодарю", "лучший", "лучше", "улучшение"
    ]
    
    negative_words = [
        "крах", "погано", "критика", "скандал", "провал", "позов", "негатив",
        "плохо", "плохой", "ужасно", "ужас", "беда", "беды", "проблема", 
        "ошибка", "ошибки", "падение", "поражение", "война", "конфликт",
        "насилие", "агрессия", "бойня", "катастрофа", "кризис"
    ]
    
    text_lower = text.lower()
    
    pos_count = sum(1 for word in positive_words if word.lower() in text_lower)
    neg_count = sum(1 for word in negative_words if word.lower() in text_lower)
    
    if pos_count > neg_count:
        score = min(0.5 + (pos_count - neg_count) * 0.1, 1.0)
        return "positive", score
    elif neg_count > pos_count:
        score = max(-0.5 - (neg_count - pos_count) * 0.1, -1.0)
        return "negative", score
    else:
        return "neutral", 0.0

def print_header(title):
    """Вивести заголовок"""
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)
    print()

def print_timestamp():
    """Вивести поточний час"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
