import feedparser
import requests
import json
import os
from datetime import datetime, timezone
import time

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
SEEN_FILE = "seen.json"

# ✏️ کلمات کلیدی خودت رو اینجا بنویس
KEYWORDS = [
    "سئو",
    "دیجیتال مارکتینگ",
    "هوش مصنوعی",
]

def get_feeds(keyword):
    q = requests.utils.quote(keyword)
    return [
        f"https://news.google.com/rss/search?q={q}&hl=fa&gl=IR&ceid=IR:fa",
        f"https://news.google.com/rss/search?q={q}&hl=en&gl=US&ceid=US:en",
        "https://www.isna.ir/rss",
        "https://www.tasnimnews.com/fa/rss/feed/0/8/0",
        "https://www.farsnews.ir/rss",
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
        print(f"  Telegram response: {r.status_code}")
    except Exception as e:
        print(f"  Telegram error: {e}")
    time.sleep(1)

def check_keyword(keyword, seen):
    new_items = []

    for feed_url in get_feeds(keyword):
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:15]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                published = entry.get("published_parsed", None)

                try:
                    source = entry.source.title
                except:
                    source = feed.feed.get("title", "Unknown")

                # فیدهای ایران رو فیلتر کن بر اساس کیورد
                is_google = "news.google.com" in feed_url
                if not is_google:
                    if keyword.lower() not in title.lower():
                        continue

                if link and link not in seen:
                    seen[link] = True
                    date_str = datetime(*published[:6]).strftime("%Y-%m-%d") if published else "N/A"
                    ago = time_ago(published) if published else "recently"
                    new_items.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "date": date_str,
                        "ago": ago,
                    })
        except Exception as e:
            print(f"  Error fetching {feed_url}: {e}")

    return new_items

def main():
    seen = load_seen()
    total_sent = 0

    for keyword in KEYWORDS:
        print(f"\n🔍 Checking: {keyword}")
        new_items = check_keyword(keyword, seen)

        if not new_items:
            print(f"  No new results.")
            continue

        # محدود به ۵ آیتم در هر بار
        items_to_send = new_items[:5]

        header = f"🔔 <b>{len(items_to_send)} new results for #{keyword.replace(' ', '_')}</b>\n\n"
        message = header

        for i, item in enumerate(items_to_send, 1):
            number_emojis = ["1⃣","2⃣","3⃣","4⃣","5⃣"]
            num = number_emojis[i-1] if i <= 5 else f"{i}."

            short_title = item['title'][:120]
            message += (
                f"{num} <b>{short_title}</b>\n"
                f"<i>{item['source']}</i> | {item['date']}\n\n"
                f"📌 {short_title}\n"
                f"🔗 <a href='{item['link']}'>Source</a>   "
                f"🕒 {item['ago']}\n\n"
                f"{'─' * 28}\n\n"
            )

        send_message(message)
        total_sent += len(items_to_send)
        print(f"  ✅ Sent {len(items_to_send)} items.")

    save_seen(seen)
    print(f"\n✅ Done. Total sent: {total_sent}")

if __name__ == "__main__":
    main()
