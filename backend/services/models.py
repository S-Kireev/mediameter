"""
Re-export models from parent package and define service models
"""

from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime

# Re-export main models
from ..models import (
    Mention,
    Person,
    DailyAggregate,
    SentimentEnum,
    SourceTypeEnum,
    Base,
)

# Service-specific models
class AnalysisCache:
    """Cache for analysis results"""
    __tablename__ = "analysis_cache"
    
    id = Column(Integer, primary_key=True)
    query_hash = Column(String(255), unique=True, index=True)
    query = Column(Text)
    result = Column(Text)
    person_id = Column(Integer)
    period = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)
    
    def __init__(self, query_hash, query, result, person_id, period, expires_at):
        self.query_hash = query_hash
        self.query = query
        self.result = result
        self.person_id = person_id
        self.period = period
        self.created_at = datetime.utcnow()
        self.expires_at = expires_at

__all__ = [
    "Mention",
    "Person", 
    "DailyAggregate",
    "SentimentEnum",
    "SourceTypeEnum",
    "Base",
    "AnalysisCache",
]
