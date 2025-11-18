"""
MediaMeter RSS Parser v3 - для Railway
Загружает персон из БД и собирает новости
"""

import asyncio
import hashlib
from datetime import datetime
import os
import sys

# Добавить текущую папку в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from collectors_utils_v2 import (
        get_persons_from_db, send_to_api, extract_persons_from_text,
        analyze_sentiment, print_header, print_timestamp
    )
except ImportError:
    print("❌ Error: collectors_utils_v2.py not found!")
    sys.exit(1)

import feedparser

# ============ CONFIG ============

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev_key_change_in_prod")
COLLECTION_INTERVAL = int(os.getenv("COLLECTION_INTERVAL", "3600"))  # 1 час

# RSS канали
RSS_FEEDS = [
    {"name": "Українська правда", "url": "https://www.pravda.com.ua/rss/"},
    {"name": "BBC Україна", "url": "https://www.bbc.com/ukrainian/index.xml"},
    {"name": "Укринформ", "url": "https://www.ukrinform.ua/rss/all"},
]

PROCESSED_IDS = set()
PERSONS = []

# ============ FUNCTIONS ============

def get_article_id(url, title):
    """Генерувати унікальний ID"""
    return hashlib.md5(f"{url}{title}".encode()).hexdigest()

async def process_feed(feed_info, persons_list):
    """Обробити RSS канал"""
    try:
        print(f"\n📰 {feed_info['name']}")
        feed = feedparser.parse(feed_info['url'])
        
        entries = feed.entries[:20]  # Взяти більше статей
        print(f"  Found {len(entries)} articles")
        
        processed_count = 0
        
        for entry in entries:
            try:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                link = entry.get('link', '')
                published = entry.get('published', '')
                
                if not title or not link:
                    continue
                
                # Перевірити персону
                persons = extract_persons_from_text(title + " " + summary, persons_list)
                if not persons:
                    continue
                
                # Перевірити чи не обробили
                article_id = get_article_id(link, title)
                if article_id in PROCESSED_IDS:
                    continue
                
                PROCESSED_IDS.add(article_id)
                
                # Аналіз тональності
                sentiment, score = analyze_sentiment(title + " " + summary)
                
                # Parse дати
                try:
                    # Спробувати різні формати дат
                    if published:
                        published_dt = datetime.strptime(published[:19], "%Y-%m-%dT%H:%M:%S")
                    else:
                        published_dt = datetime.now()
                except:
                    published_dt = datetime.now()
                
                # Дані для API
                mention_data = {
                    "external_id": article_id,
                    "source_type": "news",
                    "source_id": feed_info['name'],
                    "source_title": feed_info['name'],
                    "published_at": published_dt.isoformat(),
                    "title": title[:200],
                    "content": summary[:1000],
                    "url": link,
                    "persons": persons,
                    "sentiment": {"label": sentiment, "score": score},
                }
                
                # Відправити на API
                success, status = await send_to_api(mention_data, API_BASE_URL, API_KEY)
                if success:
                    print(f"  ✓ {title[:50]}... ({persons[0]})")
                    processed_count += 1
                else:
                    print(f"  ❌ Failed: {status}")
            
            except Exception as e:
                pass
        
        if processed_count > 0:
            print(f"  ✓ Processed {processed_count} articles with tracked persons")
    
    except Exception as e:
        print(f"  ❌ Error: {e}")

async def main():
    """Основна функція"""
    global PERSONS
    
    print_header("MediaMeter RSS Parser v3 (Railway)")
    
    print(f"Configuration:")
    print(f"  API_BASE_URL: {API_BASE_URL}")
    print(f"  API_KEY: {API_KEY[:20]}...")
    print(f"  Collection interval: {COLLECTION_INTERVAL}s")
    print()
    
    # Загрузить персон з БД
    PERSONS = get_persons_from_db()
    if not PERSONS:
        print("❌ No persons to track! Add some to database first.")
        return
    
    print(f"✓ Tracking persons:")
    for person in PERSONS:
        print(f"  • {person}")
    print()
    
    iteration = 0
    while True:
        iteration += 1
        print(f"\n{'='*60}")
        print(f"⏱ Iteration #{iteration} - {print_timestamp()}")
        print(f"{'='*60}")
        
        try:
            for feed_info in RSS_FEEDS:
                await process_feed(feed_info, PERSONS)
        except Exception as e:
            print(f"\n❌ Iteration error: {e}")
        
        print(f"\n⏳ Waiting {COLLECTION_INTERVAL}s until next collection...")
        await asyncio.sleep(COLLECTION_INTERVAL)

if __name__ == "__main__":
    try:
        print("✓ Starting RSS Parser v3...")
        print()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✓ Parser stopped by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        sys.exit(1)
