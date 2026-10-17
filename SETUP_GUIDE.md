# YouTube Shorts Auto-Bot: Setup Guide (zero coding)

**Ye kya karega:** roz 3 Shorts apne aap banayega aur upload karega.

| Time (IST) | Type | Kaise upload hoga |
|---|---|---|
| ~9:00 AM | Taaza news (CJP / NEET) | Private upload, **90 min baad apne aap Public**. Is beech aap check karke delete kar sakte ho |
| ~2:00 PM | Explainer (CJP kya hai, etc.) | Seedha Public |
| ~7:00 PM | Motivation (students ke liye) | Seedha Public |

GitHub ke servers par chalta hai, aapka laptop band ho tab bhi.

**Kharcha:** GitHub free, Pexels free, voice free. Sirf AI: Claude me approx Rs 2-4 per video, ya **Gemini free**.

---

## Step 1: GitHub account aur repository
1. github.com par free account banao.
2. Upar `+` → **New repository**. Naam: `shorts-bot`. **Private** select karo. Create karo.
3. **uploading an existing file** link par click karo.
4. Is zip ko extract karo aur andar ki **saari files/folders drag-drop** karo, phir **Commit changes**.
5. **Zaroori check:** repo me `.github/workflows/daily.yml` dikhna chahiye. Agar `.github` folder upload nahi hua (kabhi kabhi hidden folder skip ho jata hai):
   - **Add file → Create new file**, naam me likho: `.github/workflows/daily.yml`
   - `daily_workflow_copy.yml` ka poora content wahan paste karo aur Commit karo.

## Step 2: AI key (koi EK lo)
- **Option A, free (Gemini):** aistudio.google.com/apikey → Create API key → copy.
- **Option B, Claude (zyada accurate Hindi):** console.anthropic.com → API Keys → Create key. Billing me thoda credit daalna padega ($5 kaafi hai).

## Step 3: Pexels key (free, backgrounds ke liye)
pexels.com/api → sign up → API key copy karo. (Na lo to simple coloured background aayega.)

## Step 4: YouTube permission (sabse lamba step, dhyan se)
1. console.cloud.google.com → naya **Project** banao.
2. **APIs & Services → Library** → "YouTube Data API v3" → **Enable**.
3. **OAuth consent screen** (naye menu me "Google Auth Platform"):
   - User type: **External**, app ka naam kuch bhi, apni email daalo.
   - **Test users** me apni Gmail add karo (jis se YouTube channel hai).
   - **Zaroori:** phir **Publish app** (Publishing status → **In production**) dabao. Ye na kiya to token 7 din me expire ho jayega aur bot ruk jayega.
4. **Credentials → Create credentials → OAuth client ID:**
   - Type: **Web application**
   - **Authorized redirect URIs** me ye daalo: `https://developers.google.com/oauthplayground`
   - Create. **Client ID** aur **Client Secret** copy karke rakho.
5. Browser me **developers.google.com/oauthplayground** kholo:
   - Upar-right **gear icon** → **Use your own OAuth credentials** tick → apna Client ID aur Secret paste karo.
   - Left me neeche "Input your own scopes" box me ye daalo: `https://www.googleapis.com/auth/youtube.upload` → **Authorize APIs**.
   - Apna Google account chuno (channel wala). "Google hasn't verified this app" aaye to **Advanced → Go to ... (unsafe) → Allow**.
   - **Exchange authorization code for tokens** dabao. **Refresh token** copy karo.

## Step 5: Secrets daalo
GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**. Ek-ek karke:

| Name | Value |
|---|---|
| `GEMINI_API_KEY` ya `ANTHROPIC_API_KEY` | Step 2 wali key |
| `PEXELS_API_KEY` | Step 3 wali key |
| `YT_CLIENT_ID` | Step 4 ka Client ID |
| `YT_CLIENT_SECRET` | Step 4 ka Client Secret |
| `YT_REFRESH_TOKEN` | Step 4 ka Refresh token |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | *Optional*, neeche dekho |

## Step 6: Test karo
1. Repo me **Actions** tab → **Daily Shorts** → **Run workflow**.
2. slot me `explainer` likho → **Run workflow**. 4-6 minute lagenge.
3. Green tick aaye to YouTube Studio me video check karo.
4. Red cross aaye to us run par click karke error ka screenshot mujhe bhej do, main fix kar dunga.

Iske baad kuch nahi karna. Roz apne aap chalega.

---

## Zaroori baatein (sach me padh lena)
1. **Private lock:** Google ke naye API projects se upload ki gayi videos kabhi-kabhi **"Private" lock** ho jati hain jab tak project ka compliance audit pass na ho. Aisa ho to YouTube Studio se manually Public karo, ya Google ka "YouTube API Services audit" form bharo. Main form me madad kar dunga.
2. **News ki jimmedari aapki hai.** AI sirf diye gaye headlines se script banata hai aur neutral rehta hai, phir bhi galti ho sakti hai. Roz subah wali news video ek baar dekh lena (Studio me, 90 min ki window me).
3. **Monetization:** YouTube repetitive/mass-produced content ko monetize nahi karta. Jaldi paisa mat expect karo; apna touch aur kabhi-kabhi khud ki video bhi daalo.
4. **Upload limit:** YouTube API roz ~6 uploads allow karta hai. 3 kaafi hain.

## Optional: Telegram alert
Video upload hote hi aapke phone par message aayega (aur error aaye to bhi).
1. Telegram me `@BotFather` → `/newbot` → token copy karo → `TELEGRAM_BOT_TOKEN`.
2. Apne naye bot ko "hi" bhejo. Phir browser me kholo: `https://api.telegram.org/bot<TOKEN>/getUpdates` → `"chat":{"id": 12345...` wala number → `TELEGRAM_CHAT_ID`.

## Settings badalni ho (optional)
Repo → Settings → Secrets and variables → Actions → **Variables** tab:
- `NEWS_DELAY_MINUTES` = `0` (news turant Public) ya `180` (3 ghante baad)
- `PRIVACY` = `private` (sab videos pehle private, aap khud Public karo)

Topics badalne ho (jaise koi aur news niche) to mujhse bol do, main files update kar dunga.
