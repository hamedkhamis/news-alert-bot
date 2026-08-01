import feedparser
import requests
import json
import os
from datetime import datetime, timezone
import time
import re
import html

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
SEEN_FILE = "seen.json"

# فقط اخبار ۷ روز اخیر
MAX_AGE_DAYS = 7

FEEDS = [
    {"url": "https://zoomit.ir/feed",           "name": "زومیت"},
    {"url": "https://digiato.com/feed",          "name": "دیجیاتو"},
    {"url": "https://www.click.ir/feed",         "name": "کلیک"},
    {"url": "https://www.imarketor.com/feed",    "name": "آی‌مارکتور"},
    {"url": "https://ecomotive.ir/feed",         "name": "اکوموتیو"},
    {"url": "https://techna.news/feed",          "name": "تکنا"},
    {"url": "https://technoc.ir/feed",           "name": "تکنوک"},
    {"url": "https://www.shahrsakhtafzar.com/fa/news/feed", "name": "شهر سخت‌افزار"},
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

def time_ago(published):
    try:
        pub_time = datetime(*published[:6], tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - pub_time
        minutes = int(diff.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes} minutes ago"
        elif minutes < 1440:
            return f"{minutes // 60} hours ago"
        else:
            return f"{minutes // 1440} days ago"
    except:
        return "recently"

def is_fresh(published):
    """فقط اخبار ۷ روز اخیر"""
    if not published:
        return False
    try:
        pub_time = datetime(*published[:6], tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - pub_time
        return diff.total_seconds() < (MAX_AGE_DAYS * 86400)
    except:
        return False

def clean_summary(text, max_len=200):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = ' '.join(text.split())
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + "..."
    return text.strip()

def fetch_all_news(seen):
    new_items = []

    for feed_info in FEEDS:
        try:
            print(f"  Fetching: {feed_info['name']}")
            feed = feedparser.parse(feed_info["url"])

            for entry in feed.entries:
                link = entry.get("link", "")
                title = entry.get("title", "")
                published = entry.get("published_parsed", None)

                if not link or not title:
                    continue

                # فقط اخبار تازه
                if not is_fresh(published):
                    continue

                # فقط اخبار جدید
                if link in seen:
                    continue

                raw_summary = entry.get("summary", "") or entry.get("description", "")
                summary = clean_summary(raw_summary)

                date_str = datetime(*published[:6]).strftime("%Y-%m-%d") if published else "N/A"
                ago = time_ago(published) if published else "recently"

                new_items.append({
                    "title": title,
                    "link": link,
                    "source": feed_info["name"],
                    "date": date_str,
                    "ago": ago,
                    "summary": summary,
                    "published": published,
                })

                seen[link] = True

        except Exception as e:
            print(f"  Error {feed_info['name']}: {e}")

    # مرتب از جدید به قدیم
    new_items.sort(
        key=lambda x: x["published"] if x["published"] else (2000,1,1,0,0,0),
        reverse=True
    )

    return new_items

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"  Telegram: {r.status_code}")
    except Exception as e:
        print(f"  Telegram error: {e}")
    time.sleep(0.5)

def main():
    seen = load_seen()

    print("📡 Fetching news from Persian sources...")
    new_items = fetch_all_news(seen)

    if not new_items:
        print("No new items.")
        save_seen(seen)
        return

    print(f"\n📬 Total new items: {len(new_items)}")

    # هر ۱۰ تا یه پیام
    number_emojis = ["1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣","🔟"]
    chunk_size = 10
    chunks = [new_items[i:i+chunk_size] for i in range(0, len(new_items), chunk_size)]

    for chunk_idx, chunk in enumerate(chunks):
        part = f" | بخش {chunk_idx+1} از {len(chunks)}" if len(chunks) > 1 else ""
        header = f"🔔 <b>{len(chunk)} خبر جدید تکنولوژی{part}</b>\n\n"
        message = header

        for i, item in enumerate(chunk, 1):
            num = number_emojis[i-1] if i <= 10 else f"{i}."
            short_title = item['title'][:120]
            summary_line = f"📝 {item['summary']}\n" if item['summary'] else ""

            message += (
                f"{num} <b>{short_title}</b>\n"
                f"<i>{item['source']}</i> | {item['date']}\n\n"
                f"{summary_line}"
                f"🔗 <a href='{item['link']}'>منبع</a>   "
                f"🕒 {item['ago']}\n\n"
                f"{'─' * 28}\n\n"
            )

        send_message(message)
        print(f"  ✅ Sent chunk {chunk_idx+1}")

    save_seen(seen)
    print(f"\n✅ Done. Total sent: {len(new_items)} items in {len(chunks)} messages.")

if __name__ == "__main__":
    main()
