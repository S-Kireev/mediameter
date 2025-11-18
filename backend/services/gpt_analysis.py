import json
import hashlib
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from .models import AnalysisCache, Mention, Person
from .metrics import MetricsService
from openai import OpenAI
import os


class GPTAnalysisService:
    """Аналитические запросы к ChatGPT с кэшированием"""
    
    def __init__(self, db: Session, api_key: str):
        self.db = db
        self.client = OpenAI(api_key=api_key)
    
    def compute_query_hash(
        self,
        query: str,
        person_id: Optional[int],
        period: str,
    ) -> str:
        """Вычислить хеш запроса для кэша"""
        combined = f"{query}:{person_id}:{period}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def get_cached_analysis(self, query_hash: str) -> Optional[Dict]:
        """Получить анализ из кэша, если не истёк"""
        cache = self.db.query(AnalysisCache).filter(
            AnalysisCache.query_hash == query_hash,
            AnalysisCache.expires_at > datetime.utcnow(),
        ).first()
        
        if cache:
            return json.loads(cache.response)
        return None
    
    def cache_analysis(
        self,
        query_hash: str,
        query: str,
        response: Dict,
        person_id: Optional[int],
        period: str,
        ttl_hours: int = 24,
    ):
        """Сохранить анализ в кэш"""
        expires_at = datetime.utcnow() + __import__('datetime').timedelta(hours=ttl_hours)
        
        cache = AnalysisCache(
            query_hash=query_hash,
            query=query,
            response=json.dumps(response),
            person_id=person_id,
            period=period,
            expires_at=expires_at,
        )
        self.db.add(cache)
        self.db.commit()
    
    def analyze_sentiment_trend(
        self,
        person_id: Optional[int],
        period: str = "last_30",
        use_cache: bool = True,
    ) -> Dict:
        """Анализ тренда тональности и риск-факторы"""
        query = f"sentiment_trend:{person_id}:{period}"
        query_hash = self.compute_query_hash(query, person_id, period)
        
        if use_cache:
            cached = self.get_cached_analysis(query_hash)
            if cached:
                return cached
        
        # Получить метрики
        metrics_svc = MetricsService(self.db)
        sentiment = metrics_svc.get_sentiment_metrics(person_id, period)
        mention_count = metrics_svc.get_mention_count(person_id, period)
        
        person_name = "Невизначена персона"
        if person_id:
            person = self.db.query(Person).filter(Person.id == person_id).first()
            if person:
                person_name = person.name
        
        # Промпт для GPT
        prompt = f"""
Проанализируй медиа-метрики для персоны "{person_name}" за период {period}:

Метрики:
- Всього упоминаний: {mention_count['total']}
- В фокусе: {mention_count['focus']}
- Положительные: {sentiment['positive']} ({sentiment['pos_share']:.1%})
- Отрицательные: {sentiment['negative']} ({sentiment['neg_share']:.1%})
- Нейтральные: {sentiment['neutral']} ({sentiment['neu_share']:.1%})
- Net Sentiment Score: {sentiment['net_sentiment']:.2f}

Дай краткий анализ (3-5 предложений):
1. Общее настроение в медиа
2. Ключевые риск-факторы (если есть)
3. Рекомендации для управления репутацией
4. Тренд (улучшается, ухудшается или стабильно)

Отвечай на украинском языке, как аналитик PR-агентства.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Ты опытный PR-аналитик с глубокими знаннями медиа-ландшафта."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            
            analysis = response.choices[0].message.content
            
            result = {
                "type": "sentiment_trend",
                "analysis": analysis,
                "metrics": sentiment,
                "generated_at": datetime.utcnow().isoformat(),
            }
            
            # Кэшируем результат
            self.cache_analysis(query_hash, query, result, person_id, period)
            
            return result
        
        except Exception as e:
            return {
                "error": str(e),
                "analysis": "Помилка при звернені до GPT API",
            }
    
    def analyze_spike(
        self,
        person_id: Optional[int],
        period: str = "last_7",
    ) -> Dict:
        """Анализ всплесков упоминаний"""
        query = f"spike_analysis:{person_id}:{period}"
        query_hash = self.compute_query_hash(query, person_id, period)
        
        cached = self.get_cached_analysis(query_hash)
        if cached:
            return cached
        
        # Метрики
        metrics_svc = MetricsService(self.db)
        velocity = metrics_svc.get_velocity_metrics(person_id, period)
        top_sources = metrics_svc.get_top_sources(person_id, period, limit=5)
        top_topics = metrics_svc.get_top_topics(person_id, period, limit=5)
        
        person_name = "Невизначена персона"
        if person_id:
            person = self.db.query(Person).filter(Person.id == person_id).first()
            if person:
                person_name = person.name
        
        prompt = f"""
Проаналізуй всплеск упоминаний для "{person_name}":

Показатели:
- Z-score: {velocity['z_score']:.2f}
- Всплеск выявлен: {'Так' if velocity['is_spike'] else 'Ні'}
- Скорость: {velocity['velocity_per_hour']:.1f} упоминаний/час
- Ускорение: {velocity['acceleration']:+.2f}

Топ-источники:
{chr(10).join(f"- {s['source_title']}: {s['mentions']} упоминаний" for s in top_sources)}

Топ-темы:
{chr(10).join(f"- {t['name']}: {t['count']} упоминаний" for t in top_topics)}

Дай быструю оценку (2-4 речення):
1. Чи це природний всплеск чи кризис?
2. Основні драйвери тренда
3. Що робити (рекомендації)

Відповідай на українській мові, коротко і по суті.
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Ты експерт з кризисного管理 і медіа-аналізу."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=400,
            )
            
            analysis = response.choices[0].message.content
            
            result = {
                "type": "spike_analysis",
                "analysis": analysis,
                "is_spike": velocity['is_spike'],
                "z_score": velocity['z_score'],
                "generated_at": datetime.utcnow().isoformat(),
            }
            
            self.cache_analysis(query_hash, query, result, person_id, period)
            
            return result
        
        except Exception as e:
            return {
                "error": str(e),
                "analysis": "Помилка при аналізі всплесків",
            }
    
    def ask_custom_question(
        self,
        question: str,
        person_id: Optional[int],
        period: str = "last_30",
    ) -> Dict:
        """Кастомный вопрос об аналитике"""
        
        # Метрики для контекста
        metrics_svc = MetricsService(self.db)
        mention_count = metrics_svc.get_mention_count(person_id, period)
        sentiment = metrics_svc.get_sentiment_metrics(person_id, period)
        reach = metrics_svc.get_reach_metrics(person_id, period)
        velocity = metrics_svc.get_velocity_metrics(person_id, period)
        top_topics = metrics_svc.get_top_topics(person_id, period, limit=10)
        top_entities = metrics_svc.get_top_entities(person_id, period, limit=10)
        
        person_name = "Невизначена персона"
        if person_id:
            person = self.db.query(Person).filter(Person.id == person_id).first()
            if person:
                person_name = person.name
        
        context = f"""
Контекст аналітики для "{person_name}" за період {period}:

Обсяг: {mention_count['total']} упоминаний ({mention_count['focus']} в фокусе)
Охват: {reach['total_reach']:,} views
Тональность: {sentiment['pos_share']:.0%} позитив, {sentiment['neg_share']:.0%} негатив, {sentiment['neu_share']:.0%} нейтраль
Скорость: {velocity['velocity_per_hour']:.1f} упоминаний/час
Уникальні источники: {reach['unique_sources']}

Топ-теми: {', '.join(t['name'] for t in top_topics[:5])}
Топ-сущности: {', '.join(e['name'] for e in top_entities[:5])}
"""
        
        prompt = context + f"\nВопрос: {question}\n\nОтвет (коротко и по существу):"
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "Ты опытный PR и медиа-аналитик. Отвечай на основе предоставленных данных, кратко и профессионально."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=800,
            )
            
            answer = response.choices[0].message.content
            
            return {
                "type": "custom_question",
                "question": question,
                "answer": answer,
                "context_used": mention_count['total'] > 0,
                "generated_at": datetime.utcnow().isoformat(),
            }
        
        except Exception as e:
            return {
                "error": str(e),
                "answer": "Помилка при звернені до GPT API",
            }
