import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func
from .models import Mention


class DedupService:
    """Дедупликация и нормализация упоминаний"""
    
    @staticmethod
    def compute_external_id_hash(external_id: str) -> str:
        """Создать SHA1 хеш external_id"""
        return hashlib.sha1(external_id.encode()).hexdigest()
    
    @staticmethod
    def compute_content_hash(source_id: str, published_at: datetime, content: str) -> str:
        """
        Создать хеш на основе источника, времени и первых 200 символов контента.
        Это для поиска дубликатов при отсутствии external_id.
        """
        first_200 = content[:200] if content else ""
        combined = f"{source_id}:{published_at.isoformat()}:{first_200}"
        return hashlib.sha1(combined.encode()).hexdigest()
    
    @staticmethod
    def check_duplicate(
        db: Session,
        external_id: str,
        source_id: str,
        published_at: datetime,
        content: str,
    ) -> Optional[Mention]:
        """
        Проверить, существует ли уже такое упоминание.
        Сначала ищем по external_id, потом по комбинированному хешу.
        """
        # Поиск по external_id
        if external_id:
            existing = db.query(Mention).filter(
                Mention.external_id == external_id
            ).first()
            if existing:
                return existing
        
        # Поиск по контент-хешу (в окне ±1 минута от published_at)
        time_window_start = published_at - timedelta(minutes=1)
        time_window_end = published_at + timedelta(minutes=1)
        
        content_hash = DedupService.compute_content_hash(
            source_id, published_at, content
        )
        
        # Грубая дедупликация: ищем по source + время
        existing = db.query(Mention).filter(
            Mention.source_id == source_id,
            Mention.published_at.between(time_window_start, time_window_end),
            func.left(Mention.content, 200) == content[:200],
        ).first()
        
        return existing
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Базовая нормализация текста"""
        if not text:
            return ""
        
        # Убрать лишние пробелы
        text = " ".join(text.split())
        
        # UTF-8 normalization (уже в Python 3, но на всякий случай)
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        
        return text
    
    @staticmethod
    def detect_language(text: str) -> str:
        """
        Простое определение языка по ключевым символам.
        Можно улучшить с помощью langdetect, но это добавит зависимость.
        """
        if not text:
            return "unknown"
        
        cyrillic_chars = sum(1 for c in text if '\u0400' <= c <= '\u04ff')
        latin_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        
        total_alpha = cyrillic_chars + latin_chars
        
        if total_alpha == 0:
            return "unknown"
        
        cyrillic_ratio = cyrillic_chars / total_alpha
        
        if cyrillic_ratio > 0.7:
            # Может быть УК или РУ, простая эвристика
            if 'ї' in text or 'є' in text or 'і' in text or 'ґ' in text:
                return "uk"
            return "ru"
        elif cyrillic_ratio > 0.3:
            return "mixed"
        else:
            return "en"
    
    @staticmethod
    def parse_date(date_str: str) -> Optional[datetime]:
        """Парсер ISO 8601 дат"""
        from dateutil import parser
        try:
            return parser.isoparse(date_str)
        except:
            return None


# Import для инициализации services __init__.py
from .models import Mention
