from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

from .config import settings
from .database import get_db, init_db
from .models import (
    Person, Mention, Entity, Topic, SentimentEnum, 
    SourceTypeEnum, FocusEnum, APIKey
)

# Инициализация FastAPI
app = FastAPI(
    title="MediaMeter API",
    description="Система аналитики упоминаний персон в медиа",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Pydantic Models ============

class MentionCreate(BaseModel):
    external_id: str
    source_type: str
    source_id: str
    source_title: str
    published_at: str
    language: Optional[str] = "uk"
    
    title: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    quote: Optional[str] = None
    summary: Optional[str] = None
    
    persons: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    
    views: Optional[int] = 0
    forwards: Optional[int] = 0
    likes: Optional[int] = 0
    comments: Optional[int] = 0
    
    sentiment: Optional[dict] = None
    focus: Optional[str] = "mention"


class PersonCreate(BaseModel):
    name: str
    slug: str
    name_variants: List[str] = Field(default_factory=list)
    minus_words: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)


class PersonResponse(BaseModel):
    id: int
    name: str
    slug: str
    active: bool
    
    class Config:
        from_attributes = True


# ============ Authentication ============

def verify_api_key(x_mm_key: str = Header(None), db: Session = Depends(get_db)):
    """Проверить API ключ"""
    if not x_mm_key:
        raise HTTPException(status_code=401, detail="API key required in X-MM-Key header")
    
    api_key = db.query(APIKey).filter(
        APIKey.key == x_mm_key,
        APIKey.active == True,
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return api_key


# ============ Routes ============

@app.on_event("startup")
async def startup_event():
    """Инициализация при старте"""
    init_db()
    print("✓ API started")


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok"}


@app.get("/v1/test", tags=["Debug"])
async def test_endpoint():
    """Простой тестовый эндпоинт"""
    return {"message": "API is working!", "timestamp": datetime.now().isoformat()}


@app.get("/v1/debug/persons", tags=["Debug"])
async def debug_persons(db: Session = Depends(get_db)):
    """Показать всех персон в БД (для отладки)"""
    try:
        persons = db.query(Person).all()
        return {
            "total": len(persons),
            "persons": [{"id": p.id, "name": p.name, "active": p.active} for p in persons]
        }
    except Exception as e:
        return {"error": str(e)}


# --- Persons Management ---

@app.post("/v1/persons", response_model=PersonResponse, tags=["Persons"])
async def create_person(
    person: PersonCreate,
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Создать новую персону"""
    existing = db.query(Person).filter(Person.slug == person.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Person with this slug already exists")
    
    db_person = Person(
        name=person.name,
        slug=person.slug,
        name_variants=person.name_variants,
        minus_words=person.minus_words,
        topics=person.topics,
    )
    db.add(db_person)
    db.commit()
    db.refresh(db_person)
    return db_person


@app.get("/v1/persons", response_model=List[PersonResponse], tags=["Persons"])
async def list_persons(db: Session = Depends(get_db)):
    """Список всех персон"""
    persons = db.query(Person).all()
    return persons


@app.get("/v1/persons/{person_id}", response_model=PersonResponse, tags=["Persons"])
async def get_person(person_id: int, db: Session = Depends(get_db)):
    """Получить персону"""
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


# --- Metrics ---

@app.get("/v1/metrics/{person_id}", tags=["Metrics"])
async def get_metrics(person_id: int, period: str = "last_7", db: Session = Depends(get_db)):
    """Получить метрики для персоны"""
    try:
        # Базовые метрики
        person = db.query(Person).filter(Person.id == person_id).first()
        if not person:
            raise HTTPException(status_code=404, detail="Person not found")
        
        # Считать упоминания
        mentions = db.query(Mention).filter(
            Mention.persons.any(Person.id == person_id)
        ).all()
        
        total = len(mentions)
        focus = sum(1 for m in mentions if m.focus.value == "focus")
        
        # Тональность
        positive = sum(1 for m in mentions if m.sentiment_label.value == "positive")
        negative = sum(1 for m in mentions if m.sentiment_label.value == "negative")
        neutral = sum(1 for m in mentions if m.sentiment_label.value == "neutral")
        
        pos_share = positive / total if total > 0 else 0
        neg_share = negative / total if total > 0 else 0
        net_sentiment = (positive - negative) / total if total > 0 else 0
        
        # Охват
        total_reach = sum(m.views or 0 for m in mentions)
        unique_sources = len(set(m.source_id for m in mentions))
        
        # Скорость
        velocity_per_hour = len(mentions) / 24 if mentions else 0
        acceleration = 0
        
        # Источники
        source_counts = {}
        for m in mentions:
            if m.source_title not in source_counts:
                source_counts[m.source_title] = {"mentions": 0, "views": 0}
            source_counts[m.source_title]["mentions"] += 1
            source_counts[m.source_title]["views"] += m.views or 0
        
        top_sources = [
            {"source_title": k, "mentions": v["mentions"], "views": v["views"]}
            for k, v in sorted(source_counts.items(), key=lambda x: x[1]["mentions"], reverse=True)[:5]
        ]
        
        # Темы
        top_topics = [{"name": "General", "mentions": total}]
        
        return {
            "mentions": {"total": total, "focus": focus},
            "sentiment": {
                "positive": positive,
                "negative": negative,
                "neutral": neutral,
                "pos_share": pos_share,
                "neg_share": neg_share,
                "net_sentiment": net_sentiment,
            },
            "reach": {
                "total_reach": total_reach,
                "unique_sources": unique_sources,
            },
            "velocity": {
                "velocity_per_hour": velocity_per_hour,
                "acceleration": acceleration,
            },
            "top_sources": top_sources,
            "top_topics": top_topics,
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- Mentions Ingestion ---

@app.post("/v1/ingest", tags=["Ingestion"])
async def ingest_mention(
    data: MentionCreate,
    api_key: APIKey = Depends(verify_api_key),
    db: Session = Depends(get_db),
):
    """Приём упоминания из внешних источников"""
    
    try:
        # Парсить дату
        try:
            published_at = datetime.fromisoformat(data.published_at.replace('Z', '+00:00'))
        except:
            published_at = datetime.now()
        
        # Создать упоминание
        mention = Mention(
            external_id=data.external_id,
            source_type=SourceTypeEnum(data.source_type),
            source_id=data.source_id,
            source_title=data.source_title,
            published_at=published_at,
            language=data.language or "uk",
            title=data.title or "",
            content=data.content or "",
            url=data.url,
            quote=data.quote,
            summary=data.summary,
            views=data.views or 0,
            forwards=data.forwards or 0,
            likes=data.likes or 0,
            comments=data.comments or 0,
            focus=FocusEnum(data.focus or "mention"),
        )
        
        # Тональность
        if data.sentiment:
            try:
                mention.sentiment_label = SentimentEnum(data.sentiment.get("label", "neutral"))
                mention.sentiment_score = float(data.sentiment.get("score", 0))
            except:
                mention.sentiment_label = SentimentEnum.NEUTRAL
                mention.sentiment_score = 0
        else:
            mention.sentiment_label = SentimentEnum.NEUTRAL
            mention.sentiment_score = 0
        
        mention.influence = 1.0
        
        db.add(mention)
        db.flush()
        
        # Добавить персон
        if data.persons:
            for person_name in data.persons:
                person = db.query(Person).filter(
                    Person.name == person_name
                ).first()
                
                if person:
                    mention.persons.append(person)
        
        # Добавить сущности
        if data.entities:
            for entity_name in data.entities:
                entity = db.query(Entity).filter(Entity.name == entity_name).first()
                if not entity:
                    entity = Entity(name=entity_name, entity_type="general")
                    db.add(entity)
                    db.flush()
                mention.entities.append(entity)
        
        # Добавить темы
        if data.topics:
            for topic_name in data.topics:
                topic = db.query(Topic).filter(Topic.name == topic_name).first()
                if not topic:
                    topic = Topic(name=topic_name)
                    db.add(topic)
                    db.flush()
                mention.topics.append(topic)
        
        db.commit()
        db.refresh(mention)
        
        return {
            "status": "success",
            "mention_id": mention.id,
            "created_at": mention.created_at.isoformat(),
        }
    
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error ingesting mention: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
