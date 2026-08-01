import os
import time
import hashlib
import json
import requests
from datetime import datetime, timedelta
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# تنظیمات
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
STATE_FILE = '/tmp/news_state.json'
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
    
    # 2. جستجو در Reddit (اختیاری)
    try:
        reddit_url = f"https://www.reddit.com/search.json?q={keyword}&sort=new&limit=10"
        headers = {'User-Agent': 'NewsBot/1.0'}
        response = requests.get(reddit_url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for post in data.get('data', {}).get('children', []):
                item_data = post.get('data', {})
                title = item_data.get('title', '')
                url = item_data.get('url', '')
                created = datetime.fromtimestamp(item_data.get('created_utc', 0))
                
                if title and url and keyword.lower() in title.lower():
                    news_items.append({
                        'title': f"[Reddit] {title}",
                        'link': url,
                        'pub_date': created.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                        'source': 'Reddit',
                        'id': hashlib.md5(url.encode()).hexdigest()
                    })
    except Exception as e:
        print(f"Error fetching Reddit: {e}")
    
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پیام خوش‌آمدگویی"""
    welcome_message = """
👋 سلام! به ربات اخبار خوش آمدید.

📌 دستورالعمل استفاده:
1️⃣ /start - نمایش این پیام
2️⃣ /setkeyword <کلمه> - تنظیم کلمه کلیدی (مثلاً: /setkeyword تکنولوژی)
3️⃣ /getnews - دریافت اخبار جدید بر اساس کلمه کلیدی شما
4️⃣ /status - مشاهده وضعیت کلمه کلیدی فعلی
5️⃣ /help - راهنمای بیشتر

💡 مثال:
/setkeyword هوش مصنوعی

پس از تنظیم کلمه کلیدی، هر زمان /getnews را بزنید، آخرین اخبار را دریافت خواهید کرد!
"""
    await update.message.reply_text(welcome_message)

async def set_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظیم کلمه کلیدی"""
    if not context.args:
        await update.message.reply_text("❌ لطفاً کلمه کلیدی را وارد کنید.\n\nمثال: /setkeyword تکنولوژی")
        return
    
    keyword = ' '.join(context.args)
    user_id = str(update.effective_user.id)
    
    # ذخیره کلمه کلیدی کاربر
    keywords = load_user_keywords()
    keywords[user_id] = keyword
    save_user_keywords(keywords)
    
    await update.message.reply_text(f"✅ کلمه کلیدی شما تنظیم شد:\n\n🔍 **{keyword}**\n\nحالا می‌توانید از دستور /getnews برای دریافت اخبار استفاده کنید!")

async def get_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت اخبار برای کاربر"""
    user_id = str(update.effective_user.id)
    
    # دریافت کلمه کلیدی کاربر
    keywords = load_user_keywords()
    keyword = keywords.get(user_id)
    
    if not keyword:
        await update.message.reply_text("❌ ابتدا باید کلمه کلیدی خود را تنظیم کنید.\n\nاز دستور زیر استفاده کنید:\n/setkeyword <کلمه کلیدی>\n\nمثال: /setkeyword تکنولوژی")
        return
    
    await update.message.reply_text(f"🔍 در حال جستجوی اخبار برای: **{keyword}**...\n\nلطفاً صبر کنید...")
    
    # دریافت اخبار
    all_news = get_news_sources(keyword)
    
    if not all_news:
        await update.message.reply_text("😔 متأسفانه خبری یافت نشد. لطفاً کلمه کلیدی دیگری امتحان کنید.")
        return
    
    # بارگذاری اخبار قبلی
    sent_news = load_sent_news(user_id)
    
    # فیلتر اخبار جدید
    new_news = [item for item in all_news if item['id'] not in sent_news]
    
    if not new_news:
        await update.message.reply_text("✅ هیچ خبر جدیدی از آخرین بررسی شما وجود ندارد.\n\nبعداً دوباره تلاش کنید!")
        return
    
    # ارسال اخبار
    messages_sent = 0
    for item in new_news[:10]:  # حداکثر ۱۰ خبر
        message = f"""
📰 <b>{item['title']}</b>

🔗 <a href="{item['link']}">لینک خبر</a>
📢 منبع: {item['source']}
⏰ زمان: {item['pub_date']}
"""
        
        try:
            await update.message.reply_text(
                message,
                parse_mode='HTML',
                disable_web_page_preview=False
            )
            sent_news.add(item['id'])
            messages_sent += 1
            time.sleep(1)  # جلوگیری از محدودیت نرخ
        except TelegramError as e:
            print(f"Error sending message: {e}")
            continue
    
    # ذخیره وضعیت
    save_sent_news(user_id, sent_news)
    
    await update.message.reply_text(f"\n✅ تعداد {messages_sent} خبر جدید برای شما ارسال شد!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش وضعیت کلمه کلیدی"""
    user_id = str(update.effective_user.id)
    keywords = load_user_keywords()
    keyword = keywords.get(user_id)
    
    if not keyword:
        await update.message.reply_text("❌ هنوز کلمه کلیدی تنظیم نکرده‌اید.\n\nاز دستور /setkeyword استفاده کنید.")
        return
    
    sent_news = load_sent_news(user_id)
    
    status_message = f"""
📊 وضعیت حساب شما:

🔍 کلمه کلیدی فعلی: <b>{keyword}</b>
📰 تعداد اخبار دریافتی: {len(sent_news)}

💡 برای تغییر کلمه کلیدی:
/setkeyword <کلمه جدید>

📥 برای دریافت اخبار جدید:
/getnews
"""
    await update.message.reply_text(status_message, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """راهنما"""
    help_message = """
🤖 راهنمای ربات اخبار

📌 دستورات موجود:

/start - شروع ربات و نمایش پیام خوش‌آمدگویی

/setkeyword <کلمه> - تنظیم کلمه کلیدی برای جستجوی اخبار
   مثال: /setkeyword هوش مصنوعی

/getnews - دریافت آخرین اخبار بر اساس کلمه کلیدی شما

/status - مشاهده وضعیت کلمه کلیدی و آمار

/help - نمایش این پیام راهنما

💡 نکات مهم:
- کلمه کلیدی می‌تواند فارسی یا انگلیسی باشد
- اخبار تکراری ارسال نمی‌شوند
- حداکثر ۱۰ خبر در هر درخواست ارسال می‌شود
- از منابع معتبر مانند Google News اخبار دریافت می‌شود

🎉 لذت ببرید!
"""
    await update.message.reply_text(help_message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش پیام‌های متنی"""
    text = update.message.text.strip()
    
    # اگر کاربر فقط کلمه کلیدی فرستاد
    if not text.startswith('/'):
        user_id = str(update.effective_user.id)
        keywords = load_user_keywords()
        
        if user_id not in keywords:
            await update.message.reply_text(
                f"به نظر می‌رسد می‌خواهید کلمه کلیدی تنظیم کنید.\n\n"
                f"لطفاً از دستور زیر استفاده کنید:\n"
                f"/setkeyword {text}\n\n"
                f"یا اگر سوالی دارید /help را بزنید."
            )
        else:
            await update.message.reply_text(
                "برای دریافت اخبار از دستور /getnews استفاده کنید.\n"
                "برای تغییر کلمه کلیدی: /setkeyword <کلمه جدید>"
            )

def main():
    """تابع اصلی برای اجرای ربات به صورت interactive"""
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set!")
        return
    
    print(f"Starting Telegram bot at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ساخت برنامه
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # افزودن handlerها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setkeyword", set_keyword))
    application.add_handler(CommandHandler("getnews", get_news))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # شروع ربات
    print("Bot is running... Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
