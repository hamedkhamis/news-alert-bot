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

FEEDS = [
    # SEO & Digital Marketing
    "https://feeds.feedburner.com/Moz",
    "https://searchengineland.com/feed",
    "https://searchenginejournal.com/feed",
    "https://www.semrush.com/blog/feed/",
    "https://ahrefs.com/blog/feed/",
    "https://neilpatel.com/blog/feed/",
    "https://backlinko.com/feed",
    # AI & Tech
    "https://feeds.feedburner.com/venturebeat/SZYF",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://wired.com/feed/rss",
    # Marketing & Soft Skills
    "https://feeds.feedburner.com/hubspot/blog",
    "https://hbr.org/feed",
    "https://feeds.feedblitz.com/marketingprofs",
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

    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:20]:
                link = entry.get("link", "")
                title = entry.get("title", "")
                published = entry.get("published_parsed", None)

                try:
                    source = entry.source.title
                except:
                    source = feed.feed.get("title", "Unknown")

                # فیلتر بر اساس کیورد
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
            print(f"  Error: {feed_url} → {e}")

    return new_items

def main():
    seen = load_seen()
    total_sent = 0

    for keyword in KEYWORDS:
        print(f"\n🔍 Checking: {keyword}")
        new_items = check_keyword(keyword, seen)

        if not new_items:
            # Google News به عنوان fallback
            try:
                q = requests.utils.quote(keyword)
                url = f"https://news.google.com/rss/search?q={q}&hl=en&gl=US&ceid=US:en"
                feed = feedparser.parse(url)
                for entry in feed.entries[:10]:
                    link = entry.get("link", "")
                    title = entry.get("title", "")
                    published = entry.get("published_parsed", None)
                    try:
                        source = entry.source.title
                    except:
                        source = "Google News"
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
                print(f"  Google News error: {e}")

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
