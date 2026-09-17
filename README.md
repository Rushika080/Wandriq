# ✦ Wandriq — AI Travel Planner

> Budget-smart, sustainable, AI-powered travel itineraries. Multi-currency. Free forever.

---

## 🚀 Quick Start (3 steps)

### Step 1 — Get your FREE Groq API key
1. Go to **https://console.groq.com**
2. Sign up (free, no credit card needed)
3. Click **"Create API Key"** → copy it

### Step 2 — Set the key
**Windows (Command Prompt):**
```
set GROQ_API_KEY=gsk_your_key_here
```

**Windows (PowerShell):**
```
$env:GROQ_API_KEY="gsk_your_key_here"
```

**Mac / Linux:**
```
export GROQ_API_KEY=gsk_your_key_here
```

### Step 3 — Run
```
python start.py
```
Open http://localhost:8000 in your browser. That's it!

---

## 📦 Project Structure

```
wandriq/
├── backend/
│   └── main.py          ← FastAPI server (Python 3.10+)
├── frontend/
│   ├── templates/
│   │   └── index.html   ← Main UI
│   └── static/
│       ├── css/main.css ← Dark luxury styles
│       └── js/app.js    ← App logic
├── requirements.txt
├── start.py             ← One-click launcher
└── README.md
```

---

## 🔑 APIs Used (All Free)

| API | What it does | Cost |
|-----|-------------|------|
| **Groq** (LLaMA 3 70B) | AI itinerary, destination suggestions | Free tier |
| **Open-Meteo** | Real live weather forecast | Free, no key |
| **Open-ER-API** | Currency exchange rates | Free, no key |
| **Open-Meteo Geocoding** | City coordinates lookup | Free, no key |

---

## 🧠 Is LLaMA 3 70B Heavy?

**No! You do NOT download the model.**

Groq runs the model on their cloud servers. Your PC only needs:
- Python 3.10+
- ~50 MB for the app + dependencies
- Internet connection

| Option | Model size | Your PC RAM needed | Notes |
|--------|-----------|-------------------|-------|
| **Groq API (recommended)** | Hosted | ~200 MB RAM | Free, fast |
| Ollama (local) | LLaMA 3 8B = 5 GB | 8 GB RAM min | Slower, offline |
| Ollama (local) | LLaMA 3 70B = 40 GB | 64 GB RAM! | Very heavy |

**Verdict: Use Groq API. Free, instant, no download required.**

---

## 💡 Features

- ✈ AI-generated day-by-day itinerary
- 💰 Budget tracking with multi-currency support (20 currencies)
- 🌍 "Best places by month" destination finder
- 🌤 Real live weather forecast (Open-Meteo)
- 🏨 Hotel & restaurant recommendations
- 🌱 Sustainable travel tips
- 🎒 Auto-generated packing checklist
- 🗣 Local phrase cheatsheet
- 💾 Offline cache (saves last itinerary)
- ↺ Regenerate button

---

## 🔧 Manual Start (without start.py)

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 Supported Currencies

USD, EUR, GBP, INR, JPY, AUD, CAD, SGD, AED, BRL, MXN, KRW, THB, IDR, TRY, ZAR, CHF, SEK, NOK, NZD

---

## 📋 Requirements

- Python 3.10, 3.11, 3.12, or 3.13
- Internet connection
- Free Groq API key

---

Made with ✦ and wanderlust.
