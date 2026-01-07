import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
import requests
# === ایمپورت کتابخانه برای خواندن فایل .env ===
from dotenv import load_dotenv
import os

from pathlib import Path

# ساخت مسیر کامل به فایل .env کنار فایل فعلی
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)
print(f"✅ در حال خواندن فایل .env از: {env_path}")

# === خواندن مقادیر محرمانه از محیط ===
BOT_TOKEN = os.getenv("BOT_TOKEN")  # مقدار "BOT_TOKEN" از فایل .env خوانده می‌شود
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")

# === بررسی که حتما مقادیر خوانده شده‌اند (اختیاری ولی توصیه شده) ===
if not all([BOT_TOKEN, COINGECKO_API_KEY, CHANNEL_USERNAME]):
    raise ValueError("❌ یک یا چند متغیر ضروری در فایل .env تعریف نشده‌اند.")
COMPARING = 1

# تنظیمات لاگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== توابع کمکی ====================
async def is_user_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت کاربر در کانال اجباری."""
    try:
        chat_member = await context.bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id
        )
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"خطا در بررسی عضویت کانال: {e}")
        return False

def get_crypto_price(coin_id="bitcoin"):
    """دریافت قیمت ارز دیجیتال از CoinGecko API."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "x_cg_demo_api_key": COINGECKO_API_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if coin_id in data and "usd" in data[coin_id]:
            return data[coin_id]["usd"]
        else:
            logger.warning(f"ارز {coin_id} در پاسخ API یافت نشد.")
            return None
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت {coin_id}: {e}")
        return None

# ==================== مدیریت مکالمه مقایسه ====================
async def price_compare_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند مقایسه - مرحله اول."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "برای مقایسه، لطفاً نام دو ارز را با فاصله وارد کنید.\n\n"
        "مثال:\n"
        "• `bitcoin ethereum`\n"
        "• `solana cardano`\n\n"
        "از نام انگلیسی ارزها استفاده کنید.\n\n"
        "❌ برای لغو: /cancel",
        parse_mode="Markdown"
    )
    
    # ورود به حالت مقایسه
    return COMPARING

async def compare_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش ورودی کاربر در حالت مقایسه - مرحله دوم."""
    user_input = update.message.text.strip().lower()
    
    # بررسی لغو
    if user_input == "/cancel":
        await update.message.reply_text("✅ عملیات مقایسه لغو شد.")
        return ConversationHandler.END
    
    # تجزیه ورودی کاربر
    parts = user_input.split()
    
    if len(parts) < 2:
        await update.message.reply_text(
            "❌ لطفاً نام **دو** ارز را با فاصله وارد کنید.\n"
            "مثال: `bitcoin ethereum`\n\n"
            "برای لغو: /cancel",
            parse_mode="Markdown"
        )
        return COMPARING  # همچنان در حالت مقایسه باقی بمان
    
    coin1, coin2 = parts[0], parts[1]
    
    # دریافت قیمت‌ها
    await update.message.reply_text("⏳ در حال دریافت قیمت‌ها...")
    
    price1 = get_crypto_price(coin1)
    price2 = get_crypto_price(coin2)
    
    # بررسی نتایج
    if price1 is None or price2 is None:
        error_msg = "❌ دریافت قیمت برای ارز(های) زیر ناموفق بود:\n"
        if price1 is None:
            error_msg += f"• `{coin1}`\n"
        if price2 is None:
            error_msg += f"• `{coin2}`\n"
        error_msg += "\nلطفاً از نام انگلیسی استاندارد استفاده کنید.\n\nبرای تلاش مجدد، دو ارز را وارد کنید:"
        
        await update.message.reply_text(error_msg, parse_mode="Markdown")
        return COMPARING
    
    # محاسبه و نمایش نتیجه
    ratio = price1 / price2 if price2 != 0 else 0
    
    message = (
        f"⚖️ **مقایسه قیمت**\n\n"
        f"• **{coin1.upper()}**: ${price1:,.2f}\n"
        f"• **{coin2.upper()}**: ${price2:,.2f}\n\n"
        f"📊 **نسبت قیمت**:\n"
        f"1 {coin1.upper()} = {ratio:.6f} {coin2.upper()}\n"
        f"1 {coin2.upper()} = {1/ratio:.6f} {coin1.upper() if ratio != 0 else 0}\n\n"
        f"🔄 برای مقایسه جدید، از منوی اصلی استفاده کنید."
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 مقایسه دو ارز دیگر", callback_data="price_compare")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    
    # خروج از حالت مکالمه
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لغو عملیات جاری."""
    await update.message.reply_text("✅ عملیات کنونی لغو شد.")
    return ConversationHandler.END

# ==================== دستورات اصلی ربات ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /start - اولین تعامل کاربر."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # بررسی عضویت در کانال
    if not await is_user_member(user_id, context):
        keyboard = [
            [InlineKeyboardButton("🔗 عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
            [InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_membership")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"سلام {user_name}! 👋\n\n"
            "برای استفاده از ربات، **لطفاً ابتدا در کانال ما عضو شوید**.\n"
            "پس از عضویت، روی دکمه «بررسی عضویت» کلیک کنید.",
            reply_markup=reply_markup
        )
        return
    
    # نمایش منوی اصلی
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی اصلی ربات."""
    keyboard = [
        [InlineKeyboardButton("💰 قیمت ارز دیجیتال", callback_data="price_single")],
        [InlineKeyboardButton("⚖️ مقایسه دو ارز", callback_data="price_compare")],
        [InlineKeyboardButton("📈 قیمت‌های محبوب", callback_data="popular_prices")],
        [InlineKeyboardButton("ℹ️ راهنما", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("🤖 **منوی اصلی ربات قیمت‌یاب**", reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "🤖 **منوی اصلی ربات قیمت‌یاب**",
            reply_markup=reply_markup
        )

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بررسی مجدد عضویت کاربر در کانال."""
    query = update.callback_query
    await query.answer()
    
    if await is_user_member(query.from_user.id, context):
        await query.edit_message_text("✅ عالی! شما عضو کانال هستید. اکنون می‌توانید از ربات استفاده کنید.")
        await show_main_menu(update, context)
    else:
        await query.edit_message_text(
            "❌ هنوز در کانال عضو نشده‌اید.\n"
            "لطفاً ابتدا عضویت خود را تکمیل کنید."
        )

async def price_single_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منوی دریافت قیمت تک ارز."""
    query = update.callback_query
    await query.answer()
    
    popular_coins = {
        "bitcoin": "بیت‌کوین (BTC)",
        "ethereum": "اتریوم (ETH)",
        "tether": "تتر (USDT)",
        "cardano": "کاردانو (ADA)",
        "solana": "سولانا (SOL)",
        "ripple": "ریپل (XRP)",
        "polkadot": "پولکادات (DOT)"
    }
    
    keyboard = []
    for coin_id, coin_name in popular_coins.items():
        keyboard.append([InlineKeyboardButton(f"{coin_name}", callback_data=f"price_{coin_id}")])
    
    keyboard.append([InlineKeyboardButton("🔍 جستجوی ارز دیگر", callback_data="search_coin")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "🎯 ارز مورد نظر خود را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def show_coin_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش قیمت یک ارز خاص."""
    query = update.callback_query
    await query.answer()
    
    coin_id = query.data.replace("price_", "")
    price = get_crypto_price(coin_id)
    
    if price:
        formatted_price = f"{price:,.2f}"
        message = f"💰 **قیمت {coin_id.capitalize()}**\n\n📊 **${formatted_price}** USD"
        
        keyboard = [
            [InlineKeyboardButton("🔄 دریافت مجدد قیمت", callback_data=f"price_{coin_id}")],
            [InlineKeyboardButton("⚖️ مقایسه با ارز دیگر", callback_data=f"compare_{coin_id}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="price_single")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await query.edit_message_text(
            f"❌ دریافت قیمت `{coin_id}` ناموفق بود.\n"
            f"لطفاً دقایقی دیگر تلاش کنید.",
            parse_mode="Markdown"
        )

async def show_popular_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش قیمت‌های ارزهای محبوب."""
    query = update.callback_query
    await query.answer()
    
    popular_coins = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "tether": "USDT",
        "binancecoin": "BNB",
        "solana": "SOL",
        "ripple": "XRP",
        "cardano": "ADA"
    }
    
    message = "📊 **قیمت‌های لحظه‌ای ارزهای محبوب:**\n\n"
    
    for coin_id, symbol in popular_coins.items():
        price = get_crypto_price(coin_id)
        if price:
            message += f"• **{symbol}**: ${price:,.2f}\n"
        else:
            message += f"• **{symbol}**: نامعلوم\n"
    
    message += "\n⏳ آخرین بروزرسانی: لحظاتی پیش"
    
    keyboard = [
        [InlineKeyboardButton("🔄 بروزرسانی قیمت‌ها", callback_data="popular_prices")],
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode="Markdown", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /help - راهنمای ربات."""
    help_text = (
        "📖 **راهنمای ربات قیمت‌یاب**\n\n"
        "🔹 **دستورات اصلی:**\n"
        "• /start - راه‌اندازی ربات\n"
        "• /help - نمایش این راهنما\n"
        "• /cancel - لغو عملیات جاری\n\n"
        "🔹 **امکانات ربات:**\n"
        "• 💰 دریافت قیمت لحظه‌ای ارزهای دیجیتال\n"
        "• ⚖️ مقایسه نسبت قیمت دو ارز (مثل باسکول)\n"
        "• 📈 مشاهده لیست قیمت‌های محبوب\n\n"
        "🔹 **نکات مهم:**\n"
        "• قیمت‌ها به دلار (USD) نمایش داده می‌شوند.\n"
        "• داده‌ها از CoinGecko دریافت می‌شوند.\n"
        "• برای جستجو از نام انگلیسی ارزها استفاده کنید.\n\n"
        "⚠️ **توجه:** برای استفاده از ربات، عضویت در کانال ما ضروری است."
    )
    
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

async def handle_search_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت درخواست جستجوی ارز."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 لطفاً نام انگلیسی ارز مورد نظر را وارد کنید:\n\n"
        "مثال: `dogecoin` یا `litecoin`\n\n"
        "برای لغو: /cancel",
        parse_mode="Markdown"
    )
    
    # ذخیره وضعیت برای دریافت ورودی بعدی
    context.user_data["awaiting_coin_search"] = True

async def handle_coin_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پردازش جستجوی ارز توسط کاربر."""
    if not context.user_data.get("awaiting_coin_search", False):
        return
    
    coin_id = update.message.text.strip().lower()
    price = get_crypto_price(coin_id)
    
    if price:
        formatted_price = f"{price:,.2f}"
        message = f"💰 **قیمت {coin_id.capitalize()}**\n\n📊 **${formatted_price}** USD"
        
        keyboard = [
            [InlineKeyboardButton("🔄 دریافت مجدد", callback_data=f"price_{coin_id}")],
            [InlineKeyboardButton("⚖️ مقایسه با ارز دیگر", callback_data=f"compare_{coin_id}")],
            [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(
            f"❌ ارز `{coin_id}` یافت نشد.\n"
            f"لطفاً نام انگلیسی صحیح ارز را وارد کنید.\n\n"
            f"برای تلاش مجدد، نام ارز را وارد کنید:",
            parse_mode="Markdown"
        )
    
    # پاک کردن وضعیت جستجو
    context.user_data["awaiting_coin_search"] = False

# ==================== مدیریت دکمه‌ها ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌های اینلاین."""
    query = update.callback_query
    callback_data = query.data
    
    logger.info(f"دکمه کلیک شده: {callback_data}")
    
    # مسیریابی بر اساس callback_data
    if callback_data == "check_membership":
        await check_membership(update, context)
    elif callback_data == "price_single":
        await price_single_menu(update, context)
    elif callback_data == "popular_prices":
        await show_popular_prices(update, context)
    elif callback_data == "help":
        await help_command(update, context)
    elif callback_data == "back_to_menu":
        await show_main_menu(update, context)
    elif callback_data == "search_coin":
        await handle_search_request(update, context)
    elif callback_data.startswith("price_"):
        await show_coin_price(update, context)
    elif callback_data.startswith("compare_"):
        # شروع مقایسه با یک ارز از پیش انتخاب شده
        base_coin = callback_data.replace("compare_", "")
        context.user_data["base_coin"] = base_coin
        await query.edit_message_text(
            f"⚖️ مقایسه {base_coin.upper()} با:\n\n"
            f"لطفاً نام ارز دوم را وارد کنید:\n"
            f"مثال: `ethereum`\n\n"
            f"برای لغو: /cancel",
            parse_mode="Markdown"
        )
        context.user_data["awaiting_compare_coin"] = True

# ==================== تابع اصلی ====================
def main():
    """تابع اصلی اجرای ربات."""
    # ساخت اپلیکیشن
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ثبت هندلر مکالمه برای مقایسه
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(price_compare_menu, pattern="^price_compare$")],
        states={
            COMPARING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, compare_input)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # ثبت هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel))
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # هندلر برای جستجوی ارز
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_coin_search
    ))
    
    # شروع ربات
    print("=" * 50)
    print("🤖 ربات قیمت‌یاب ارز دیجیتال فعال شد")
    print("📞 برای خروج: Ctrl + C")
    print("=" * 50)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()