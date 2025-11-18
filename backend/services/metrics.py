from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import statistics
from .models import Mention, Person, DailyAggregate, SentimentEnum, SourceTypeEnum
import pytz


class MetricsService:
    """Расчёт KPI и аналитических метрик"""
    
    def __init__(self, db: Session, timezone: str = "UTC"):
        self.db = db
        self.tz = pytz.timezone(timezone)
    
    def get_period_dates(self, period: str) -> tuple:
        """Получить диапазон дат по названию периода"""
        now = datetime.now(self.tz).replace(tzinfo=None)
        
        if period == "all_time":
            start = datetime(2000, 1, 1)
        elif period == "ytd":  # Year to Date
            start = datetime(now.year, 1, 1)
        elif period == "qtd":  # Quarter to Date
            quarter = (now.month - 1) // 3
            start = datetime(now.year, quarter * 3 + 1, 1)
        elif period == "last_90":
            start = now - timedelta(days=90)
        elif period == "last_30":
            start = now - timedelta(days=30)
        elif period == "last_14":
            start = now - timedelta(days=14)
        elif period == "last_7":
            start = now - timedelta(days=7)
        elif period == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "last_24h":
            start = now - timedelta(hours=24)
        elif period == "last_3h":
            start = now - timedelta(hours=3)
        else:
            start = now - timedelta(days=30)
        
        return start, now
    
    def get_mention_count(
        self, person_id: Optional[int] = None, period: str = "last_30"
    ) -> Dict:
        """Подсчёт упоминаний"""
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end)
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        total = query.count()
        focus = query.filter(Mention.focus == "focus").count()
        
        # Распределение по источникам
        source_dist = query.with_entities(
            Mention.source_type, func.count(Mention.id)
        ).group_by(Mention.source_type).all()
        
        return {
            "total": total,
            "focus": focus,
            "mention": total - focus,
            "by_source": dict(source_dist),
        }
    
    def get_sentiment_metrics(
        self, person_id: Optional[int] = None, period: str = "last_30"
    ) -> Dict:
        """Анализ тональности"""
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end)
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        sentiment_counts = query.with_entities(
            Mention.sentiment_label, func.count(Mention.id)
        ).group_by(Mention.sentiment_label).all()
        
        sentiment_dict = dict(sentiment_counts)
        total = sum(sentiment_dict.values())
        
        pos = sentiment_dict.get(SentimentEnum.POSITIVE, 0)
        neg = sentiment_dict.get(SentimentEnum.NEGATIVE, 0)
        neu = sentiment_dict.get(SentimentEnum.NEUTRAL, 0)
        
        # Net sentiment = (pos - neg) / max(1, total)
        net_sentiment = (pos - neg) / max(1, total)
        
        # Средневзвешенная тональность по influence
        mentions = query.all()
        weighted_sentiment = 0
        if mentions:
            total_influence = sum(m.influence for m in mentions)
            for m in mentions:
                score = m.sentiment_score or 0
                weight = m.influence / max(1, total_influence)
                weighted_sentiment += score * weight
        
        return {
            "positive": pos,
            "negative": neg,
            "neutral": neu,
            "total": total,
            "pos_share": pos / total if total else 0,
            "neg_share": neg / total if total else 0,
            "neu_share": neu / total if total else 0,
            "net_sentiment": net_sentiment,
            "weighted_sentiment": weighted_sentiment,
        }
    
    def get_reach_metrics(
        self, person_id: Optional[int] = None, period: str = "last_30"
    ) -> Dict:
        """Охват и вес источников"""
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end)
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        mentions = query.all()
        
        total_views = sum(m.views or 0 for m in mentions)
        total_influence = sum(m.influence or 0 for m in mentions)
        unique_sources = self.db.query(func.count(func.distinct(Mention.source_id))).filter(
            Mention.published_at.between(start, end)
        ).scalar()
        
        if person_id:
            unique_sources = query.with_entities(
                func.count(func.distinct(Mention.source_id))
            ).scalar()
        
        return {
            "total_views": total_views,
            "total_reach": total_views,
            "total_influence": total_influence,
            "avg_influence": total_influence / len(mentions) if mentions else 0,
            "unique_sources": unique_sources,
        }
    
    def get_velocity_metrics(
        self, person_id: Optional[int] = None, period: str = "last_7"
    ) -> Dict:
        """Скорость и всплески"""
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end)
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        mentions = query.all()
        
        # Скорость по часам
        hourly_counts = {}
        for m in mentions:
            hour_key = m.published_at.strftime("%Y-%m-%d %H:00")
            hourly_counts[hour_key] = hourly_counts.get(hour_key, 0) + 1
        
        hourly_values = list(hourly_counts.values())
        
        if not hourly_values:
            return {
                "velocity_per_hour": 0,
                "velocity_per_day": 0,
                "acceleration": 0,
                "z_score": 0,
                "is_spike": False,
            }
        
        # Средняя скорость
        velocity_per_hour = sum(hourly_values) / len(hourly_values) if hourly_values else 0
        velocity_per_day = velocity_per_hour * 24
        
        # Ускорение (сравнить с предыдущим периодом)
        prev_start = start - (end - start)
        prev_query = self.db.query(Mention).filter(
            Mention.published_at.between(prev_start, start)
        )
        if person_id:
            prev_query = prev_query.join(Mention.persons).filter(Person.id == person_id)
        
        prev_mentions = prev_query.all()
        prev_velocity = len(prev_mentions) / max(1, (start - prev_start).total_seconds() / 3600)
        acceleration = velocity_per_hour - prev_velocity
        
        # Z-score для всплесков
        mean = statistics.mean(hourly_values) if hourly_values else 0
        stdev = statistics.stdev(hourly_values) if len(hourly_values) > 1 else 1
        current = hourly_values[-1] if hourly_values else 0
        z_score = (current - mean) / max(0.1, stdev)
        is_spike = z_score >= 2
        
        return {
            "velocity_per_hour": velocity_per_hour,
            "velocity_per_day": velocity_per_day,
            "acceleration": acceleration,
            "z_score": z_score,
            "is_spike": is_spike,
            "hourly_distribution": hourly_counts,
        }
    
    def get_top_sources(
        self, person_id: Optional[int] = None, period: str = "last_30", limit: int = 10
    ) -> List[Dict]:
        """Топ источники по упоминаниям/охвату"""
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end)
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        sources = query.with_entities(
            Mention.source_id,
            Mention.source_title,
            func.count(Mention.id).label("mention_count"),
            func.sum(Mention.views).label("total_views"),
        ).group_by(Mention.source_id, Mention.source_title).order_by(
            func.count(Mention.id).desc()
        ).limit(limit).all()
        
        return [
            {
                "source_id": s[0],
                "source_title": s[1],
                "mentions": s[2],
                "views": s[3] or 0,
            }
            for s in sources
        ]
    
    def get_top_topics(
        self, person_id: Optional[int] = None, period: str = "last_30", limit: int = 10
    ) -> List[Dict]:
        """Топ темы"""
        from sqlalchemy.orm import joinedload
        
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end)
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        mentions = query.all()
        
        topic_counts = {}
        for m in mentions:
            for topic in m.topics:
                topic_counts[topic.name] = topic_counts.get(topic.name, 0) + 1
        
        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        return [
            {"name": name, "count": count}
            for name, count in sorted_topics
        ]
    
    def get_top_entities(
        self, person_id: Optional[int] = None, period: str = "last_30", limit: int = 10
    ) -> List[Dict]:
        """Топ со-упоминания (сущности)"""
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end)
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        mentions = query.all()
        
        entity_counts = {}
        for m in mentions:
            for entity in m.entities:
                entity_counts[entity.name] = entity_counts.get(entity.name, 0) + 1
        
        sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        
        return [
            {"name": name, "count": count}
            for name, count in sorted_entities
        ]
    
    def get_key_quotes(
        self, person_id: Optional[int] = None, period: str = "last_30", limit: int = 5
    ) -> List[Dict]:
        """Ключевые цитаты"""
        start, end = self.get_period_dates(period)
        
        query = self.db.query(Mention).filter(
            Mention.published_at.between(start, end),
            Mention.quote.isnot(None),
        )
        
        if person_id:
            query = query.join(Mention.persons).filter(Person.id == person_id)
        
        quotes = query.order_by(Mention.influence.desc()).limit(limit).all()
        
        return [
            {
                "text": q.quote,
                "source": q.source_title,
                "url": q.url,
                "published_at": q.published_at.isoformat(),
            }
            for q in quotes
        ]
