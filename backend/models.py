from sqlalchemy import (
    Column, Integer, String, DateTime, Float, Text, DECIMAL,
    Enum, Boolean, ForeignKey, Table, JSON, Index, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class SourceTypeEnum(str, enum.Enum):
    TELEGRAM = "telegram"
    NEWS = "news"
    SOCIAL = "social"
    BLOG = "blog"
    OTHER = "other"


class SentimentEnum(str, enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class FocusEnum(str, enum.Enum):
    FOCUS = "focus"
    MENTION = "mention"


# Association tables для many-to-many
person_mention = Table(
    'person_mention',
    Base.metadata,
    Column('mention_id', Integer, ForeignKey('mentions.id')),
    Column('person_id', Integer, ForeignKey('persons.id')),
    Index('idx_person_mention', 'mention_id', 'person_id')
)

mention_entity = Table(
    'mention_entity',
    Base.metadata,
    Column('mention_id', Integer, ForeignKey('mentions.id')),
    Column('entity_id', Integer, ForeignKey('entities.id')),
    Column('weight', Float, default=1.0),
    Index('idx_mention_entity', 'mention_id', 'entity_id')
)

mention_topic = Table(
    'mention_topic',
    Base.metadata,
    Column('mention_id', Integer, ForeignKey('mentions.id')),
    Column('topic_id', Integer, ForeignKey('topics.id')),
    Column('weight', Float, default=1.0),
    Index('idx_mention_topic', 'mention_id', 'topic_id')
)


class Person(Base):
    """Персона"""
    __tablename__ = "persons"
    
    id = Column(Integer, primary_key=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(190), nullable=False)
    name_variants = Column(JSON, default=[])  # ["Ім'я Прізвище", "Имя Фамилия", "Name Surname"]
    minus_words = Column(JSON, default=[])     # слова-омонимы для фильтра
    topics = Column(JSON, default=[])          # связанные темы
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    mentions = relationship("Mention", secondary=person_mention, back_populates="persons")
    
    def __repr__(self):
        return f"<Person {self.name}>"


class Mention(Base):
    """Упоминание"""
    __tablename__ = "mentions"
    
    id = Column(Integer, primary_key=True)
    external_id = Column(String(255), unique=True, nullable=False, index=True)
    source_type = Column(Enum(SourceTypeEnum), nullable=False)
    source_id = Column(String(190), nullable=False, index=True)
    source_title = Column(String(255))
    published_at = Column(DateTime, nullable=False, index=True)
    language = Column(String(10), default="uk")
    
    title = Column(Text)
    content = Column(Text)
    url = Column(String(500))
    quote = Column(Text)
    summary = Column(Text)
    
    # Метрики источника
    views = Column(Integer, default=0)
    forwards = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    
    # Тональность
    sentiment_label = Column(Enum(SentimentEnum))
    sentiment_score = Column(Float)  # -1 .. 1
    
    # Фокус
    focus = Column(Enum(FocusEnum), default=FocusEnum.MENTION)
    
    # Вычисленные веса
    influence = Column(Float, default=1.0)  # вес источника
    
    # Системные
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    persons = relationship("Person", secondary=person_mention, back_populates="mentions")
    entities = relationship("Entity", secondary=mention_entity, back_populates="mentions")
    topics = relationship("Topic", secondary=mention_topic, back_populates="mentions")
    
    __table_args__ = (
        Index('idx_published_at_sentiment', 'published_at', 'sentiment_label'),
        Index('idx_source_type_published', 'source_type', 'published_at'),
    )
    
    def __repr__(self):
        return f"<Mention {self.external_id}>"


class Entity(Base):
    """Сущность (организация, место, концепция)"""
    __tablename__ = "entities"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(190), unique=True, nullable=False, index=True)
    entity_type = Column(String(50))  # organization, location, concept
    
    mentions = relationship("Mention", secondary=mention_entity, back_populates="entities")


class Topic(Base):
    """Тема/тег"""
    __tablename__ = "topics"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(190), unique=True, nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey('topics.id'), nullable=True)
    
    mentions = relationship("Mention", secondary=mention_topic, back_populates="topics")


class DailyAggregate(Base):
    """Материализованная суточная агрегация"""
    __tablename__ = "daily_aggregates"
    
    id = Column(Integer, primary_key=True)
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    person_id = Column(Integer, ForeignKey('persons.id'), nullable=True, index=True)
    source_type = Column(Enum(SourceTypeEnum), nullable=True, index=True)
    
    mentions_count = Column(Integer, default=0)
    focus_count = Column(Integer, default=0)
    positive_count = Column(Integer, default=0)
    negative_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    
    total_reach = Column(Integer, default=0)  # сумма views
    total_influence = Column(Float, default=0.0)
    unique_sources = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_daily_agg', 'date', 'person_id', 'source_type', unique=False),
    )


class APIKey(Base):
    """API ключи для приёма данных"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(100))
    allowed_ips = Column(JSON, default=[])  # ["192.168.1.1", "*"]
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)


class AnalysisCache(Base):
    """Кэш аналитических запросов к GPT"""
    __tablename__ = "analysis_cache"
    
    id = Column(Integer, primary_key=True)
    query_hash = Column(String(64), unique=True, nullable=False, index=True)
    query = Column(Text)
    response = Column(Text)  # JSON с результатом GPT
    person_id = Column(Integer, ForeignKey('persons.id'), nullable=True)
    period = Column(String(50))  # last_7, last_30, etc.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # TTL для кэша
