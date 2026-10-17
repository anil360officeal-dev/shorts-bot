"""Script banane wala hissa: Claude (Anthropic) ya Gemini."""
import json
import os
import random
import re
from datetime import datetime

import requests

RULES = """You are an experienced Hindi YouTube Shorts script writer.
Output ONLY valid JSON, no extra text, no markdown fences.
Format:
{"title": "...", "description": "...", "tags": ["..."], "scenes": [{"narration": "...", "image_query": "..."}]}
Rules:
- 8 or 9 scenes. Each scene's narration is in Devanagari Hindi, 10-14 words. Total 90-115 words.
- First scene is a strong hook. Last scene is a short question or a request to follow.
- title: Hindi, under 60 characters, no false clickbait.
- description: Hindi, 2-3 lines.
- tags: 5-8 tags, mix of Hindi and English.
- image_query: English, 2-3 generic words (e.g. "students exam hall", "parliament building", "crowd protest"). NEVER put a real person's name in image_query.
- Tone: calm, factual, respectful. Simple spoken Hindi that is easy to read aloud.
"""

NEWS_RULES = """This is a NEWS UPDATE about the Cockroach Janta Party (CJP) protests / NEET paper leak issue.
STRICT accuracy rules:
- Use ONLY what is stated in the headlines given below. Do NOT add numbers, names, quotes or claims from your own memory.
- Attribute claims ("रिपोर्ट्स के मुताबिक", or the outlet's name). Never state allegations against a person or party as proven fact.
- Present both sides where the headlines allow (protesters/opposition AND government/police).
- If something is unconfirmed or videos are disputed, say it is not confirmed yet.
- Do not incite hatred or violence, do not take sides, no insulting language.
- If headlines are thin, keep the video short and general rather than inventing details."""

EXPLAINER_RULES = """This is an EXPLAINER video. Use only widely known, well-established facts and the headlines context given.
Do not invent statistics, dates or quotes. If unsure of a number, leave it out. Stay neutral and educational."""

MOTIVATION_RULES = """This is a MOTIVATION video for students and competitive-exam aspirants in India (NEET, JEE, UPSC etc.).
Be uplifting and practical, with one clear takeaway. No medical or financial claims, no fake stories about named real people."""

EXPLAINER_TOPICS = [
    "कॉकरोच जनता पार्टी (CJP) क्या है और कैसे शुरू हुई",
    "NEET पेपर लीक विवाद आसान भाषा में",
    "NEET परीक्षा क्या है और क्यों इतनी अहम है",
    "पेपर लीक रोकने के लिए भारत में कौन से कानून हैं",
    "जंतर मंतर: भारत में विरोध प्रदर्शन की मशहूर जगह",
    "शांतिपूर्ण प्रदर्शन का अधिकार: संविधान क्या कहता है",
    "भूख हड़ताल क्या होती है और इसका इतिहास",
    "भारत के बड़े छात्र आंदोलन: एक छोटा इतिहास",
    "परीक्षा रद्द होने पर छात्रों पर क्या असर पड़ता है",
    "परीक्षा एजेंसी (NTA) क्या काम करती है",
]

MOTIVATION_TOPICS = [
    "असफलता के बाद वापसी कैसे करें",
    "रोज़ थोड़ा पढ़ना, एक दिन में ज़्यादा पढ़ने से बेहतर क्यों है",
    "परीक्षा के तनाव में शांत कैसे रहें",
    "जब मन न लगे तब भी शुरुआत कैसे करें",
    "दूसरों से तुलना करना कैसे छोड़ें",
    "परीक्षा रद्द या देरी होने पर हिम्मत कैसे बनाए रखें",
    "छोटी आदतें जो बड़ा बदलाव लाती हैं",
    "समय का सही इस्तेमाल करने के 3 आसान तरीके",
    "फोन की लत से पढ़ाई बचाने का तरीका",
    "लगातार मेहनत का असली मतलब",
]


def _pick(pool, hist):
    used = {h.get("topic") for h in hist}
    fresh = [t for t in pool if t not in used]
    return random.choice(fresh or pool)


def _extract_json(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    s, e = text.find("{"), text.rfind("}")
    return json.loads(text[s:e + 1])


def _call_anthropic(system, user):
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"],
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-5-5",
              "max_tokens": 2500, "system": system,
              "messages": [{"role": "user", "content": user}]},
        timeout=120)
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json()["content"])


def _call_gemini(system, user):
    model = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"],
                 "content-type": "application/json"},
        json={"systemInstruction": {"parts": [{"text": system}]},
              "contents": [{"role": "user", "parts": [{"text": user}]}],
              "generationConfig": {"responseMimeType": "application/json"}},
        timeout=120)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def _call(system, user):
    provider = (os.getenv("LLM_PROVIDER") or "").lower()
    if not provider:
        provider = "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "gemini"
    if provider == "anthropic":
        return _call_anthropic(system, user)
    return _call_gemini(system, user)


def _valid(d):
    sc = d.get("scenes")
    if not isinstance(sc, list) or not (5 <= len(sc) <= 12):
        return False
    if not all(isinstance(s, dict) and s.get("narration", "").strip() for s in sc):
        return False
    words = sum(len(s["narration"].split()) for s in sc)
    return 50 <= words <= 170 and bool(d.get("title"))


def make_script(slot, items, hist):
    today = datetime.now().strftime("%d %B %Y")
    recent = [h["title"] for h in hist[-30:] if h.get("title")]
    avoid = ("\nRecently made videos, do NOT repeat: " + " | ".join(recent)) if recent else ""
    ctx = "\n".join(f"- {i['title']} ({i['source']}, {i['date']:%d %b %Y})" for i in items)
    topic = None

    if slot == "news":
        system = RULES + "\n" + NEWS_RULES
        user = f"Today is {today}. Latest headlines:\n{ctx}\n\nWrite a Shorts script summarising today's key developments.{avoid}"
    elif slot == "explainer":
        topic = _pick(EXPLAINER_TOPICS, hist)
        system = RULES + "\n" + EXPLAINER_RULES
        user = f"Today is {today}. Topic: {topic}\nContext headlines (may help):\n{ctx or '(none)'}{avoid}"
    else:
        topic = _pick(MOTIVATION_TOPICS, hist)
        system = RULES + "\n" + MOTIVATION_RULES
        user = f"Topic: {topic}{avoid}"

    last_err = None
    for attempt in range(3):
        try:
            d = _extract_json(_call(system, user))
            if _valid(d):
                d["title"] = d["title"].strip()[:90]
                d["tags"] = [str(t).strip() for t in d.get("tags", [])][:8]
                for s in d["scenes"]:
                    s["narration"] = s["narration"].strip()
                    s["image_query"] = (s.get("image_query") or "students studying").strip()
                d["topic"] = topic
                return d
            last_err = "script format sahi nahi tha"
        except Exception as e:
            last_err = e
        print("LLM retry:", last_err)
    raise RuntimeError(f"Script nahi ban payi: {last_err}")
