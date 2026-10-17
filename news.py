"""Google News RSS se taaza headlines laata hai (koi API key nahi chahiye)."""
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests

# Yahan apni marzi se searches badal sakte hain
SEARCHES = [
    ("Cockroach Janta Party", "hi"),
    ("Cockroach Janta Party CJP protest", "en"),
    ("NEET paper leak", "en"),
]


def _url(q, lang, window):
    q = quote_plus(f"{q} when:{window}")
    if lang == "hi":
        return f"https://news.google.com/rss/search?q={q}&hl=hi&gl=IN&ceid=IN:hi"
    return f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"


def _fetch(q, lang, window):
    try:
        r = requests.get(_url(q, lang, window), timeout=20,
                         headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        print("news fetch fail:", q, e)
        return []
    out = []
    for it in root.iter("item"):
        title = html.unescape((it.findtext("title") or "").strip())
        src_el = it.find("source")
        source = ((src_el.text if src_el is not None else "") or "").strip()
        if source and title.endswith(" - " + source):
            title = title[: -len(" - " + source)]
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            dt = datetime.now(timezone.utc)
        out.append({"title": title, "source": source or "Unknown",
                    "date": dt, "link": it.findtext("link") or ""})
    return out


def fetch(limit=12):
    uniq = []
    for window in ("2d", "7d"):
        items = []
        for q, lang in SEARCHES:
            items += _fetch(q, lang, window)
        seen, uniq = set(), []
        for it in sorted(items, key=lambda x: x["date"], reverse=True):
            key = re.sub(r"\W+", "", it["title"].lower())[:60]
            if key and key not in seen:
                seen.add(key)
                uniq.append(it)
        if len(uniq) >= 3:
            break
    return uniq[:limit]
