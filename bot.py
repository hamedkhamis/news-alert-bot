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

KEYWORDS = [
    {"label": "SEO", "query": "SEO search engine optimization 2026", "must": ["seo", "search engine", "ranking", "serp", "backlink", "core update"]},
    {"label": "Google_Ads", "query": "Google Ads PPC advertising 2026", "must": ["google ads", "ppc", "paid search", "adwords", "cpc", "roas"]},
    {"label": "Social_Media_Ads", "query": "Facebook Instagram TikTok ads advertising 2026", "must": ["facebook ads", "instagram ads", "tiktok ads", "meta ads", "social ads"]},
    {"label": "Content_Marketing", "query": "content marketing strategy 2026", "must": ["content marketing", "content strategy", "copywriting", "storytelling"]},
    {"label": "Email_Marketing", "query": "email marketing automation 2026", "must": ["email marketing", "newsletter", "email automation", "drip campaign"]},
    {"label": "AI_Tools", "query": "AI tools productivity marketing 2026", "must": ["ai tool", "chatgpt", "claude", "gemini", "llm", "generative ai", "artificial intelligence"]},
    {"label": "MarTech", "query": "marketing technology martech tools 2026", "must": ["martech", "marketing technology", "crm", "automation", "analytics"]},
    {"label": "eCommerce", "query": "ecommerce growth conversion rate optimization 2026", "must": ["ecommerce", "e-commerce", "shopify", "conversion", "cro", "amazon"]},
    {"label": "Social_Media", "query": "social media marketing trends 2026", "must": ["social media", "instagram", "tiktok", "linkedin", "youtube", "influencer"]},
    {"label": "Analytics_Data", "query": "web analytics data marketing 2026", "must": ["analytics", "google analytics", "data", "ga4", "tracking", "attribution"]},
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

def is_relevant(title, must_keywords):
    title_lower = title.lower()
    return any(kw in title_lower for kw in must_keywords)

def clean_summary(text, max_len=200):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = ' '.join(text.split())
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0] + "..."
    return text.strip()

def fetch_news(keyword_obj):
    query = requests.utils.quote(keyword_obj["query"])
    url = f"https://news.google.com/rss/search?q={query}&hl=en&gl=US&ceid=US:en"

    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:50]:
            link = entry.get("link", "")
            title = entry.get("title", "")
            published = entry.get("published_parsed", None)

            if not title or not link:
                continue

            # فیلتر ارتباط
            if not is_relevant(title, keyword_obj["must"]):
                continue

            raw_summary = entry.get("summary", "") or entry.get("description", "")
            summary = clean_summary(raw_summary)

            try:
                source = entry.source.title
            except:
                source = feed.feed.get("title", "Google News")

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
    time.sleep(0.5)

def build_message(label, items):
    """هر ۱۰ تا خبر یه پیام جداگانه"""
    messages = []
    chunk_size = 10
    chunks = [items[i:i+chunk_size] for i in range(0, len(items), chunk_size)]

    number_emojis = ["1⃣","2⃣","3⃣","4⃣","5⃣","6⃣","7⃣","8⃣","9⃣","🔟"]

    for chunk_idx, chunk in enumerate(chunks):
        part = f" (part {chunk_idx+1})" if len(chunks) > 1 else ""
        header = f"🔔 <b>{len(chunk)} new results for #{label}{part}</b>\n\n"
        message = header

        for i, item in enumerate(chunk, 1):
            num = number_emojis[i-1] if i <= 10 else f"{i}."
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

        messages.append(message)
    return messages

def main():
    seen = load_seen()
    total_sent = 0

    for kw in KEYWORDS:
        print(f"\n🔍 Checking: {kw['label']}")
        all_items = fetch_news(kw)

        new_items = []
        for item in all_items:
            if item["link"] not in seen:
                seen[item["link"]] = True
                new_items.append(item)

        if not new_items:
            print(f"  No new results.")
            continue

        print(f"  Found {len(new_items)} new items.")
        messages = build_message(kw["label"], new_items)

        for msg in messages:
            send_message(msg)
            total_sent += 1

        print(f"  ✅ Sent {len(messages)} message(s).")

    save_seen(seen)
    print(f"\n✅ Done. Total messages sent: {total_sent}")

if __name__ == "__main__":
    main()
