"""
ربات اخبار - نسخه interactive برای GitHub Actions
این نسخه برای اجرای دستی با پارامترهای خاص طراحی شده است
"""
import os
import time
import hashlib
import json
import requests
from datetime import datetime

# تنظیمات
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TARGET_USER_ID = os.getenv('TARGET_USER_ID')
SEARCH_KEYWORD = os.getenv('SEARCH_KEYWORD')
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

def save_user_keywords(keywords):
    """ذخیره کلمات کلیدی کاربران"""
    with open(USER_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)

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
    """اجرای دستی جستجوی اخبار"""
    print(f"Starting interactive news search at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        return
    
    if not TARGET_USER_ID:
        print("ERROR: TARGET_USER_ID not set!")
        return
    
    if not SEARCH_KEYWORD:
        print("ERROR: SEARCH_KEYWORD not set!")
        return
    
    print(f"Searching news for user {TARGET_USER_ID} with keyword: {SEARCH_KEYWORD}")
    
    # ذخیره کلمه کلیدی کاربر (اگر قبلاً ذخیره نشده)
    keywords = load_user_keywords()
    keywords[TARGET_USER_ID] = SEARCH_KEYWORD
    save_user_keywords(keywords)
    
    # دریافت اخبار
    all_news = get_news_sources(SEARCH_KEYWORD)
    
    if not all_news:
        print("No news found!")
        send_telegram_message(
            TARGET_USER_ID,
            "😔 متأسفانه خبری یافت نشد. لطفاً کلمه کلیدی دیگری امتحان کنید."
        )
        return
    
    print(f"Found {len(all_news)} news items")
    
    # بارگذاری اخبار قبلی
    sent_news = load_sent_news(TARGET_USER_ID)
    
    # فیلتر اخبار جدید
    new_news = [item for item in all_news if item['id'] not in sent_news]
    
    if not new_news:
        print("No new news since last check!")
        send_telegram_message(
            TARGET_USER_ID,
            "✅ هیچ خبر جدیدی از آخرین بررسی شما وجود ندارد.\n\nبعداً دوباره تلاش کنید!"
        )
        return
    
    print(f"Found {len(new_news)} new news items!")
    
    # ارسال پیام شروع
    send_telegram_message(
        TARGET_USER_ID,
        f"🔍 در حال جستجوی اخبار برای: <b>{SEARCH_KEYWORD}</b>\n\nلطفاً صبر کنید..."
    )
    
    # ارسال اخبار (حداکثر ۱۰ خبر)
    messages_sent = 0
    for item in new_news[:10]:
        message = f"""
📰 <b>{item['title']}</b>

🔗 <a href="{item['link']}">لینک خبر</a>
📢 منبع: {item['source']}
⏰ زمان: {item['pub_date']}
"""
        
        if send_telegram_message(TARGET_USER_ID, message):
            sent_news.add(item['id'])
            messages_sent += 1
            print(f"Sent: {item['title'][:50]}...")
            time.sleep(0.5)  # جلوگیری از محدودیت نرخ
    
    # ذخیره وضعیت
    save_sent_news(TARGET_USER_ID, sent_news)
    
    # ارسال پیام پایان
    send_telegram_message(
        TARGET_USER_ID,
        f"\n✅ تعداد {messages_sent} خبر جدید برای شما ارسال شد!"
    )
    
    print(f"Successfully sent {messages_sent} new news items to user {TARGET_USER_ID}!")

if __name__ == "__main__":
    main()
