#!/usr/bin/env python3
"""
🇧🇩 Bangladesh Free Temp Number Telegram Bot — Updated
========================================================
✅ সম্পূর্ণ বিনামূল্যে | কোনো account বা payment লাগবে না
✅ নিচে সবসময় Menu Bar থাকবে
✅ "📞 New Number" → নতুন নম্বর
✅ "👁 View OTP" → Real-time OTP দেখায়
✅ One-tap Copy Button
"""

import os
import re
import random
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    BotCommand,
    MenuButtonCommands,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ─── Load env ─────────────────────────────────────────────────────────────────
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_URL     = "https://free-otp-receive.com"
COUNTRY_URL  = f"{BASE_URL}/en/country/bd/"
NUMBER_URL   = f"{BASE_URL}/en/number/bd-{{idx}}/"

BACKUP_URL   = "https://receive-sms.io/temporary-numbers/bangladesh/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

POLL_INTERVAL = 5    # seconds
MAX_WAIT      = 300  # 5 minutes

# ─── Global State ─────────────────────────────────────────────────────────────
# user_id → { "number", "idx", "source", "task", "seen", "latest_sms" }
active: dict[int, dict] = {}


# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTENT BOTTOM MENU  (Reply Keyboard — সবসময় নিচে থাকে)
# ══════════════════════════════════════════════════════════════════════════════

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📞 New Number"),   KeyboardButton("👁 View OTP")],
        [KeyboardButton("📋 Copy Number"),  KeyboardButton("❌ Stop")],
        [KeyboardButton("💰 Balance Info"), KeyboardButton("❓ Help")],
    ],
    resize_keyboard=True,
    persistent=True,
    input_field_placeholder="👇 নিচের menu থেকে বেছে নিন...",
)


# ══════════════════════════════════════════════════════════════════════════════
#  SCRAPING
# ══════════════════════════════════════════════════════════════════════════════

def _fetch(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        logger.warning("fetch %s → %s", url, e)
        return None


def scrape_number_list() -> list[dict]:
    """Return list of { idx, number, status } from free-otp-receive.com"""
    soup = _fetch(COUNTRY_URL)
    if not soup:
        return _scrape_backup_list()

    results = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"/en/number/bd-\d+/")):
        m = re.search(r"/bd-(\d+)/", a["href"])
        if not m:
            continue
        idx  = int(m.group(1))
        text = a.get_text(" ", strip=True)
        ph   = re.search(r"(\+880[\d\s\-]+)", text)
        if not ph:
            continue
        phone  = re.sub(r"[\s\-]", "", ph.group(1))
        status = "Offline" if "Offline" in text else "Active"
        if phone not in seen:
            seen.add(phone)
            results.append({"idx": idx, "number": phone, "status": status})

    return sorted(results, key=lambda x: x["idx"])


def _scrape_backup_list() -> list[dict]:
    soup = _fetch(BACKUP_URL)
    if not soup:
        return []
    results = []
    for a in soup.find_all("a", href=re.compile(r"/temporary-numbers/bangladesh/\d+")):
        m = re.search(r"/(\d+)/?$", a["href"])
        if m:
            results.append({"idx": 0, "number": "+" + m.group(1), "status": "Active"})
    return results


def scrape_inbox(idx: int) -> list[dict]:
    """Scrape latest SMS from the number's inbox page."""
    url  = NUMBER_URL.format(idx=idx)
    soup = _fetch(url)
    if not soup:
        return []

    messages = []
    # Every code block has pattern: `Code: XXXX`
    for code_tag in soup.find_all(string=re.compile(r"Code:\s*\d+")):
        parent = code_tag.parent
        # Walk up 6 levels to capture the full message block
        block = parent
        for _ in range(6):
            if block is None:
                break
            block = block.parent

        if block is None:
            continue

        full = block.get_text(" ", strip=True)

        # Extract OTP code
        code_m = re.search(r"Code:\s*(\d+)", full)
        code   = code_m.group(1) if code_m else ""

        # Extract time ago
        time_m = re.search(
            r"(just now|\d+\s*(?:min|sec|hour|second|minute)s?\s*ago|recently)",
            full, re.IGNORECASE
        )
        time_s = time_m.group(0) if time_m else "recently"

        # Sender detection
        sender = _sender(full)

        # Clean message text
        clean = re.sub(r"`Code:\s*\d+`", "", full)
        clean = re.sub(r"\s{2,}", " ", clean).strip()[:350]

        if code:  # Only include SMS that have a code
            messages.append({
                "sender": sender,
                "time":   time_s,
                "text":   clean,
                "code":   code,
            })

    # Also catch SMS without explicit "Code:" label
    for block in soup.select("div, article, li"):
        text = block.get_text(" ", strip=True)
        if len(text) < 15 or len(text) > 500:
            continue
        # Look for 4-8 digit standalone OTP pattern
        otp_m = re.search(r"\b(\d{4,8})\b", text)
        if not otp_m:
            continue
        code = otp_m.group(1)
        # Skip if already captured
        if any(m["code"] == code for m in messages):
            continue
        time_m = re.search(
            r"(just now|\d+\s*(?:min|sec|hour)s?\s*ago|recently)",
            text, re.IGNORECASE
        )
        messages.append({
            "sender": _sender(text),
            "time":   time_m.group(0) if time_m else "recently",
            "text":   text[:350],
            "code":   code,
        })

    # Deduplicate by code
    seen = set()
    unique = []
    for m in messages:
        if m["code"] not in seen:
            seen.add(m["code"])
            unique.append(m)
    return unique


def _sender(text: str) -> str:
    brands = [
        "Telegram","WhatsApp","Facebook","Google","TikTok","Instagram",
        "Amazon","Apple","Binance","Discord","PayPal","Snapchat",
        "Twitter","LinkedIn","Shopee","Grab","Signal","Microsoft",
        "Coinbase","Viber","Steam","Yahoo","Wise","LINE","Uber",
        "Netflix","Spotify","Airbnb","OTP",
    ]
    for b in brands:
        if b.lower() in text.lower():
            return b
    return "Unknown"


# ══════════════════════════════════════════════════════════════════════════════
#  INLINE KEYBOARDS
# ══════════════════════════════════════════════════════════════════════════════

def number_inline_kb(number: str, idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📋 কপি করুন: {number}", callback_data=f"copynum:{number}")],
        [
            InlineKeyboardButton("👁 View OTP", callback_data=f"viewotp:{idx}:{number}"),
            InlineKeyboardButton("🔄 নতুন নম্বর", callback_data="newnum"),
        ],
        [InlineKeyboardButton("❌ বন্ধ করুন", callback_data="stop")],
    ])


def otp_inline_kb(code: str, idx: int, number: str) -> InlineKeyboardMarkup:
    rows = []
    if code:
        rows.append([InlineKeyboardButton(
            f"📋 OTP কপি: {code}", callback_data=f"copyotp:{code}"
        )])
    rows.append([
        InlineKeyboardButton("🔄 Refresh OTP", callback_data=f"viewotp:{idx}:{number}"),
        InlineKeyboardButton("📞 নতুন নম্বর", callback_data="newnum"),
    ])
    rows.append([InlineKeyboardButton("❌ বন্ধ করুন", callback_data="stop")])
    return InlineKeyboardMarkup(rows)


# ══════════════════════════════════════════════════════════════════════════════
#  REAL-TIME POLLING  (background task)
# ══════════════════════════════════════════════════════════════════════════════

async def realtime_poll(user_id: int, idx: int, number: str,
                        context: ContextTypes.DEFAULT_TYPE):
    """
    Polls the inbox every POLL_INTERVAL seconds.
    Sends new OTP messages to the user immediately.
    """
    elapsed  = 0
    seen_set: set[str] = set()

    # Pre-load existing messages (don't re-notify old ones)
    for m in scrape_inbox(idx):
        seen_set.add(m["code"])

    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"⏳ *Real-time SMS monitoring শুরু হয়েছে!*\n\n"
            f"📞 নম্বর: `{number}`\n"
            f"🔄 প্রতি {POLL_INTERVAL} সেকেন্ডে check হচ্ছে...\n\n"
            f"OTP/SMS আসলে সাথে সাথে নিচে দেখাবে।"
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MAIN_MENU,
    )

    while elapsed < MAX_WAIT:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        if user_id not in active:
            return

        msgs = scrape_inbox(idx)
        new_msgs = [m for m in msgs if m["code"] not in seen_set]

        for msg in new_msgs:
            seen_set.add(msg["code"])
            code   = msg["code"]
            sender = msg["sender"]
            text   = msg["text"]
            time_s = msg["time"]

            # Store latest SMS in state
            active[user_id]["latest_sms"] = msg

            notification = (
                f"🔔 *নতুন OTP এসেছে!*\n\n"
                f"📞 *নম্বর:* `{number}`\n"
                f"📤 *প্রেরক:* {sender}\n"
                f"🕐 *সময়:* {time_s}\n\n"
                f"📝 *বার্তা:*\n`{text}`\n\n"
                f"🔑 *OTP কোড:* `{code}`\n\n"
                f"👆 নিচের বোতামে চাপলে কপি হবে!"
            )
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=notification,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=otp_inline_kb(code, idx, number),
                )
            except Exception as e:
                logger.error("poll send err: %s", e)

    # Timeout
    active.pop(user_id, None)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "⏰ *৫ মিনিট শেষ!*\n\n"
                "কোনো SMS আসেনি। নতুন নম্বর নিতে\n"
                "নিচের *📞 New Number* বোতামে চাপুন।"
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU,
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  CORE LOGIC: get a number & start monitoring
# ══════════════════════════════════════════════════════════════════════════════

async def give_new_number(user_id: int, chat_id: int,
                          context: ContextTypes.DEFAULT_TYPE,
                          reply_fn):
    """Pick a random active BD number and start real-time polling."""

    # Cancel existing task
    if user_id in active:
        t = active[user_id].get("task")
        if t and not t.done():
            t.cancel()
        active.pop(user_id)

    # Scrape number list in thread
    loop    = asyncio.get_event_loop()
    numbers = await loop.run_in_executor(None, scrape_number_list)

    active_nums = [n for n in numbers if n["status"] == "Active"]
    if not active_nums:
        await reply_fn(
            "❌ এই মুহূর্তে কোনো সক্রিয় নম্বর নেই।\nকিছুক্ষণ পরে আবার চেষ্টা করুন।"
        )
        return

    # Pick a random active number
    chosen = random.choice(active_nums)
    idx    = chosen["idx"]
    number = chosen["number"]

    # Save state
    active[user_id] = {
        "idx": idx, "number": number,
        "source": "main", "seen": set(),
        "latest_sms": None,
    }

    msg = (
        f"✅ *নতুন বাংলাদেশি নম্বর পেয়েছেন!*\n\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📞 *আপনার নম্বর:*\n"
        f"`{number}`\n"
        f"━━━━━━━━━━━━━━━━━\n\n"
        f"👆 উপরের নম্বরে ট্যাপ করলেই কপি হবে!\n\n"
        f"📲 এই নম্বরে OTP পাঠান।\n"
        f"📨 OTP আসলে *real-time* এখানে দেখাবে।\n\n"
        f"নিচের মেনু থেকে *👁 View OTP* চাপলে\n"
        f"সর্বশেষ OTP দেখতে পাবেন।"
    )
    await reply_fn(msg, keyboard=number_inline_kb(number, idx))

    # Start real-time polling
    task = asyncio.create_task(realtime_poll(user_id, idx, number, context))
    active[user_id]["task"] = task


# ══════════════════════════════════════════════════════════════════════════════
#  COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🇧🇩 *Bangladesh Free Temp Number Bot*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "✅ সম্পূর্ণ বিনামূল্যে\n"
        "✅ কোনো account লাগবে না\n"
        "✅ Bangladesh (+880) নম্বর\n"
        "✅ Real-time OTP notification\n"
        "✅ One-tap Copy বোতাম\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 *নিচের মেনু বার থেকে শুরু করুন:*\n\n"
        "📞 *New Number* → নতুন নম্বর নিন\n"
        "👁 *View OTP* → সর্বশেষ OTP দেখুন\n"
        "📋 *Copy Number* → নম্বর কপি করুন\n"
        "❌ *Stop* → monitoring বন্ধ করুন\n"
        "❓ *Help* → সাহায্য\n\n"
        "👈 বার্তার বাম দিকের *☰ বোতামেও* সব command আছে!"
    )
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=MAIN_MENU,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ *সাহায্য — Free Temp Number Bot*\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📌 *কীভাবে ব্যবহার করবেন:*\n\n"
        "1️⃣ নিচে *📞 New Number* চাপুন\n"
        "2️⃣ একটা +880 নম্বর আসবে\n"
        "3️⃣ নম্বরে ট্যাপ করলে কপি হবে\n"
        "4️⃣ সেই নম্বরে OTP পাঠান\n"
        "5️⃣ OTP আসলে এখানে সাথে সাথে দেখাবে\n"
        "6️⃣ *👁 View OTP* চাপলে সর্বশেষ OTP দেখবেন\n"
        "7️⃣ OTP copy করে ব্যবহার করুন\n"
        "8️⃣ শেষ হলে *❌ Stop* চাপুন\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *মেনু বোতামের কাজ:*\n\n"
        "📞 New Number — নতুন নম্বর নিন\n"
        "👁 View OTP — সর্বশেষ OTP দেখুন\n"
        "📋 Copy Number — নম্বর কপি করুন\n"
        "❌ Stop — monitoring বন্ধ করুন\n"
        "💰 Balance Info — ব্যবহারের তথ্য\n"
        "❓ Help — এই সাহায্য\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *মনে রাখুন:*\n"
        "• এগুলো public নম্বর\n"
        "• OTP দ্রুত ব্যবহার করুন\n"
        "• ব্যাংক কাজে ব্যবহার করবেন না\n"
    )
    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_MENU
    )


# ══════════════════════════════════════════════════════════════════════════════
#  MENU BUTTON HANDLERS  (Reply Keyboard text messages)
# ══════════════════════════════════════════════════════════════════════════════

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text.strip()
    user_id = update.effective_user.id

    # ── 📞 New Number ─────────────────────────────────────────────────────────
    if "New Number" in text:
        loading = await update.message.reply_text(
            "⏳ বাংলাদেশি নম্বর খোঁজা হচ্ছে...",
            reply_markup=MAIN_MENU,
        )

        async def reply_fn(msg, keyboard=None):
            await loading.edit_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
            )

        await give_new_number(user_id, update.effective_chat.id, context, reply_fn)

    # ── 👁 View OTP ──────────────────────────────────────────────────────────
    elif "View OTP" in text:
        if user_id not in active:
            await update.message.reply_text(
                "⚠️ আপনার কোনো সক্রিয় নম্বর নেই।\n"
                "*📞 New Number* চাপুন আগে।",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_MENU,
            )
            return

        info       = active[user_id]
        idx        = info["idx"]
        number     = info["number"]
        latest_sms = info.get("latest_sms")

        if latest_sms:
            code   = latest_sms["code"]
            sender = latest_sms["sender"]
            text_m = latest_sms["text"]
            time_s = latest_sms["time"]
            msg = (
                f"👁 *সর্বশেষ OTP*\n\n"
                f"📞 *নম্বর:* `{number}`\n"
                f"📤 *প্রেরক:* {sender}\n"
                f"🕐 *সময়:* {time_s}\n\n"
                f"📝 *বার্তা:*\n`{text_m}`\n\n"
                f"🔑 *OTP কোড:* `{code}`\n\n"
                f"👆 নিচের বোতামে চাপলে কপি হবে!"
            )
            await update.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=otp_inline_kb(code, idx, number),
            )
        else:
            # Fetch live from the page
            loading = await update.message.reply_text(
                "🔄 Real-time OTP চেক করা হচ্ছে...",
                reply_markup=MAIN_MENU,
            )
            loop = asyncio.get_event_loop()
            msgs = await loop.run_in_executor(None, scrape_inbox, idx)

            if msgs:
                latest = msgs[0]
                code   = latest["code"]
                active[user_id]["latest_sms"] = latest
                msg = (
                    f"👁 *সর্বশেষ OTP*\n\n"
                    f"📞 *নম্বর:* `{number}`\n"
                    f"📤 *প্রেরক:* {latest['sender']}\n"
                    f"🕐 *সময়:* {latest['time']}\n\n"
                    f"📝 *বার্তা:*\n`{latest['text']}`\n\n"
                    f"🔑 *OTP কোড:* `{code}`"
                )
                await loading.edit_text(
                    msg,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=otp_inline_kb(code, idx, number),
                )
            else:
                await loading.edit_text(
                    f"⏳ *{number}* নম্বরে এখনো কোনো OTP আসেনি।\n\n"
                    f"OTP পাঠান — আসলে real-time এখানে দেখাবে! 🔔",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=MAIN_MENU,
                )

    # ── 📋 Copy Number ────────────────────────────────────────────────────────
    elif "Copy Number" in text:
        if user_id not in active:
            await update.message.reply_text(
                "⚠️ আগে *📞 New Number* চাপুন।",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_MENU,
            )
            return
        number = active[user_id]["number"]
        await update.message.reply_text(
            f"📋 *নম্বর কপি করুন:*\n\n`{number}`\n\n"
            f"👆 উপরের নম্বরে ট্যাপ করলেই কপি হবে!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU,
        )

    # ── ❌ Stop ────────────────────────────────────────────────────────────────
    elif "Stop" in text:
        if user_id not in active:
            await update.message.reply_text(
                "ℹ️ কোনো সক্রিয় নম্বর নেই।",
                reply_markup=MAIN_MENU,
            )
            return
        info = active.pop(user_id)
        t    = info.get("task")
        if t and not t.done():
            t.cancel()
        num = info["number"]
        await update.message.reply_text(
            f"✅ *বন্ধ করা হয়েছে!*\n\n"
            f"`{num}` নম্বরের monitoring বন্ধ।\n\n"
            f"নতুন নম্বর নিতে *📞 New Number* চাপুন।",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU,
        )

    # ── 💰 Balance Info ───────────────────────────────────────────────────────
    elif "Balance" in text:
        user_info = active.get(user_id, {})
        number    = user_info.get("number", "—")
        latest    = user_info.get("latest_sms")
        otp_count = 1 if latest else 0

        msg = (
            "💰 *ব্যবহারের তথ্য*\n\n"
            f"📞 *চলতি নম্বর:* `{number}`\n"
            f"📨 *OTP পাওয়া গেছে:* {otp_count}টি\n\n"
            "━━━━━━━━━━━━━━━━━\n"
            "ℹ️ এই বট সম্পূর্ণ বিনামূল্যে!\n"
            "কোনো balance বা payment নেই।\n"
            "free-otp-receive.com থেকে নম্বর নেওয়া হয়।"
        )
        await update.message.reply_text(
            msg, parse_mode=ParseMode.MARKDOWN, reply_markup=MAIN_MENU
        )

    # ── ❓ Help ────────────────────────────────────────────────────────────────
    elif "Help" in text:
        await cmd_help(update, context)


# ══════════════════════════════════════════════════════════════════════════════
#  INLINE CALLBACK HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    data    = query.data
    user_id = query.from_user.id

    # ── Copy number ──────────────────────────────────────────────────────────
    if data.startswith("copynum:"):
        number = data.split(":", 1)[1]
        await query.message.reply_text(
            f"📋 *নম্বর কপি করুন:*\n\n`{number}`\n\n"
            f"👆 ট্যাপ করলেই কপি হবে!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU,
        )

    # ── Copy OTP ─────────────────────────────────────────────────────────────
    elif data.startswith("copyotp:"):
        code = data.split(":", 1)[1]
        await query.message.reply_text(
            f"📋 *OTP কপি করুন:*\n\n`{code}`\n\n"
            f"👆 ট্যাপ করলেই কপি হবে!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=MAIN_MENU,
        )

    # ── View OTP inline ───────────────────────────────────────────────────────
    elif data.startswith("viewotp:"):
        parts  = data.split(":", 2)
        idx    = int(parts[1])
        number = parts[2]

        await query.message.reply_text("🔄 Real-time OTP check হচ্ছে...")
        loop = asyncio.get_event_loop()
        msgs = await loop.run_in_executor(None, scrape_inbox, idx)

        if msgs:
            latest = msgs[0]
            code   = latest["code"]
            if user_id in active:
                active[user_id]["latest_sms"] = latest
            msg = (
                f"👁 *সর্বশেষ OTP*\n\n"
                f"📞 *নম্বর:* `{number}`\n"
                f"📤 *প্রেরক:* {latest['sender']}\n"
                f"🕐 *সময়:* {latest['time']}\n\n"
                f"📝 *বার্তা:*\n`{latest['text']}`\n\n"
                f"🔑 *OTP:* `{code}`"
            )
            await query.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=otp_inline_kb(code, idx, number),
            )
        else:
            await query.message.reply_text(
                "⏳ এখনো কোনো OTP আসেনি।\nOTP পাঠান — real-time আসবে!",
                reply_markup=MAIN_MENU,
            )

    # ── New number ────────────────────────────────────────────────────────────
    elif data == "newnum":
        loading = await query.message.reply_text(
            "⏳ নতুন নম্বর খোঁজা হচ্ছে..."
        )

        async def reply_fn(msg, keyboard=None):
            await loading.edit_text(
                msg, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
            )

        await give_new_number(
            user_id, query.message.chat_id, context, reply_fn
        )

    # ── Stop ──────────────────────────────────────────────────────────────────
    elif data == "stop":
        if user_id in active:
            info = active.pop(user_id)
            t    = info.get("task")
            if t and not t.done():
                t.cancel()
            num = info["number"]
            await query.message.reply_text(
                f"✅ `{num}` বন্ধ করা হয়েছে।\n"
                f"নতুন নম্বর → *📞 New Number*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=MAIN_MENU,
            )
        else:
            await query.message.reply_text(
                "ℹ️ কোনো সক্রিয় নম্বর নেই।",
                reply_markup=MAIN_MENU,
            )


# ══════════════════════════════════════════════════════════════════════════════
#  BOT INIT & MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def post_init(application: Application) -> None:
    """Register slash commands — shows in ☰ hamburger menu."""
    await application.bot.set_my_commands([
        BotCommand("start",   "🚀 বট শুরু করুন"),
        BotCommand("help",    "❓ সাহায্য দেখুন"),
    ])
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("✅ Bot initialized.")


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "❌ BOT_TOKEN পাওয়া যায়নি!\n"
            ".env ফাইলে BOT_TOKEN=আপনার_token লিখুন।"
        )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Slash command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))

    # Reply keyboard (bottom menu bar) handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_menu,
    ))

    # Inline button handler
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("🤖 Bot চালু হচ্ছে...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
