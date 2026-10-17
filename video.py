"""Voiceover + captions + video (ffmpeg + Pillow)."""
import asyncio
import glob
import os
import random
import subprocess
import time
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


# ---------- voice ----------
async def _edge(text, path, voice, rate):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate).save(path)


def tts(text, path):
    voice = os.getenv("TTS_VOICE") or "hi-IN-MadhurNeural"
    rate = os.getenv("TTS_RATE") or "+5%"
    for _ in range(3):
        try:
            asyncio.run(_edge(text, str(path), voice, rate))
            if os.path.getsize(path) > 1000:
                return
        except Exception as e:
            print("edge-tts fail:", e)
            time.sleep(2)
    from gtts import gTTS  # backup voice
    gTTS(text, lang="hi").save(str(path))


# ---------- images ----------
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


def pexels_bg(query, out):
    key = os.getenv("PEXELS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://api.pexels.com/v1/search",
                         params={"query": query, "orientation": "portrait", "per_page": 6},
                         headers={"Authorization": key}, timeout=20)
        photos = r.json().get("photos", [])
        if not photos:
            return None
        url = random.choice(photos)["src"]["portrait"]
        Path(out).write_bytes(requests.get(url, timeout=30).content)
        return out
    except Exception as e:
        print("pexels fail:", e)
        return None


PALETTES = [((20, 30, 70), (90, 40, 120)), ((10, 60, 70), (20, 20, 60)),
            ((70, 20, 40), (20, 20, 50)), ((20, 50, 30), (10, 30, 60))]


def gradient(idx):
    top, bot = PALETTES[idx % len(PALETTES)]
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return img


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


def render_frame(text, bg_path, label, out, idx):
    if bg_path:
        bg = Image.open(bg_path).convert("RGB")
        s = max(W / bg.width, H / bg.height)
        bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1), Image.LANCZOS)
        l, t = (bg.width - W) // 2, (bg.height - H) // 2
        bg = bg.crop((l, t, l + W, t + H))
        bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.58)
    else:
        bg = gradient(idx)
    d = ImageDraw.Draw(bg)
    fp = find_font()

    # upar ka label
    lf = ImageFont.truetype(fp, 56)
    lw = lf.getlength(label)
    d.rounded_rectangle([(W - lw) / 2 - 40, 150, (W + lw) / 2 + 40, 250], radius=50, fill=(220, 40, 50))
    d.text(((W - lw) / 2, 160), label, font=lf, fill="white")

    # captions
    for size in (84, 76, 68, 60, 54, 48):
        font = ImageFont.truetype(fp, size)
        lines = wrap(font, text, 900)
        lh = int(size * 1.55)
        if len(lines) * lh <= 1050:
            break
    y = (H - len(lines) * lh) // 2 + 60
    for ln in lines:
        x = (W - font.getlength(ln)) / 2
        d.text((x, y), ln, font=font, fill="white", stroke_width=5, stroke_fill="black")
        y += lh
    bg.save(out)


# ---------- final video ----------
def build(scenes, label, workdir):
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, sc in enumerate(scenes):
        audio = work / f"a{i}.mp3"
        tts(sc["narration"], audio)
        dur = duration(audio) + 0.25
        bg = pexels_bg(sc["image_query"], work / f"bg{i}.jpg")
        frame = work / f"f{i}.png"
        render_frame(sc["narration"], bg, label, frame, i)
        part = work / f"p{i}.mp4"
        run(["ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-i", str(frame), "-i", str(audio),
             "-t", f"{dur:.2f}", "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
             "-r", "30", "-af", "apad", "-c:a", "aac", "-ar", "44100", "-b:a", "128k", str(part)])
        parts.append(part)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    final = work / "final.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy",
         "-movflags", "+faststart", str(final)])
    print(f"Video ready: {duration(final):.1f} sec")
    return final
