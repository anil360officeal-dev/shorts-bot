"""Voiceover + visuals + captions -> final vertical video (ffmpeg + Pillow)."""
import asyncio
import base64
import glob
import os
import random
import subprocess
import time
import wave
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30


def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg error: " + p.stderr[-800:])


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# ======================= VOICE =======================
def _gemini_tts(text, path):
    """Gemini ki natural awaz (free tier). Fail ho to edge-tts par chala jata hai."""
    key = os.environ["GEMINI_API_KEY"]
    model = os.getenv("GEMINI_TTS_MODEL") or "gemini-3.1-flash-tts-preview"
    voice = os.getenv("GEMINI_VOICE") or "Kore"
    prompt = "Say in a clear, steady, engaging Hindi voice like a friendly news presenter: " + text
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["AUDIO"],
                                 "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}}
    for attempt in range(4):
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": key, "content-type": "application/json"},
            json=body, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            print("gemini tts busy, wait...", r.status_code)
            time.sleep(20 * (attempt + 1))
            continue
        r.raise_for_status()
        part = r.json()["candidates"][0]["content"]["parts"][0]
        blob = part.get("inlineData") or part.get("inline_data")
        pcm = base64.b64decode(blob["data"])
        wav = str(path) + ".wav"
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(pcm)
        run(["ffmpeg", "-y", "-i", wav, "-ar", "44100", "-ac", "1", "-b:a", "160k", str(path)])
        return
    raise RuntimeError("gemini tts nahi chala")


async def _edge(text, path, voice, rate):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


def _edge_tts(text, path):
    voice = os.getenv("TTS_VOICE") or "hi-IN-SwaraNeural"
    rate = os.getenv("TTS_RATE") or "+0%"
    for _ in range(3):
        try:
            asyncio.run(_edge(text, str(path), voice, rate))
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            print("edge-tts fail:", e)
            time.sleep(2)
    raise RuntimeError("edge-tts nahi chala")


def _gtts(text, path):
    from gtts import gTTS
    gTTS(text, lang="hi").save(str(path))


def synth_all(scenes, work):
    """Poori video ki awaz ek hi engine se banao, taaki voice beech me na badle."""
    order = []
    if (os.getenv("TTS_ENGINE") or "gemini").lower() == "gemini" and os.getenv("GEMINI_API_KEY"):
        order.append(("gemini", _gemini_tts))
    order += [("edge", _edge_tts), ("gtts", _gtts)]
    for name, fn in order:
        try:
            paths = []
            for i, sc in enumerate(scenes):
                p = work / f"a{i}.mp3"
                fn(sc["narration"], p)
                paths.append(p)
                if name == "gemini":
                    time.sleep(2)
            print("Voice engine:", name)
            return paths
        except Exception as e:
            print(f"Voice engine {name} fail:", e)
    raise RuntimeError("Koi voice engine nahi chala")


# ======================= VISUALS =======================
def _queries(q):
    words = q.split()
    out = [q]
    if len(words) > 1:
        out.append(words[-1])
    out.append("abstract light background")
    return out


def pixabay_video(query, out):
    key = os.getenv("PIXABAY_API_KEY")
    if not key:
        return None
    for q in _queries(query):
        try:
            r = requests.get("https://pixabay.com/api/videos/",
                             params={"key": key, "q": q, "per_page": 12, "safesearch": "true"}, timeout=20)
            hits = r.json().get("hits", [])
            random.shuffle(hits)
            for h in hits:
                for size in ("medium", "small", "large"):
                    v = (h.get("videos") or {}).get(size) or {}
                    if v.get("url") and 0 < v.get("size", 1) < 40_000_000:
                        data = requests.get(v["url"], timeout=90).content
                        Path(out).write_bytes(data)
                        return out
        except Exception as e:
            print("pixabay video fail:", e)
    return None


def pixabay_image(query, out):
    key = os.getenv("PIXABAY_API_KEY")
    if not key:
        return None
    for q in _queries(query):
        try:
            r = requests.get("https://pixabay.com/api/",
                             params={"key": key, "q": q, "image_type": "photo", "orientation": "vertical",
                                     "per_page": 12, "safesearch": "true"}, timeout=20)
            hits = r.json().get("hits", [])
            if hits:
                url = random.choice(hits)["largeImageURL"]
                Path(out).write_bytes(requests.get(url, timeout=60).content)
                return out
        except Exception as e:
            print("pixabay image fail:", e)
    return None


PALETTES = [((20, 30, 70), (90, 40, 120)), ((10, 60, 70), (20, 20, 60)),
            ((70, 20, 40), (20, 20, 50)), ((20, 50, 30), (10, 30, 60))]


def gradient_bg(idx, out):
    top, bot = PALETTES[idx % len(PALETTES)]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for _ in range(6):
        r = random.randint(150, 350)
        x, y = random.randint(0, W), random.randint(0, H)
        c = tuple(min(255, v + random.randint(50, 120)) for v in top)
        gd.ellipse([x - r, y - r, x + r, y + r], fill=c)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    Image.blend(img, glow, 0.55).save(out)
    return out


def find_font():
    env = os.getenv("FONT_PATH")
    if env and os.path.exists(env):
        return env
    for pat in ("/usr/share/fonts/**/NotoSansDevanagari-Bold.ttf",
                "/usr/share/fonts/**/NotoSansDevanagari*Bold*.ttf",
                "/usr/share/fonts/**/NotoSansDevanagari*.ttf",
                "/usr/share/fonts/**/Lohit-Devanagari.ttf",
                "C:/Windows/Fonts/Nirmala.ttf"):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return hits[0]
    raise RuntimeError("Devanagari font nahi mila (fonts-noto-core install karein)")


def wrap(font, text, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if font.getlength(t) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def render_overlay(text, label, out):
    """Transparent PNG: upar label, neeche caption (dark box ke saath)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fp = find_font()

    lf = ImageFont.truetype(fp, 52)
    lw = lf.getlength(label)
    d.rounded_rectangle([(W - lw) / 2 - 40, 130, (W + lw) / 2 + 40, 225], radius=48, fill=(220, 40, 50, 245))
    d.text(((W - lw) / 2, 140), label, font=lf, fill="white")

    for size in (76, 70, 64, 58, 52, 46):
        font = ImageFont.truetype(fp, size)
        lines = wrap(font, text, 880)
        lh = int(size * 1.5)
        if len(lines) * lh <= 780:
            break
    total = len(lines) * lh
    y0 = min(max(1180 - total // 2, 300), H - 160 - total)
    d.rounded_rectangle([50, y0 - 40, W - 50, y0 + total + 30], radius=40, fill=(0, 0, 0, 150))
    y = y0
    for ln in lines:
        x = (W - font.getlength(ln)) / 2
        d.text((x, y), ln, font=font, fill="white", stroke_width=4, stroke_fill="black")
        y += lh
    img.save(out)


# ======================= VIDEO =======================
def make_part(kind, bg, overlay, audio, dur, out):
    frames = int(dur * FPS) + 3
    if kind == "video":
        pre = ["-stream_loop", "-1", "-i", str(bg)]
        chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 f"setsar=1,fps={FPS},eq=brightness=-0.22:saturation=0.9[bg]")
    else:
        dark = ",eq=brightness=-0.22" if kind == "image" else ""
        pre = ["-i", str(bg)]
        chain = (f"[0:v]scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880,"
                 f"zoompan=z='min(1+0.0007*on,1.22)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                 f":d={frames}:s={W}x{H}:fps={FPS}{dark},setsar=1[bg]")
    graph = chain + ";[bg][1:v]overlay=0:0:shortest=1,format=yuv420p[v]"
    run(["ffmpeg", "-y", *pre, "-loop", "1", "-framerate", str(FPS), "-i", str(overlay), "-i", str(audio),
         "-filter_complex", graph, "-map", "[v]", "-map", "2:a", "-t", f"{dur:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-af", "apad", "-c:a", "aac", "-ar", "44100", "-b:a", "128k", str(out)])


def build(scenes, label, workdir):
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    audios = synth_all(scenes, work)
    parts = []
    for i, sc in enumerate(scenes):
        dur = duration(audios[i]) + 0.3
        q = sc.get("image_query") or "students studying"
        bg = pixabay_video(q, work / f"bg{i}.mp4")
        kind = "video"
        if not bg:
            bg = pixabay_image(q, work / f"bg{i}.jpg")
            kind = "image"
        if not bg:
            bg = gradient_bg(i, work / f"bg{i}.png")
            kind = "gradient"
        print(f"scene {i}: {kind}")
        overlay = work / f"o{i}.png"
        render_overlay(sc["narration"], label, overlay)
        part = work / f"p{i}.mp4"
        try:
            make_part(kind, bg, overlay, audios[i], dur, part)
        except Exception as e:  # bg kharab nikla to gradient se bana lo
            print("scene fallback:", e)
            make_part("gradient", gradient_bg(i, work / f"bgf{i}.png"), overlay, audios[i], dur, part)
        parts.append(part)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    final = work / "final.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
         "-movflags", "+faststart", str(final)])
    print(f"Video ready: {duration(final):.1f} sec")
    return final
