from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .config import settings
from .models import Base, APIKey, Person

# Создание engine
import os

# Получить DATABASE_URL напрямую из окружения, игнорируя settings
database_url = os.getenv("DATABASE_URL", "sqlite:///./mediameter.db")

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
    echo=os.getenv("DEBUG", "False").lower() == "true",
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    """Зависимость FastAPI для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Инициализация всех таблиц"""
    Base.metadata.create_all(bind=engine)
    print("✓ База данных инициализирована")
    
    # Create default dev API key
    db = SessionLocal()
    try:
        dev_key = db.query(APIKey).filter(APIKey.key == "dev_key_change_in_prod").first()
        if not dev_key:
            dev_key = APIKey(
                key="dev_key_change_in_prod",
                name="Development Key",
                active=True,
            )
            db.add(dev_key)
            print("✓ Dev API key created")
        
        # Create test person if none exists
        test_person = db.query(Person).filter(Person.slug == "test-person").first()
        if not test_person:
            test_person = Person(
                name="Test Person",
                slug="test-person",
                name_variants=["Test", "Test Person"],
                active=True,
            )
            db.add(test_person)
            print("✓ Test person created")
        
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠ Error: {e}")
    finally:
        db.close()

def drop_all_tables():
    """Удалить все таблицы"""
    Base.metadata.drop_all(bind=engine)
    print("✓ Все таблицы удалены")