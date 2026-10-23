#!/usr/bin/env python3
"""
ZayrenYouTubeBot
----------------
ربات تلگرامی که ویدیوهای جدید (لانگ و شورت) یوتیوب را به کانال تلگرام می‌فرستد.

اجرا روی GitHub Actions هر ۱۵ دقیقه. حالت ذخیره‌شده در bot_state.json نگهداری می‌شود.
"""

import html
import json
import logging
import os
import random
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("zayren-bot")

# ----------------------------------------------------------------------------
# تنظیمات
# ----------------------------------------------------------------------------

STATE_FILE = Path(os.environ.get("STATE_FILE", "bot_state.json"))
YOUTUBE_URL = "https://www.youtube.com/@Zayren666"
YOUTUBE_SUBSCRIBE_URL = YOUTUBE_URL + "?sub_confirmation=1"
BOT_NAME = "زایرن‌بات"

MAX_AGE_DAYS = 7          # ویدیوهای قدیمی‌تر از این تعداد روز، دیگر ارسال نمی‌شوند
MAX_POSTS_PER_RUN = 5     # سقف ارسال در هر اجرا (ضد اسپم)
FUN_MIN_HOURS = 48        # حداقل فاصله دو پست فان تصادفی
FUN_CHANCE = 0.10         # احتمال ارسال پست فان در هر اجرا (بعد از گذشت فاصله)
TEHRAN = timezone(timedelta(hours=3, minutes=30))

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})


def env(name, default=""):
    """مقدار متغیر محیطی؛ مقدار خالی هم مثل «تنظیم‌نشده» حساب می‌شود."""
    return (os.environ.get(name) or default).strip()


def flag(name):
    return env(name).lower() in ("1", "true", "yes", "y", "on")


class ConfigError(Exception):
    """خطای تنظیمات (توکن، کانال، دسترسی ادمین و ...)."""


class TelegramError(Exception):
    pass


def normalize_chat(value):
    """@name ، t.me/name و https://t.me/name همه قبول می‌شوند."""
    value = (value or "").strip()
    if not value:
        return "@Zayren6666"
    m = re.match(r"^(?:https?://)?(?:www\.)?t\.me/(?:s/)?([A-Za-z0-9_]{4,})/?$", value)
    if m:
        return "@" + m.group(1)
    if re.fullmatch(r"-?\d+", value):
        return value
    if not value.startswith("@"):
        value = "@" + value
    return value


# ----------------------------------------------------------------------------
# متن‌های رندوم و فان
# ----------------------------------------------------------------------------

HEADERS_LONG = [
    "🎬 ویدیوی جدید زایرن رسید!",
    "🚨 آپلود جدید! زایرن دوباره زد توی خال",
    "🔥 تازه‌ترین ویدیوی زایرن، داغِ داغ!",
    "🍿 پاپ‌کورن آماده؟ ویدیوی جدید اومد!",
    "🎮 لشکر زایرن، وقت تجمعه!",
    "⚡ سکوت شکسته شد؛ ویدیوی جدید منتشر شد!",
    "👀 هی رفیق! این یکی رو باید ببینی!",
    "🛎️ زنگ خبر! زایرن ویدیو گذاشت!",
]
HEADERS_SHORT = [
    "⚡ شورت جدید زایرن!",
    "📱 یه شورت سریع و خفن رسید!",
    "💥 کمتر از یه دقیقه، پر از انرژی!",
    "🏃 سریع ببین، زود تموم میشه!",
    "🎯 شورتِ تازه، مستقیم به هدف!",
    "🌪️ یه شورتِ طوفانی از زایرن!",
]
HOOKS = [
    "رفیق، از دستش نده؛ همین الان ببینش!",
    "قول میدم پشیمون نمیشی!",
    "اگه حوصله‌ت سر رفته، دقیقاً همینو لازم داشتی 😎",
    "یه لحظه همه‌چیزو ول کن و ببین!",
    "این یکی فرق داره، خودت ببین!",
    "بدو که همه دیدن، فقط تو مونده‌ای! 😄",
]
ASKS = [
    "💬 نظرت رو زیر ویدیو بنویس.",
    "👍 لایک یادت نره!",
    "🔔 اگه هنوز سابسکرایب نکردی، همین الان وقتشه!",
    "📤 برای رفیقات بفرست تا اونا هم ببینن.",
    "💛 با لایک و حمایتت از زایرن پشتیبانی کن!",
    "🗣️ بگو کدوم قسمتش بیشتر خوشت اومد!",
]
CLOSERS = [
    "🎲 این پیام رو یه بات رندوم نوشت!",
    "🤖 بات هم گاهی هیجان‌زده میشه!",
    "🎰 قالب این پیام شانسی انتخاب شد!",
    "✨ هر بار یه شکل؛ بات من خسته نمیشه!",
    "🪄 جادوی رندوم بات فعال شد!",
]
WATCH_BUTTONS = [
    "▶️ تماشای ویدیو",
    "🍿 پخش کن!",
    "🔥 بزن بریم ببینیم",
    "👀 همین الان ببین",
    "🎬 برو به یوتیوب",
]
CHANNEL_BUTTONS = [
    "📺 کانال یوتیوب زایرن",
    "🔔 سابسکرایب کن",
    "💛 حمایت از زایرن",
]

FUN_TEXTS = [
    "🤖 بات تو خدمته! هنوز بیدارم و یوتیوب رو زیر نظر دارم. ویدیوی جدیدی بیاد، اول از همه شما می‌فهمید 😎",
    "🎲 فکت رندوم: بات‌ها هیچ‌وقت نمی‌خوابن، فقط هر ۱۵ دقیقه یه چرت کوچیک می‌زنن 😴",
    "🍿 سؤال روز: بهترین ویدیوی زایرن تا حالا کدوم بوده؟ بنویس تو کامنت‌های یوتیوب!",
    "🔔 یادآوری دوستانه: سابسکرایب و لایک رایگانه، ولی ارزشش برای زایرن طلاست 💛",
    "🧠 اگه ایده‌ای برای ویدیوی بعدی داری، زیر آخرین ویدیو کامنت بذار؛ شاید همونو ساختیم!",
    "🎮 امروز چه بازی‌ای کردی؟ بگو ببینم بات هم یه چیزی یاد بگیره 😄",
]
FUN_POLLS = [
    ("🎬 دوست داری ویدیوهای بعدی چطوری باشن؟",
     ["ویدیوهای بلند و کامل", "شورت‌های سریع", "ترکیبی از هر دو"]),
    ("🤖 بات بیشتر چه شکلی باشه؟",
     ["جدی و مرتب", "شوخ و رندوم", "اصلاً مهم نیست، ویدیو برسه!"]),
    ("⏰ بهترین زمان دیدن ویدیوی جدید؟",
     ["صبح", "عصر", "شب", "هر وقت اومد"]),
]


def pick(options, state, key):
    """رندوم انتخاب می‌کند ولی همان مورد دفعه قبل را تکرار نمی‌کند."""
    last = state.setdefault("last_pick", {})
    choices = [i for i in range(len(options)) if i != last.get(key)] or [0]
    idx = random.choice(choices)
    last[key] = idx
    return options[idx]


# ----------------------------------------------------------------------------
# حالت ذخیره‌شده
# ----------------------------------------------------------------------------

def default_state():
    return {
        "initialized": False,
        "intro_sent": False,
        "seen": [],
        "update_offset": 0,
        "last_fun_post": None,
        "heartbeat": None,
        "last_pick": {},
    }


def load_state():
    state = default_state()
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                state.update(data)
        except (json.JSONDecodeError, OSError):
            log.warning("فایل state خراب بود؛ از صفر شروع می‌شود.")
    return state


def save_state(state):
    state["seen"] = state["seen"][-500:]
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


# ----------------------------------------------------------------------------
# تلگرام
# ----------------------------------------------------------------------------

class Telegram:
    def __init__(self, token):
        self.base = f"https://api.telegram.org/bot{token}"

    def call(self, method, **payload):
        last = None
        for attempt in range(4):
            try:
                resp = HTTP.post(f"{self.base}/{method}", json=payload, timeout=45)
            except requests.RequestException as exc:
                last = f"network error: {exc}"
                time.sleep(2 * (attempt + 1))
                continue
            try:
                data = resp.json()
            except ValueError:
                data = {"ok": False, "description": resp.text[:200]}
            if data.get("ok"):
                return data["result"]
            if resp.status_code == 429:
                wait = int(data.get("parameters", {}).get("retry_after", 5))
                log.warning("Rate limit؛ %s ثانیه صبر می‌کنم.", wait)
                time.sleep(min(wait + 1, 60))
                last = data.get("description")
                continue
            raise TelegramError(
                f"{method} → {data.get('error_code')}: {data.get('description')}"
            )
        raise TelegramError(f"{method} failed after retries: {last}")


def preflight(tg, channel):
    """بررسی توکن، وجود کانال و ادمین بودن بات؛ با پیام‌های فارسی و واضح."""
    try:
        me = tg.call("getMe")
    except TelegramError as exc:
        raise ConfigError(
            f"توکن بات (BOT_TOKEN) اشتباه است یا باطل شده.\n  جزئیات: {exc}"
        )
    log.info("بات متصل شد: @%s", me.get("username"))

    try:
        chat = tg.call("getChat", chat_id=channel)
    except TelegramError as exc:
        raise ConfigError(
            f"کانال «{channel}» پیدا نشد. اسم کانال را درست بنویس (مثلاً @Zayren6666) "
            f"و مطمئن شو بات داخلش ادمین است.\n  جزئیات: {exc}"
        )

    try:
        member = tg.call("getChatMember", chat_id=chat["id"], user_id=me["id"])
    except TelegramError as exc:
        raise ConfigError(f"وضعیت بات در کانال خوانده نشد: {exc}")

    status = member.get("status")
    if status not in ("administrator", "creator"):
        raise ConfigError(
            "بات داخل کانال ادمین نیست. کانال ← Administrators ← Add Admin ← بات را اضافه کن."
        )
    if (
        chat.get("type") == "channel"
        and status == "administrator"
        and member.get("can_post_messages") is False
    ):
        raise ConfigError(
            "بات ادمین است ولی اجازه‌ی «Post Messages» ندارد. این دسترسی را برایش روشن کن."
        )
    return me, chat["id"]


def send_message(tg, chat_id, text, markup=None, preview=False):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": not preview,
    }
    if markup:
        payload["reply_markup"] = markup
    return tg.call("sendMessage", **payload)


# ----------------------------------------------------------------------------
# یوتیوب
# ----------------------------------------------------------------------------

CHANNEL_ID_RE = re.compile(r"UC[0-9A-Za-z_-]{22}")


def resolve_channel_id():
    """از YOUTUBE_CHANNEL_ID یا (اگر نبود) از روی @handle آی‌دی کانال را پیدا می‌کند."""
    raw = env("YOUTUBE_CHANNEL_ID")
    m = CHANNEL_ID_RE.search(raw)
    if m:
        return m.group(0)

    handle = env("YOUTUBE_HANDLE", "@Zayren666")
    if not handle.startswith("@"):
        handle = "@" + handle
    log.info("YOUTUBE_CHANNEL_ID معتبر نبود؛ از روی %s پیدا می‌کنم…", handle)
    try:
        resp = HTTP.get(
            f"https://www.youtube.com/{handle}",
            timeout=30,
            cookies={"CONSENT": "YES+1", "SOCS": "CAI"},
        )
        for pattern in (
            r'"channelId":"(UC[0-9A-Za-z_-]{22})"',
            r'"externalId":"(UC[0-9A-Za-z_-]{22})"',
            r'channel/(UC[0-9A-Za-z_-]{22})',
        ):
            found = re.search(pattern, resp.text)
            if found:
                return found.group(1)
    except requests.RequestException as exc:
        log.warning("پیدا کردن آی‌دی کانال ناموفق بود: %s", exc)
    raise ConfigError(
        "آی‌دی کانال یوتیوب پیدا نشد. Secret با نام YOUTUBE_CHANNEL_ID را بساز "
        "(با UC شروع می‌شود و ۲۴ حرف است)."
    )


def fetch_feed(channel_id):
    urls = [
        f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
        # فید پلی‌لیست آپلودها؛ اگر فید اصلی خطا داد
        f"https://www.youtube.com/feeds/videos.xml?playlist_id=UU{channel_id[2:]}",
    ]
    last = None
    for url in urls:
        for attempt in range(3):
            try:
                resp = HTTP.get(url, timeout=30)
                if resp.status_code == 200 and resp.content:
                    return resp.content
                last = f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                last = str(exc)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"دریافت فید یوتیوب ناموفق بود: {last}")


def parse_feed(content):
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    root = ET.fromstring(content)
    videos = []
    for entry in root.findall("atom:entry", ns):
        vid = entry.findtext("yt:videoId", namespaces=ns)
        if not vid:
            continue
        link = ""
        for el in entry.findall("atom:link", ns):
            if el.get("rel") == "alternate":
                link = el.get("href", "")
        published = entry.findtext("atom:published", default="", namespaces=ns)
        try:
            pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            pub_dt = datetime.now(timezone.utc)
        videos.append({
            "id": vid,
            "title": (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            or "ویدیوی جدید",
            "feed_link": link,
            "published": pub_dt,
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        })
    videos.sort(key=lambda v: v["published"], reverse=True)  # جدیدترین اول
    return videos


def is_short(video):
    """شورت را از لانگ تشخیص می‌دهد."""
    if "/shorts/" in video.get("feed_link", ""):
        return True
    try:
        resp = HTTP.head(
            f"https://www.youtube.com/shorts/{video['id']}",
            allow_redirects=False,
            timeout=15,
            cookies={"CONSENT": "YES+1", "SOCS": "CAI"},
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False


def video_url(video, short):
    kind = "shorts/" if short else "watch?v="
    return f"https://www.youtube.com/{kind}{video['id']}"


# ----------------------------------------------------------------------------
# ساخت و ارسال پیام‌ها
# ----------------------------------------------------------------------------

def build_caption(video, short, state):
    title = video["title"]
    if len(title) > 200:
        title = title[:197] + "…"
    header = pick(HEADERS_SHORT if short else HEADERS_LONG, state, "header")
    hook = pick(HOOKS, state, "hook")
    ask1, ask2 = random.sample(ASKS, 2)
    closer = pick(CLOSERS, state, "closer")
    tags = "#زایرن #Zayren " + ("#شورت #Shorts" if short else "#ویدیو")

    caption = (
        f"<b>{html.escape(header)}</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"{'📱' if short else '🔥'} <b>{html.escape(title)}</b>\n\n"
        f"💥 <b>{html.escape(hook)}</b>\n\n"
        f"{html.escape(ask1)}\n{html.escape(ask2)}\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"{html.escape(closer)}\n"
        f"{html.escape(tags)}"
    )
    return caption[:1024]


def build_keyboard(url, state):
    sub = random.random() < 0.5
    return {
        "inline_keyboard": [
            [{"text": pick(WATCH_BUTTONS, state, "watch"), "url": url}],
            [{
                "text": pick(CHANNEL_BUTTONS, state, "chan"),
                "url": YOUTUBE_SUBSCRIBE_URL if sub else YOUTUBE_URL,
            }],
        ]
    }


def publish_video(tg, chat_id, video, state):
    short = is_short(video)
    url = video_url(video, short)
    caption = build_caption(video, short, state)
    keyboard = build_keyboard(url, state)
    try:
        tg.call(
            "sendPhoto",
            chat_id=chat_id,
            photo=video["thumbnail"],
            caption=caption,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except TelegramError as exc:
        # اگر مشکل از عکس بود، بدون عکس بفرست
        log.warning("sendPhoto خطا داد (%s)؛ بدون تصویر می‌فرستم.", exc)
        send_message(tg, chat_id, caption + f"\n\n{html.escape(url)}", keyboard, preview=True)
    log.info("ارسال شد: %s (%s) %s", video["id"], "شورت" if short else "لانگ", video["title"])
    return short


def intro_text():
    return (
        f"👋 <b>سلام! من {BOT_NAME} هستم، بات رسمی کانال زایرن 🤖</b>\n"
        "━━━━━━━━━━━━━━\n\n"
        "🎯 <b>کارم چیه؟</b>\n"
        "کانال یوتیوب زایرن رو شبانه‌روز زیر نظر دارم و هر ویدیوی جدید "
        "(چه <b>لانگ</b> چه <b>شورت</b>) رو سریع اینجا برات می‌فرستم.\n\n"
        "🎲 <b>رفتارم چطوره؟</b>\n"
        "کاملاً رندوم و بامزه! هر بار با یه تیتر، یه جمله و یه دکمه‌ی متفاوت میام. "
        "گاهی هم بدون هیچ دلیلی یه پیام فان یا نظرسنجی می‌ذارم 😄\n\n"
        "💬 <b>می‌خوای باهام حرف بزنی؟</b>\n"
        "توی پی‌وی بهم /start یا /help یا /latest بفرست.\n\n"
        "💛 فقط کافیه نوتیفیکیشن کانال رو روشن نگه داری!"
    )


def intro_keyboard():
    return {"inline_keyboard": [[{"text": "📺 کانال یوتیوب زایرن", "url": YOUTUBE_SUBSCRIBE_URL}]]}


def send_intro(tg, chat_id):
    msg = send_message(tg, chat_id, intro_text(), intro_keyboard())
    try:
        tg.call("pinChatMessage", chat_id=chat_id, message_id=msg["message_id"],
                disable_notification=True)
    except TelegramError as exc:
        log.info("پین نشد (مهم نیست): %s", exc)
    log.info("پیام معرفی بات ارسال شد.")


# ----------------------------------------------------------------------------
# دستورهای پی‌وی (/start و ...)
# ----------------------------------------------------------------------------

def handle_commands(tg, state, videos):
    """پیام‌های خصوصی را می‌خواند و جواب می‌دهد (با تأخیر حداکثر ۱۵ دقیقه)."""
    try:
        updates = tg.call(
            "getUpdates",
            offset=state.get("update_offset", 0),
            timeout=0,
            limit=50,
            allowed_updates=["message"],
        )
    except TelegramError as exc:
        log.warning("خواندن پیام‌های خصوصی ممکن نشد: %s", exc)
        return

    for upd in updates:
        state["update_offset"] = upd["update_id"] + 1
        msg = upd.get("message") or {}
        text = (msg.get("text") or "").strip()
        chat = msg.get("chat") or {}
        if chat.get("type") != "private" or not text.startswith("/"):
            continue
        cmd = text.split()[0].split("@")[0].lower()
        try:
            if cmd in ("/start", "/help", "/about"):
                send_message(tg, chat["id"], intro_text(), intro_keyboard())
            elif cmd == "/latest" and videos:
                v = videos[0]
                url = video_url(v, is_short(v))
                send_message(
                    tg, chat["id"],
                    f"🎬 آخرین ویدیوی زایرن:\n<b>{html.escape(v['title'])}</b>\n{html.escape(url)}",
                    preview=True,
                )
            elif cmd == "/fun":
                send_message(tg, chat["id"], random.choice(FUN_TEXTS))
            else:
                send_message(tg, chat["id"], "🤔 این دستور رو بلد نیستم. /help رو امتحان کن!")
        except TelegramError as exc:
            log.warning("جواب به کاربر ممکن نشد: %s", exc)


# ----------------------------------------------------------------------------
# پست فان تصادفی
# ----------------------------------------------------------------------------

def maybe_fun_post(tg, chat_id, state):
    if flag("DISABLE_FUN_POSTS"):
        return False
    now = datetime.now(timezone.utc)
    last = state.get("last_fun_post")
    if last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(hours=FUN_MIN_HOURS):
                return False
        except ValueError:
            pass
    else:
        state["last_fun_post"] = now.isoformat()
        return False
    if not 10 <= now.astimezone(TEHRAN).hour < 22:
        return False  # شب‌ها مزاحم نشو
    if random.random() >= FUN_CHANCE:
        return False

    if random.random() < 0.35:
        question, options = random.choice(FUN_POLLS)
        tg.call("sendPoll", chat_id=chat_id, question=question,
                options=options, is_anonymous=True)
    else:
        send_message(tg, chat_id, random.choice(FUN_TEXTS))
    state["last_fun_post"] = now.isoformat()
    log.info("پست فان تصادفی ارسال شد.")
    return True


# ----------------------------------------------------------------------------
# منطق اصلی
# ----------------------------------------------------------------------------

def latest_long_and_short(videos):
    """جدیدترین ویدیوی لانگ و جدیدترین شورت را برمی‌گرداند."""
    long_v = short_v = None
    for v in videos:  # جدیدترین اول
        if long_v and short_v:
            break
        if is_short(v):
            short_v = short_v or v
        else:
            long_v = long_v or v
    return [x for x in (long_v, short_v) if x]


def run():
    token = env("BOT_TOKEN")
    if not token:
        raise ConfigError(
            "Secret با نام BOT_TOKEN تنظیم نشده. "
            "Settings ← Secrets and variables ← Actions ← New repository secret"
        )
    channel = normalize_chat(env("TELEGRAM_CHANNEL", "@Zayren6666"))
    tg = Telegram(token)
    _, chat_id = preflight(tg, channel)

    channel_id = resolve_channel_id()
    videos = parse_feed(fetch_feed(channel_id))
    log.info("%d ویدیو در فید یوتیوب پیدا شد.", len(videos))

    state = load_state()
    before = json.dumps(state, sort_keys=True)
    errors = []

    try:
        force_latest = flag("FORCE_LATEST")
        force_intro = flag("FORCE_INTRO")

        # --- معرفی بات (فقط یک بار، یا با درخواست دستی)
        if not state["intro_sent"] or force_intro:
            send_intro(tg, chat_id)
            state["intro_sent"] = True

        # --- اجرای اول (یا درخواست دستی): آخرین لانگ و شورت را بفرست
        if (not state["initialized"] or force_latest) and videos:
            batch = latest_long_and_short(videos)
            batch.sort(key=lambda v: v["published"])  # قدیمی‌تر اول، تا جدیدترین پایین باشد
            for v in batch:
                publish_video(tg, chat_id, v, state)
            state["seen"] = list(dict.fromkeys(state["seen"] + [v["id"] for v in videos]))
            state["initialized"] = True
            log.info("اجرای اول: آخرین ویدیوی لانگ و شورت ارسال شد.")
        else:
            # --- حالت عادی: فقط ویدیوهای جدید
            seen = set(state["seen"])
            cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
            fresh = [v for v in reversed(videos) if v["id"] not in seen]  # قدیمی‌تر اول
            posted = 0
            for v in fresh:
                if v["published"] < cutoff:
                    state["seen"].append(v["id"])  # خیلی قدیمی؛ فقط ثبت شود
                    continue
                if posted >= MAX_POSTS_PER_RUN:
                    log.info("سقف ارسال این اجرا پر شد؛ بقیه نوبت بعد.")
                    break
                publish_video(tg, chat_id, v, state)
                state["seen"].append(v["id"])
                save_state(state)
                posted += 1
            if posted == 0:
                log.info("ویدیوی جدیدی نیست.")
                maybe_fun_post(tg, chat_id, state)

        handle_commands(tg, state, videos)

    except Exception as exc:  # noqa: BLE001
        errors.append(exc)
        log.error("خطا: %s", exc)
    finally:
        # ضربان: هر ~۲۰ روز یک بار فایل را تغییر می‌دهیم تا گیت‌هاب
        # به‌خاطر بی‌فعالیتی، اجرای زمان‌بندی‌شده را غیرفعال نکند.
        today = datetime.now(timezone.utc).date()
        hb = state.get("heartbeat")
        try:
            stale = not hb or (today - datetime.fromisoformat(hb).date()).days >= 20
        except ValueError:
            stale = True
        if stale:
            state["heartbeat"] = today.isoformat()
        if json.dumps(state, sort_keys=True) != before:
            save_state(state)

    if errors:
        raise errors[0]


def main():
    try:
        run()
    except ConfigError as exc:
        log.error("❌ مشکل تنظیمات:\n  %s", exc)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        log.error("❌ خطا: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
