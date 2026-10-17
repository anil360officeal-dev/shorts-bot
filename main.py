"""Roz ke Shorts: news -> script -> voice -> video -> YouTube."""
import argparse
import os
import traceback
from datetime import datetime, timedelta, timezone

import history
import llm
import news
import notify
import uploader
import video

LABELS = {"news": "ताज़ा खबर", "explainer": "समझिए", "motivation": "मोटिवेशन"}
CATEGORY = {"news": "25", "explainer": "27", "motivation": "22"}


def auto_slot():
    h = datetime.now(timezone.utc).hour
    if h < 6:
        return "news"        # ~9 AM IST
    if h < 11:
        return "explainer"   # ~2 PM IST
    return "motivation"      # ~7 PM IST


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    slot = a.slot.strip() or auto_slot()
    dry = a.dry_run or os.getenv("DRY_RUN") == "1"
    print("Slot:", slot)

    hist = history.load()
    items = news.fetch() if slot in ("news", "explainer") else []
    if slot == "news" and len(items) < 2:
        print("Taaza news kam hai, explainer bana rahe hain")
        slot = "explainer"

    data = llm.make_script(slot, items, hist)
    print("Title:", data["title"])
    final = video.build(data["scenes"], LABELS[slot], "out")

    desc = data["description"].strip()
    if items:
        srcs = []
        for i in items[:8]:
            if i["source"] not in srcs:
                srcs.append(i["source"])
        desc += "\n\nस्रोत (headlines): " + ", ".join(srcs[:5])
    desc += "\n\nनोट: यह वीडियो AI की मदद से बनाया गया है। पुष्टि के लिए मूल खबरें ज़रूर पढ़ें।\n#Shorts"
    tags = data["tags"] + ["Shorts"]
    title = data["title"] + " #Shorts"

    if dry:
        print("DRY RUN: upload nahi kiya. File:", final)
        return

    publish_at = None
    delay = int(os.getenv("NEWS_DELAY_MINUTES") or 90)
    if slot == "news" and delay > 0:
        publish_at = (datetime.now(timezone.utc) + timedelta(minutes=delay)).strftime("%Y-%m-%dT%H:%M:%SZ")

    vid = uploader.upload(final, title, desc, tags, CATEGORY[slot], publish_at)
    print("Uploaded:", vid)
    history.add({"date": datetime.now(timezone.utc).isoformat(), "slot": slot,
                 "title": data["title"], "topic": data.get("topic"), "id": vid})

    msg = f"✅ {slot} Short upload hua:\n{data['title']}\nhttps://studio.youtube.com/video/{vid}/edit"
    if publish_at:
        msg += f"\n\n⏰ Ye {delay} min baad apne aap Public hoga. Kuch galat lage to abhi Studio me delete ya Private kar do."
    notify.telegram(msg)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        notify.telegram(f"❌ Shorts bot fail hua: {e}")
        raise
