"""
ربات اخبار - نسخه scheduled برای GitHub Actions
این نسخه برای اجرای خودکار در GitHub Actions طراحی شده است
"""
import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta

# تنظیمات
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
STATE_FILE = '/tmp/news_state_global.json'
USER_KEYWORDS_FILE = '/tmp/user_keywords.json'

def get_news_sources(keyword):
    """دریافت اخبار از منابع مختلف بر اساس کلمه کلیدی"""
    news_items = []
    
    # 1. Google News RSS
    try:
        google_rss = f"https://news.google.com/rss/search?q={keyword}&hl=fa&gl=IR&ceid=IR:fa"
        response = requests.get(google_rss, timeout=10)
        if response.status_code == 200:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            for item in root.findall('.//item'):
                title = item.find('title').text if item.find('title') is not None else ''
                link = item.find('link').text if item.find('link') is not None else ''
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
                source = item.find('source').text if item.find('source') is not None else 'Google News'
                
                if title and link:
                    news_items.append({
                        'title': title,
                        'link': link,
                        'pub_date': pub_date,
                        'source': source,
                        'id': hashlib.md5(link.encode()).hexdigest()
                    })
    except Exception as e:
        print(f"Error fetching Google News: {e}")
    
    return news_items

def load_user_keywords():
    """بارگذاری کلمات کلیدی کاربران"""
    if os.path.exists(USER_KEYWORDS_FILE):
        try:
            with open(USER_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def load_sent_news(user_id):
    """بارگذاری لیست اخبار ارسالی شده برای کاربر"""
    state_file = f'/tmp/news_state_{user_id}.json'
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_sent_news(user_id, sent_ids):
    """ذخیره لیست اخبار ارسالی شده برای کاربر"""
    state_file = f'/tmp/news_state_{user_id}.json'
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(list(sent_ids), f, ensure_ascii=False)

def send_telegram_message(chat_id, message):
    """ارسال پیام به تلگرام"""
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram credentials not set!")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False
        }
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def main():
    """بررسی خودکار اخبار برای تمام کاربران"""
    print(f"Starting scheduled news check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        return
    
    # بارگذاری کلمات کلیدی تمام کاربران
    keywords = load_user_keywords()
    
    if not keywords:
        print("No users with keywords found!")
        return
    
    print(f"Found {len(keywords)} users to check news for")
    
    total_sent = 0
    
    # بررسی اخبار برای هر کاربر
    for user_id, keyword in keywords.items():
        print(f"\nChecking news for user {user_id} with keyword: {keyword}")
        
        # دریافت اخبار
        all_news = get_news_sources(keyword)
        
        if not all_news:
            print(f"No news found for keyword: {keyword}")
            continue
        
        # بارگذاری اخبار قبلی
        sent_news = load_sent_news(user_id)
        
        # فیلتر اخبار جدید
        new_news = [item for item in all_news if item['id'] not in sent_news]
        
        if not new_news:
            print(f"No new news for user {user_id}")
            continue
        
        print(f"Found {len(new_news)} new news items for user {user_id}")
        
        # ارسال اخبار (حداکثر ۵ خبر برای هر کاربر)
        messages_sent = 0
        for item in new_news[:5]:
            message = f"""
📰 <b>{item['title']}</b>

🔗 <a href="{item['link']}">لینک خبر</a>
📢 منبع: {item['source']}
⏰ زمان: {item['pub_date']}
"""
            
            if send_telegram_message(user_id, message):
                sent_news.add(item['id'])
                messages_sent += 1
                print(f"Sent: {item['title'][:50]}...")
                time.sleep(0.5)  # جلوگیری از محدودیت نرخ
        
        # ذخیره وضعیت
        save_sent_news(user_id, sent_news)
        total_sent += messages_sent
        print(f"Sent {messages_sent} news to user {user_id}")
    
    print(f"\n✅ Total news sent: {total_sent}")

if __name__ == "__main__":
    main()
