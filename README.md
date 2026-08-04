# 🇧🇩 Bangladesh Free Temp Number Bot — Updated

> ✅ সম্পূর্ণ বিনামূল্যে | কোনো account বা payment লাগবে না

---

## ✨ নতুন ফিচার (Updated)

```
┌─────────────────────────────────┐
│  📞 New Number  │  👁 View OTP  │  ← সবসময় নিচে থাকে
│  📋 Copy Number │    ❌ Stop    │
│  💰 Balance Info│    ❓ Help    │
└─────────────────────────────────┘
```

| বোতাম | কাজ |
|-------|-----|
| 📞 **New Number** | নতুন Bangladesh (+880) নম্বর নিন |
| 👁 **View OTP** | সর্বশেষ OTP দেখুন (real-time) |
| 📋 **Copy Number** | চলতি নম্বর কপি করুন |
| ❌ **Stop** | monitoring বন্ধ করুন |
| 💰 **Balance Info** | ব্যবহারের তথ্য দেখুন |
| ❓ **Help** | সাহায্য দেখুন |

---

## 🔄 Real-time OTP System

```
আপনি                     Bot                  free-otp-receive.com
  │                        │                          │
  │── 📞 New Number ───────►│                          │
  │                        │── নম্বর খুঁজছে ─────────►│
  │◄── +880XXXXXXXXXX ──────│◄─ Active numbers ────────│
  │                        │                          │
  │  [OTP পাঠান নম্বরে]    │                          │
  │                        │                          │
  │                        │── প্রতি ৫ সেকেন্ডে ─────►│
  │                        │◄── নতুন SMS! ────────────│
  │◄── 🔔 OTP: XXXXXX ──────│                          │
  │                        │                          │
  │── 👁 View OTP ─────────►│                          │
  │◄── সর্বশেষ OTP দেখায় ───│                          │
```

---

## 🚀 Setup (মাত্র ৩ ধাপ)

### ধাপ ১ — Bot Token নিন (বিনামূল্যে)

1. [@BotFather](https://t.me/BotFather) খুলুন
2. `/newbot` → নাম ও username দিন
3. **Token** কপি করুন

### ধাপ ২ — `.env` ফাইল বানান

```bash
cp .env.example .env
```

`.env`-এ লিখুন:
```
BOT_TOKEN=আপনার_token_এখানে
```

### ধাপ ৩ — চালু করুন

```bash
pip install -r requirements.txt
python bot.py
```

---

## ☁️ GitHub দিয়ে Host করুন

### Railway.app (বিনামূল্যে — সবচেয়ে সহজ)

1. [railway.app](https://railway.app) → GitHub Login
2. **New Project → Deploy from GitHub repo**
3. Variables: `BOT_TOKEN = আপনার_token`
4. Deploy ✅

### GitHub-এ Upload করুন

```bash
git init
git add .
git commit -m "Bangladesh Free Temp Number Bot"
git branch -M main
git remote add origin https://github.com/username/repo-name.git
git push -u origin main
```

> ⚠️ `.env` ফাইল push হবে না — `.gitignore` protect করছে।

---

## 📁 ফাইল কাঠামো

```
bd-free-tempnum-bot/
├── bot.py              ← মূল bot (সব কিছু এখানে)
├── requirements.txt    ← Python packages
├── .env.example        ← Token template
├── .env               ← আপনার token (secret)
├── .gitignore          ← .env protect করে
├── Procfile            ← Railway/Heroku
├── runtime.txt         ← Python 3.11
└── README.md           ← এই ফাইল
```

---

## ⚠️ গুরুত্বপূর্ণ

- এগুলো **public নম্বর** — অনেকে একসাথে ব্যবহার করে
- ব্যাংক বা গুরুত্বপূর্ণ কাজে ব্যবহার **করবেন না**
- OTP আসলে দ্রুত ব্যবহার করুন
