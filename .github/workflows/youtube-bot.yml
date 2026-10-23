
import os
import json
import random
import html
import logging
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "@Zayren6666")

FEED_URL = (
    "https://www.youtube.com/feeds/videos.xml"
    f"?channel_id={YOUTUBE_CHANNEL_ID}"
)

STATE_FILE = Path("seen_videos.json")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

INTRO_MESSAGES = [
    "🚨 زایرن برگشته؛ وقتشه بترکونیم!",
    "🍿 خوراکی‌هات رو آماده کن؛ ویدیوی جدید رسید!",
    "🔥 یه آپلود جدید از زایرن؛ از دستش نده!",
    "👀 هی رفیق! این یکی رو باید ببینی!",
    "🎮 لشکر زایرن، وقت تجمعه!",
    "⚡ سکوت شکسته شد؛ ویدیوی جدید منتشر شد!",
    "💛 حمایتت رو دریغ نکن؛ بزن بریم!",
]

def load_seen():
    if not STATE_FILE.exists():
        return []

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        logging.warning("Could not read saved video history.")
        return []


def save_seen(video_ids):
    STATE_FILE.write_text(
        json.dumps(video_ids[-500:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_videos():
    response = requests.get(FEED_URL, timeout=30)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    videos = []

    for entry in root.findall("atom:entry", ns):
        video_id = entry.findtext("yt:videoId", namespaces=ns)
        title = entry.findtext(
            "atom:title",
            default="ویدیوی جدید",
            namespaces=ns,
        )

        if not video_id:
            continue

        videos.append({
            "id": video_id,
            "title": title or "ویدیوی جدید",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": (
                f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
            ),
        })

    return videos


def publish_video(video):
    title = html.escape(video["title"])
    url = html.escape(video["url"], quote=True)
    intro = html.escape(random.choice(INTRO_MESSAGES))

    caption = (
        f"🚨 <b>ویدیوی جدید زایرن منتشر شد!</b>\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"🔥 <b>{title}</b>\n\n"
        f"💥 <b>رفیق، از دستش نده؛ همین الان ببینش!</b>\n\n"
        f"💬 نظرت رو بعد از تماشا برامون بنویس.\n"
        f"💛 با لایک و حمایتت از زایرن پشتیبانی کن!\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎲 {intro}"
    )

    keyboard = {
        "inline_keyboard": [
            [
                {
                    "text": "▶️ تماشای ویدیو",
                    "url": video["url"],
                }
            ],
            [
                {
                    "text": "📺 کانال یوتیوب زایرن",
                    "url": "https://www.youtube.com/@Zayren666",
                }
            ],
        ]
    }

    response = requests.post(
        f"{TELEGRAM_API}/sendPhoto",
        data={
            "chat_id": TELEGRAM_CHANNEL,
            "photo": video["thumbnail"],
            "caption": caption,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard, ensure_ascii=False),
        },
        timeout=45,
    )

    response.raise_for_status()
    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

    logging.info("Published video with thumbnail: %s", video["id"])


def main():
    seen = load_seen()
    seen_set = set(seen)

    videos = get_videos()

    if not videos:
        logging.info("No videos found in the YouTube feed.")
        return

    # The feed normally lists newest videos first.
    new_videos = [
        video for video in reversed(videos)
        if video["id"] not in seen_set
    ]

    # On the first run, record existing uploads without posting
    # every old video to the Telegram channel.
    if not seen:
        save_seen([video["id"] for video in videos])
        logging.info(
            "Initialized history with %d existing video(s). "
            "No old videos were posted.",
            len(videos),
        )
        return

    for video in new_videos:
        publish_video(video)
        seen.append(video["id"])
        save_seen(seen)

    if not new_videos:
        logging.info("No new uploads.")


if __name__ == "__main__":
    main()
