import feedparser
import requests
import json
import os
from datetime import datetime, timezone
import time
import html

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
SEEN_FILE = "seen.json"

TRUSTED_DOMAINS = [
    "searchengineland.com", "searchenginejournal.com", "semrush.com",
    "ahrefs.com", "moz.com", "backlinko.com", "neilpatel.com",
    "hubspot.com", "contentmarketinginstitute.com", "marketingweek.com",
    "techcrunch.com", "venturebeat.com", "wired.com", "theverge.com",
    "hbr.org", "forbes.com", "entrepreneur.com", "inc.com",
    "adweek.com", "socialmediaexaminer.com", "wordstream.com",
    "sproutsocial.com", "buffer.com", "hootsuite.com",
    "thenextweb.com", "mashable.com", "businessinsider.com",
    "fastcompany.com", "openai.com", "artificialintelligence-news.com",
    "towardsdatascience.com", "medium.com", "designrush.com",
]

KEYWORDS = [
    {
        "label": "SEO",
        "query": "SEO search engine optimization",
    },
    {
        "label": "Digital_Marketing",
        "query": "digital marketing strategy 2026",
    },
    {
        "label": "Soft_Skills",
        "query": "soft skills leadership productivity workplace",
    },
    {
        "label": "Artificial_Intelligence",
        "query": "artificial intelligence AI tools 2026",
    },
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

def is_trusted(link):
    for domain in TRUSTED_DOMAINS:
        if domain in link:
            return True
    return False

def clean_summary(text, max_len=180):
    """تمیز کردن HTML و کوتاه کردن summary"""
    if not text:
        return ""
    # حذف تگ‌های HTML
    import re
    text = re.sub(r'<[^>]+>', '', text)
    # decode HTML entities
    text = html.unescape(text)
    # حذف فاصله‌های اضافه
    text = ' '.join(text.split())
    # کوتاه کردن
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + "..."
    return text.strip()

def fetch_google_news(keyword_obj):
    query = requests.utils.quote(keyword_obj["query"])
    url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"

    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:30]:
            link = entry.get("link", "")
            title = entry.get("title", "")
            published = entry.get("published_parsed", None)

            # summary از فید
            raw_summary = (
                entry.get("summary", "") or
                entry.get("description", "") or
                entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""
            )
            summary = clean_summary(raw_summary)

            # فیلتر منابع نامعتبر
            if not is_trusted(link):
                continue

            # فیلتر SEO نامرتبط
            if keyword_obj["label"] == "SEO":
                title_lower = title.lower()
                if "seo" not in title_lower and "search engine" not in title_lower and "ranking" not in title_lower:
                    continue

            try:
                source = entry.source.title
            except:
                source = feed.feed.get("title", "Google News")

            if link:
                date_str = datetime(*published[:6]).strftime("%Y-%m-%d") if published else "N/A"
                ago = time_ago(published) if published else "recently"
                items.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "date": date_str,
                    "ago": ago,
                    "summary": summary,
                    "published": published,
                })
    except Exception as e:
        print(f"  Feed error: {e}")

    items.sort(
        key=lambda x: x["published"] if x["published"] else (2000,1,1,0,0,0),
        reverse=True
    )

    seen_links = set()
    unique = []
    for item in items:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            unique.append(item)

    return unique

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
    time.sleep(1)

def main():
    seen = load_seen()
    total_sent = 0

    for kw in KEYWORDS:
        print(f"\n🔍 Checking: {kw['label']}")
        all_items = fetch_google_news(kw)

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

        header = f"🔔 <b>{len(items_to_send)} new results for #{kw['label']}</b>\n\n"
        message = header

        for i, item in enumerate(items_to_send, 1):
            num = number_emojis[i-1]
            short_title = item['title'][:120]
            summary_line = f"📝 {item['summary']}\n" if item['summary'] else ""

            message += (
                f"{num} <b>{short_title}</b>\n"
                f"<i>{item['source']}</i> | {item['date']}\n\n"
                f"{summary_line}"
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
