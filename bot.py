import feedparser
import requests
import json
import os
from datetime import datetime, timezone
import time

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
SEEN_FILE = "seen.json"

KEYWORDS = [
    "SEO",
    "Digital Marketing",
    "Soft Skills",
    "Artificial Intelligence",
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

def fetch_google_news(keyword):
    q = requests.utils.quote(f'"{keyword}" when:1d')
    feeds = [
        f"https://news.google.com/rss/search?q={q}&hl=en&gl=US&ceid=US:en",
        f"https://news.google.com/rss/search?q={requests.utils.quote(keyword)}&hl=en&gl=US&ceid=US:en&sort=date",
    ]
    items = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                published = entry.get("published_parsed", None)
                try:
                    source = entry.source.title
                except:
                    source = "Google News"

                if link:
                    date_str = datetime(*published[:6]).strftime("%Y-%m-%d") if published else "N/A"
                    ago = time_ago(published) if published else "recently"
                    items.append({
                        "title": title,
                        "link": link,
                        "source": source,
                        "date": date_str,
                        "ago": ago,
                        "published": published,
                    })
        except Exception as e:
            print(f"  Feed error: {e}")

    # مرتب‌سازی بر اساس جدیدترین
    items.sort(key=lambda x: x["published"] if x["published"] else (2000,1,1,0,0,0), reverse=True)

    # حذف تکراری‌ها
    seen_titles = set()
    unique = []
    for item in items:
        if item["link"] not in seen_titles:
            seen_titles.add(item["link"])
            unique.append(item)

    return unique

def main():
    seen = load_seen()
    total_sent = 0

    for keyword in KEYWORDS:
        print(f"\n🔍 Checking: {keyword}")
        all_items = fetch_google_news(keyword)

        new_items = []
        for item in all_items:
            if item["link"] not in seen:
                seen[item["link"]] = True
                new_items.append(item)

        if not new_items:
            print(f"  No new results.")
            continue

        items_to_send = new_items[:5]
        number_emojis = ["1⃣","2⃣","3⃣","4⃣","5⃣"]

        header = f"🔔 <b>{len(items_to_send)} new results for #{keyword.replace(' ', '_')}</b>\n\n"
        message = header

        for i, item in enumerate(items_to_send, 1):
            num = number_emojis[i-1]
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
