import json, os, sys, tempfile, pathlib
from datetime import datetime, timedelta, timezone
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import bot
from xml.sax.saxutils import escape

def feed(entries):
    items = ""
    for vid, title, kind, age_h in entries:
        pub = (datetime.now(timezone.utc) - timedelta(hours=age_h)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        link = f"https://www.youtube.com/{'shorts/' if kind=='s' else 'watch?v='}{vid}"
        items += f"""<entry><yt:videoId>{vid}</yt:videoId><title>{escape(title)}</title>
<link rel="alternate" href="{link}"/><published>{pub}</published></entry>"""
    return f"""<?xml version="1.0"?><feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
xmlns="http://www.w3.org/2005/Atom">{items}</feed>""".encode()

class R:
    def __init__(s, code=200, content=b"", js=None, text=""):
        s.status_code=code; s.content=content; s._js=js; s.text=text or content.decode(errors="ignore")
    def json(s): return s._js

class Fake:
    def __init__(s, entries): s.entries=entries; s.sent=[]; s.updates=[]; s.headers={}
    def get(s, url, **k):
        if "feeds/videos.xml" in url: return R(200, feed(s.entries))
        return R(200, b"")
    def head(s, url, **k): return R(303)
    def post(s, url, json=None, **k):
        m = url.rsplit("/",1)[1]
        if m=="getMe": return R(js={"ok":True,"result":{"id":1,"username":"zbot"}})
        if m=="getChat": return R(js={"ok":True,"result":{"id":-100,"type":"channel"}})
        if m=="getChatMember": return R(js={"ok":True,"result":{"status":"administrator","can_post_messages":True}})
        if m=="getUpdates":
            u, s.updates = s.updates, []
            return R(js={"ok":True,"result":u})
        s.sent.append((m, json))
        return R(js={"ok":True,"result":{"message_id":7}})

def setup(entries, tmp):
    f = Fake(entries); bot.HTTP = f
    bot.STATE_FILE = pathlib.Path(tmp)/"bot_state.json"
    os.environ.update(BOT_TOKEN="123:abc", YOUTUBE_CHANNEL_ID="UC"+"a"*22, TELEGRAM_CHANNEL="https://t.me/Zayren6666")
    os.environ.pop("FORCE_LATEST", None)
    return f

def test_flow():
    with tempfile.TemporaryDirectory() as tmp:
        f = setup([("L1","long one",'l',5),("S1","short one",'s',3),("L0","old long",'l',50)], tmp)
        bot.run()
        kinds = [m for m,_ in f.sent]
        assert kinds.count("sendPhoto")==2, kinds          # latest long + short
        assert "sendMessage" in kinds and "pinChatMessage" in kinds   # intro
        st = json.loads(bot.STATE_FILE.read_text())
        assert st["initialized"] and set(st["seen"])=={"L1","S1","L0"}
        # second run: nothing new
        f.sent.clear(); bot.run(); assert not [m for m,_ in f.sent if m=="sendPhoto"]
        # new video appears
        f.entries.insert(0,("N1","new <b>&title",'l',0.1)); f.sent.clear(); bot.run()
        photos=[p for m,p in f.sent if m=="sendPhoto"]
        assert len(photos)==1 and "&lt;b&gt;" in photos[0]["caption"]
        assert len(photos[0]["caption"])<=1024
        # private /start command
        f.updates=[{"update_id":5,"message":{"text":"/start","chat":{"id":99,"type":"private"}}}]
        f.sent.clear(); bot.run()
        assert any(p.get("chat_id")==99 for m,p in f.sent)
        assert json.loads(bot.STATE_FILE.read_text())["update_offset"]==6

def test_force_and_old():
    with tempfile.TemporaryDirectory() as tmp:
        f = setup([("L1","a",'l',5),("S1","b",'s',3)], tmp)
        bot.run(); f.sent.clear()
        os.environ["FORCE_LATEST"]="true"; bot.run()
        assert [m for m,_ in f.sent].count("sendPhoto")==2
        os.environ.pop("FORCE_LATEST")
        f.entries.insert(0,("OLD","ancient",'l',24*30)); f.sent.clear(); bot.run()
        assert not [m for m,_ in f.sent if m=="sendPhoto"]

def test_normalize():
    assert bot.normalize_chat("https://t.me/Zayren6666")=="@Zayren6666"
    assert bot.normalize_chat("Zayren6666")=="@Zayren6666"
    assert bot.normalize_chat("")=="@Zayren6666"
    assert bot.normalize_chat("-1001234")=="-1001234"

if __name__=="__main__":
    test_normalize(); test_flow(); test_force_and_old(); print("ALL TESTS PASSED")
