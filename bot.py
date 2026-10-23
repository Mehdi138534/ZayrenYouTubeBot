
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
TELEGRAM_CHANNEL = os.environ.get(
    "TELEGRAM_CHANNEL", "@Zayren6666"
)
YOUTUBE_CHANNEL_ID = os.environ["YOUTUBE_CHANNEL_ID"]

FEED_URL = (
    "https://www.youtube.com/feeds/videos.xml"
    f"?channel_id={YOUTUBE_CHANNEL_ID}"
)
STATE_FILE = Path("seen_videos.json")

INTRO_MESSAGES = [
    "🚨 خبر فوری! زایرن دوباره ویدیو داده!",
    "🍿 تنقلات آماده؟ ویدیوی جدید رسید!",
    "🫡 مأموریت امروز: دیدن این ویدیو!",
    "👀 من که دیدمش... شوخی کردم، برو تو ببین!",
    "🎮 آپلود جدید داریم، لشکر زایرن جمع شید!",
    "🔥 یوتیوب ساکت بود، زایرن سکوت رو شکست!",
]

def load_seen():
    if not STATE_FILE.exists():
        return []
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        logging.warning("Could not read saved video state.")
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
        "media": "http://search.yahoo.com/mrss/",
    }

    videos = []
    for entry in root.findall("atom:entry", ns):
        video_id = entry.findtext("yt:videoId", namespaces=ns)
        title = entry.findtext("atom:title", default="ویدیوی جدید",
                               namespaces=ns)
        link = entry.find("atom:link", ns)
        url = link.attrib.get("href", "") if link is not None else ""

        if video_id and url:
            videos.append({
                "id": video_id,
                "title": title,
                "url": url,
            })

    return videos

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHANNEL,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    response.raise_for_status()

    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")

def make_caption(video):
    title = html.escape(video["title"])
    intro = random.choice(INTRO_MESSAGES)

    return (
        f"{intro}\n\n"
        f"🎬 <b>{title}</b>\n\n"
        f"🔗 <a href=\"{html.escape(video['url'], quote=True)}\">"
        f"تماشای ویدیو در یوتیوب</a>\n\n"
        f"💛 حمایت یادت نره!\n"
        f"📺 <a href=\"https://www.youtube.com/@Zayren666\">"
        f"کانال یوتیوب Zayren</a>"
    )

def main():
    seen = load_seen()
    seen_set = set(seen)

    videos = get_videos()
    if not videos:
        logging.info("No videos found in the feed.")
        return

    # Feed entries are normally newest first.
    new_videos = [
        video for video in reversed(videos)
        if video["id"] not in seen_set
    ]

    if not seen:
        # First run: don't spam the channel with old uploads.
        latest = videos[0]
        save_seen([video["id"] for video in videos])
        logging.info("Initialized state with latest video: %s", latest["id"])
        return

    for video in new_videos:
        send_message(make_caption(video))
        seen.append(video["id"])
        save_seen(seen)
        logging.info("Published video: %s", video["id"])

    if not new_videos:
        logging.info("No new uploads.")

if __name__ == "__main__":
    main()
