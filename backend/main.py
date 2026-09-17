"""
Wandriq backend v11
- Current Groq model: openai/gpt-oss-20b
- Reliable JSON responses
- Automatic retries + rate-limit handling
- Open-Meteo weather
- Exchange rates
- Global-first, INR default
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import httpx
import json
import os
import re
import asyncio
import logging

from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wandriq")


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# ============================================================
# HTTP CLIENT
# ============================================================

_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app):
    global _client

    _client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=15,
            read=120,
            write=30,
            pool=15
        ),
        limits=httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10
        )
    )

    # Optional Render self-ping
    asyncio.create_task(self_ping())

    log.info("Wandriq v11 started ✦")

    yield

    if _client and not _client.is_closed:
        await _client.aclose()

    log.info("Wandriq shutdown complete")


# ============================================================
# RENDER SELF PING
# ============================================================

async def self_ping():
    """
    Optional Render keep-alive.

    Set:
        RENDER_EXTERNAL_URL=https://your-app.onrender.com

    in .env / Render environment variables.
    """

    await asyncio.sleep(60)

    base = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")

    if not base:
        log.info("No RENDER_EXTERNAL_URL set, self-ping disabled")
        return

    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                response = await c.get(f"{base}/api/health")

                if response.is_success:
                    log.info("Self-ping OK")
                else:
                    log.warning(
                        f"Self-ping returned HTTP {response.status_code}"
                    )

        except Exception as e:
            log.warning(f"Self-ping failed: {e}")

        await asyncio.sleep(600)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Wandriq API",
    version="11.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# FRONTEND PATHS
# ============================================================

BASE = Path(__file__).parent.parent / "frontend"

STATIC_DIR = BASE / "static"
TEMPLATE_DIR = BASE / "templates"


if STATIC_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static"
    )


@app.get("/")
def root():
    index_file = TEMPLATE_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=500,
            detail="frontend/templates/index.html not found"
        )

    return FileResponse(str(index_file))


# ============================================================
# GROQ CONFIGURATION
# ============================================================

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Current recommended replacement for llama-3.1-8b-instant
GROQ_PRIMARY = "openai/gpt-oss-20b"

# Backup model
GROQ_FALLBACK = "openai/gpt-oss-120b"


# ============================================================
# CURRENCIES
# ============================================================

CURRENCIES = [
    {"code": "INR", "symbol": "₹", "name": "Indian Rupee"},
    {"code": "USD", "symbol": "$", "name": "US Dollar"},
    {"code": "EUR", "symbol": "€", "name": "Euro"},
    {"code": "GBP", "symbol": "£", "name": "British Pound"},
    {"code": "JPY", "symbol": "¥", "name": "Japanese Yen"},
    {"code": "AUD", "symbol": "A$", "name": "Australian Dollar"},
    {"code": "CAD", "symbol": "C$", "name": "Canadian Dollar"},
    {"code": "SGD", "symbol": "S$", "name": "Singapore Dollar"},
    {"code": "AED", "symbol": "د.إ", "name": "UAE Dirham"},
    {"code": "BRL", "symbol": "R$", "name": "Brazilian Real"},
    {"code": "MXN", "symbol": "Mex$", "name": "Mexican Peso"},
    {"code": "KRW", "symbol": "₩", "name": "South Korean Won"},
    {"code": "THB", "symbol": "฿", "name": "Thai Baht"},
    {"code": "IDR", "symbol": "Rp", "name": "Indonesian Rupiah"},
    {"code": "TRY", "symbol": "₺", "name": "Turkish Lira"},
    {"code": "ZAR", "symbol": "R", "name": "South African Rand"},
    {"code": "CHF", "symbol": "Fr", "name": "Swiss Franc"},
    {"code": "SEK", "symbol": "kr", "name": "Swedish Krona"},
    {"code": "NOK", "symbol": "kr", "name": "Norwegian Krone"},
    {"code": "NZD", "symbol": "NZ$", "name": "New Zealand Dollar"},
    {"code": "PKR", "symbol": "₨", "name": "Pakistani Rupee"},
    {"code": "BDT", "symbol": "৳", "name": "Bangladeshi Taka"},
    {"code": "LKR", "symbol": "Rs", "name": "Sri Lankan Rupee"},
    {"code": "NPR", "symbol": "रू", "name": "Nepalese Rupee"},
    {"code": "MYR", "symbol": "RM", "name": "Malaysian Ringgit"},
    {"code": "PHP", "symbol": "₱", "name": "Philippine Peso"},
    {"code": "VND", "symbol": "₫", "name": "Vietnamese Dong"},
    {"code": "EGP", "symbol": "E£", "name": "Egyptian Pound"},
    {"code": "NGN", "symbol": "₦", "name": "Nigerian Naira"},
    {"code": "KES", "symbol": "KSh", "name": "Kenyan Shilling"},
]

SYM = {
    c["code"]: c["symbol"]
    for c in CURRENCIES
}


# ============================================================
# REQUEST MODELS
# ============================================================

class TripRequest(BaseModel):
    destination: str
    budget: float
    currency: str = "INR"
    duration: int = 5
    month: str = "April"
    interests: list[str] = []
    wishlist: str = ""
    travel_style: str = "mid-range"
    trip_type: str = "solo"


class MonthRequest(BaseModel):
    month: str
    budget: float
    currency: str = "INR"
    travel_style: str = "mid-range"
    interests: list[str] = []


class ChatRequest(BaseModel):
    destination: str
    duration: int
    month: str
    question: str


# ============================================================
# GROQ AI FUNCTION
# ============================================================

async def ask(
    prompt: str,
    tokens: int = 500,
    model: str = GROQ_PRIMARY,
    attempt: int = 1,
    json_mode: bool = False
) -> str:

    key = os.getenv("GROQ_API_KEY", "").strip()

    # --------------------------------------------------------
    # API KEY CHECK
    # --------------------------------------------------------

    if not key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not set. Add it to your .env file."
        )

    if key == "paste_your_groq_key_here":
        raise HTTPException(
            status_code=503,
            detail="Replace paste_your_groq_key_here with your real Groq API key."
        )

    log.info(
        f"Groq → model={model} chars={len(prompt)} "
        f"tokens={tokens} attempt={attempt}"
    )

    # --------------------------------------------------------
    # CLIENT
    # --------------------------------------------------------

    client = _client

    temporary_client = False

    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=15,
                read=120,
                write=30,
                pool=15
            )
        )
        temporary_client = True

    # --------------------------------------------------------
    # REQUEST BODY
    # --------------------------------------------------------

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Wandriq, an expert global travel planning assistant. "
                    "Be practical, specific and accurate. "
                    "Never invent impossible travel information. "
                    "When asked for JSON, return only valid JSON."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": tokens,
        "temperature": 0.5
    }

    # JSON Object Mode
    if json_mode:
        body["response_format"] = {
            "type": "json_object"
        }

    # GPT-OSS supports reasoning effort.
    if model.startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"

    # --------------------------------------------------------
    # API REQUEST
    # --------------------------------------------------------

    try:

        response = await client.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json=body
        )

    except (
        httpx.ReadError,
        httpx.ConnectError,
        httpx.TimeoutException,
        httpx.RemoteProtocolError,
        httpx.PoolTimeout
    ) as e:

        log.warning(
            f"Groq network error attempt {attempt}: "
            f"{type(e).__name__}: {e}"
        )

        if temporary_client:
            await client.aclose()

        if attempt < 3:
            await asyncio.sleep(attempt * 2)

            return await ask(
                prompt=prompt,
                tokens=tokens,
                model=model,
                attempt=attempt + 1,
                json_mode=json_mode
            )

        raise HTTPException(
            status_code=503,
            detail="Groq network error. Please try again."
        )

    except Exception as e:

        if temporary_client:
            await client.aclose()

        log.exception(f"Unexpected Groq error: {e}")

        raise HTTPException(
            status_code=500,
            detail="Unexpected AI service error."
        )

    finally:
        if temporary_client and not client.is_closed:
            await client.aclose()

    # --------------------------------------------------------
    # HTTP ERROR HANDLING
    # --------------------------------------------------------

    if not response.is_success:

        error_message = ""

        try:
            payload = response.json()

            error_message = (
                payload
                .get("error", {})
                .get("message", "")
            )

        except Exception:
            error_message = response.text[:500]

        log.error(
            f"Groq HTTP {response.status_code}: {error_message}"
        )

        # ----------------------------------------------------
        # INVALID / DEPRECATED MODEL
        # ----------------------------------------------------

        if response.status_code in (400, 404):

            if model != GROQ_FALLBACK:

                log.warning(
                    f"Primary model failed. "
                    f"Switching to {GROQ_FALLBACK}"
                )

                await asyncio.sleep(1)

                return await ask(
                    prompt=prompt,
                    tokens=tokens,
                    model=GROQ_FALLBACK,
                    attempt=1,
                    json_mode=json_mode
                )

        # ----------------------------------------------------
        # AUTH ERROR
        # ----------------------------------------------------

        if response.status_code == 401:

            raise HTTPException(
                status_code=401,
                detail=(
                    "Invalid Groq API key. "
                    "Create/check your key in Groq Console."
                )
            )

        # ----------------------------------------------------
        # FORBIDDEN
        # ----------------------------------------------------

        if response.status_code == 403:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Groq rejected this request. "
                    "Check your API key permissions/account."
                )
            )

        # ----------------------------------------------------
        # RATE LIMIT
        # ----------------------------------------------------

        if response.status_code == 429:

            retry_after = response.headers.get(
                "retry-after",
                "5"
            )

            try:
                wait_seconds = min(
                    max(float(retry_after), 2),
                    30
                )
            except Exception:
                wait_seconds = 5

            log.warning(
                f"Groq rate limit. Waiting {wait_seconds}s"
            )

            if attempt < 3:

                await asyncio.sleep(wait_seconds)

                return await ask(
                    prompt=prompt,
                    tokens=tokens,
                    model=model,
                    attempt=attempt + 1,
                    json_mode=json_mode
                )

            raise HTTPException(
                status_code=429,
                detail=(
                    "Groq rate limit reached. "
                    "Please wait a little and try again."
                )
            )

        # ----------------------------------------------------
        # SERVER ERRORS
        # ----------------------------------------------------

        if response.status_code in (500, 502, 503, 504):

            if attempt < 3:

                await asyncio.sleep(attempt * 3)

                return await ask(
                    prompt=prompt,
                    tokens=tokens,
                    model=model,
                    attempt=attempt + 1,
                    json_mode=json_mode
                )

            raise HTTPException(
                status_code=503,
                detail=(
                    "Groq is temporarily unavailable. "
                    "Please try again."
                )
            )

        # ----------------------------------------------------
        # OTHER ERRORS
        # ----------------------------------------------------

        raise HTTPException(
            status_code=response.status_code,
            detail=f"AI error: {error_message or 'Unknown Groq error'}"
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    try:

        data = response.json()

        choices = data.get("choices", [])

        if not choices:
            raise ValueError("Groq returned no choices")

        content = (
            choices[0]
            .get("message", {})
            .get("content", "")
        )

        if not content:
            raise ValueError("Groq returned empty content")

    except Exception as e:

        log.error(
            f"Invalid Groq response: {e}"
        )

        raise HTTPException(
            status_code=502,
            detail="Groq returned an invalid response."
        )

    usage = data.get("usage", {})

    log.info(
        f"Groq ← prompt={usage.get('prompt_tokens')} "
        f"completion={usage.get('completion_tokens')}"
    )

    return content.strip()


# ============================================================
# JSON PARSER
# ============================================================

def jp(text: str) -> dict:

    if not text:
        return {
            "_e": "empty_response"
        }

    text = text.strip()

    # Remove markdown fences
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```\s*$",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:
        result = json.loads(text)

        if isinstance(result, dict):
            return result

    except Exception:
        pass

    # --------------------------------------------------------
    # Extract first JSON object
    # --------------------------------------------------------

    start = text.find("{")

    if start == -1:
        return {
            "_e": text[:200] or "no_json_object"
        }

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(text)):

        ch = text[i]

        if escaped:
            escaped = False
            continue

        if ch == "\\" and in_string:
            escaped = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1

        elif ch == "}":

            depth -= 1

            if depth == 0:

                candidate = text[start:i + 1]

                try:

                    result = json.loads(candidate)

                    if isinstance(result, dict):
                        return result

                except Exception as e:

                    log.error(
                        f"JSON extraction failed: {e}"
                    )

                    return {
                        "_e": "bad_json"
                    }

    return {
        "_e": "unclosed_json"
    }


# ============================================================
# EXCHANGE RATE
# ============================================================

async def get_rate(currency: str) -> float:

    currency = currency.upper().strip()

    if currency == "USD":
        return 1.0

    try:

        async with httpx.AsyncClient(
            timeout=8
        ) as c:

            response = await c.get(
                "https://open.er-api.com/v6/latest/USD"
            )

            response.raise_for_status()

            data = response.json()

            rate = (
                data
                .get("rates", {})
                .get(currency)
            )

            if rate is None:
                log.warning(
                    f"No exchange rate found for {currency}"
                )
                return 1.0

            return float(rate)

    except Exception as e:

        log.warning(
            f"Exchange rate failed for {currency}: {e}"
        )

        return 1.0


# ============================================================
# WEATHER
# ============================================================

async def get_weather(city: str) -> dict:

    try:

        async with httpx.AsyncClient(
            timeout=8
        ) as c:

            # ------------------------------------------------
            # GEOCODING
            # ------------------------------------------------

            geocode = await c.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": city.split(",")[0].strip(),
                    "count": 1,
                    "language": "en",
                    "format": "json"
                }
            )

            geocode.raise_for_status()

            results = (
                geocode
                .json()
                .get("results", [])
            )

            if not results:
                return {}

            latitude = results[0]["latitude"]
            longitude = results[0]["longitude"]

            # ------------------------------------------------
            # WEATHER
            # ------------------------------------------------

            weather = await c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "daily": (
                        "temperature_2m_max,"
                        "temperature_2m_min,"
                        "weathercode"
                    ),
                    "forecast_days": 7,
                    "timezone": "auto"
                }
            )

            weather.raise_for_status()

            daily = (
                weather
                .json()
                .get("daily", {})
            )

            if not daily:
                return {}

            weather_map = {
                0: "Sunny",
                1: "Mostly sunny",
                2: "Partly cloudy",
                3: "Overcast",
                45: "Foggy",
                48: "Foggy",
                51: "Light drizzle",
                53: "Drizzle",
                55: "Heavy drizzle",
                61: "Rainy",
                63: "Rainy",
                65: "Heavy rain",
                71: "Snowy",
                73: "Snowy",
                75: "Heavy snow",
                80: "Showers",
                81: "Showers",
                82: "Heavy showers",
                95: "Thunderstorm",
                96: "Thunderstorm",
                99: "Thunderstorm"
            }

            dates = daily.get("time", [])
            maximums = daily.get(
                "temperature_2m_max",
                []
            )
            minimums = daily.get(
                "temperature_2m_min",
                []
            )
            codes = daily.get(
                "weathercode",
                []
            )

            days = []

            for i in range(
                min(
                    7,
                    len(dates),
                    len(maximums),
                    len(minimums),
                    len(codes)
                )
            ):

                days.append({
                    "date": dates[i],
                    "max": round(maximums[i]),
                    "min": round(minimums[i]),
                    "condition": weather_map.get(
                        codes[i],
                        "Variable"
                    )
                })

            return {
                "days": days
            }

    except Exception as e:

        log.warning(
            f"Weather lookup failed for {city}: {e}"
        )

        return {}


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():

    key = os.getenv(
        "GROQ_API_KEY",
        ""
    ).strip()

    key_set = bool(key) and (
        key != "paste_your_groq_key_here"
    )

    return {
        "ok": True,
        "model": GROQ_PRIMARY,
        "key_set": key_set
    }


# ============================================================
# CURRENCIES ENDPOINT
# ============================================================

@app.get("/api/currencies")
def currencies():

    return {
        "currencies": CURRENCIES
    }


# ============================================================
# CHAT
# ============================================================

@app.post("/api/chat")
async def chat(req: ChatRequest):

    destination = req.destination.strip()

    if not destination:
        raise HTTPException(
            status_code=400,
            detail="Destination is required."
        )

    question = req.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question is required."
        )

    prompt = (
        f"You are a knowledgeable local travel expert "
        f"for {destination}.\n"
        f"Trip duration: {req.duration} days.\n"
        f"Travel month: {req.month}.\n"
        f"Traveler question: {question}\n\n"
        f"Give a specific, practical answer in 3-5 sentences. "
        f"Use real local knowledge. "
        f"Do not make up businesses, transport routes, "
        f"prices or attractions."
    )

    answer = await ask(
        prompt,
        tokens=450,
        json_mode=False
    )

    return {
        "answer": answer
    }


# ============================================================
# DESTINATION SUGGESTIONS
# ============================================================

@app.post("/api/suggest-destinations")
async def suggest(req: MonthRequest):

    currency = req.currency.upper().strip()

    if currency not in SYM:
        currency = "INR"

    rate = await get_rate(currency)

    # Convert user's currency budget to USD
    usd_budget = round(
        req.budget / rate
    )

    symbol = SYM.get(
        currency,
        currency
    )

    interests = ", ".join(
        req.interests[:5]
    ) if req.interests else "general sightseeing"

    prompt = f"""
Suggest 6 diverse travel destinations worldwide.

Month:
{req.month}

Budget:
{symbol}{req.budget} total

Approximate USD budget:
${usd_budget}

Travel style:
{req.travel_style}

Interests:
{interests}

Requirements:
- Include different world regions.
- Consider realistic costs.
- Consider the specified month.
- Prefer destinations appropriate for the stated budget.
- Do not invent countries or cities.
- Keep the answers concise.

Return ONLY valid JSON.

Use exactly this structure:

{{
  "destinations": [
    {{
      "city": "City, Country",
      "tagline": "short tagline",
      "why_now": "why this month works",
      "budget_fit": "excellent",
      "crowd_level": "low",
      "season": "shoulder",
      "avg_daily_usd": 60,
      "emoji": "🌍"
    }}
  ]
}}

Return exactly 6 destinations.
"""

    raw = await ask(
        prompt,
        tokens=900,
        json_mode=True
    )

    data = jp(raw)

    if "_e" in data:

        log.error(
            f"Destination JSON failed: {raw[:500]}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not generate destinations. Please try again."
        )

    destinations = data.get(
        "destinations",
        []
    )

    if not isinstance(destinations, list):
        raise HTTPException(
            status_code=500,
            detail="Invalid destination response."
        )

    return {
        "destinations": destinations[:6]
    }


# ============================================================
# GENERATE ITINERARY
# ============================================================

@app.post("/api/generate-itinerary")
async def generate(req: TripRequest):

    # --------------------------------------------------------
    # BASIC VALIDATION
    # --------------------------------------------------------

    destination = req.destination.strip()

    if not destination:
        raise HTTPException(
            status_code=400,
            detail="Destination is required."
        )

    if req.budget <= 0:
        raise HTTPException(
            status_code=400,
            detail="Budget must be greater than zero."
        )

    # Limit itinerary to 7 days
    duration = max(
        1,
        min(req.duration, 7)
    )

    currency = req.currency.upper().strip()

    if currency not in SYM:
        currency = "INR"

    month = req.month.strip() or "April"

    travel_style = (
        req.travel_style.strip()
        or "mid-range"
    )

    trip_type = (
        req.trip_type.strip()
        or "solo"
    )

    interests = (
        ", ".join(req.interests[:4])
        if req.interests
        else "sightseeing"
    )

    wishlist = (
        (req.wishlist or "none")
        .strip()
        [:120]
    )

    # --------------------------------------------------------
    # EXCHANGE RATE
    # --------------------------------------------------------

    rate = await get_rate(currency)

    usd_budget = round(
        req.budget / rate
    )

    symbol = SYM.get(
        currency,
        currency
    )

    # --------------------------------------------------------
    # BUDGET ESTIMATE
    # --------------------------------------------------------

    accommodation = round(
        usd_budget * 0.35
    )

    food = round(
        usd_budget * 0.22
    )

    transport = round(
        usd_budget * 0.15
    )

    activities = round(
        usd_budget * 0.13
    )

    misc = round(
        usd_budget * 0.07
    )

    estimated_total = round(
        usd_budget * 0.92
    )

    # ========================================================
    # PROMPT A: OVERVIEW + HOTELS + RESTAURANTS
    # ========================================================

    prompt_a = f"""
Create travel information for this trip:

Destination:
{destination}

Duration:
{duration} days

Month:
{month}

Budget:
{symbol}{req.budget} {currency}

Approximate USD budget:
${usd_budget}

Travel style:
{travel_style}

Trip type:
{trip_type}

Interests:
{interests}

Wishlist:
{wishlist}

IMPORTANT:
- Use real places and businesses where possible.
- Do not invent hotel or restaurant names.
- If uncertain, use a well-known real place rather than fabricating one.
- Keep prices approximate.
- Costs in the JSON are USD.
- Do not write markdown.

Return ONLY valid JSON in exactly this structure:

{{
  "overview": "2 vivid sentences about the trip",
  "weather_note": "typical weather in the specified month",
  "visa_info": "very short visa guidance",
  "safety_rating": "general safety note",
  "crowd_level": "low, medium or high",
  "best_for": [
    "interest 1",
    "interest 2"
  ],

  "cost_breakdown": {{
    "accommodation_usd": {accommodation},
    "food_usd": {food},
    "transport_usd": {transport},
    "activities_usd": {activities},
    "misc_usd": {misc},
    "total_usd": {estimated_total}
  }},

  "hotels": [
    {{
      "name": "real budget hotel",
      "type": "budget",
      "price_per_night_usd": 20,
      "rating": 4.0,
      "highlight": "short feature",
      "eco_certified": false
    }},
    {{
      "name": "real mid-range hotel",
      "type": "mid",
      "price_per_night_usd": 65,
      "rating": 4.4,
      "highlight": "short feature",
      "eco_certified": false
    }},
    {{
      "name": "real luxury hotel",
      "type": "luxury",
      "price_per_night_usd": 160,
      "rating": 4.8,
      "highlight": "short feature",
      "eco_certified": false
    }}
  ],

  "top_restaurants": [
    {{
      "name": "real restaurant",
      "cuisine": "cuisine",
      "avg_cost_usd": 6,
      "rating": 4.5,
      "must_try": "dish",
      "wishlist_match": false
    }},
    {{
      "name": "real restaurant",
      "cuisine": "cuisine",
      "avg_cost_usd": 15,
      "rating": 4.7,
      "must_try": "dish",
      "wishlist_match": false
    }},
    {{
      "name": "real restaurant",
      "cuisine": "cuisine",
      "avg_cost_usd": 30,
      "rating": 4.8,
      "must_try": "dish",
      "wishlist_match": false
    }}
  ]
}}
"""

    # ========================================================
    # PROMPT B: SUSTAINABILITY + PACKING + PHRASES
    # ========================================================

    prompt_b = f"""
Create practical travel tips for:

Destination:
{destination}

Month:
{month}

Duration:
{duration} days

Travel style:
{travel_style}

Trip type:
{trip_type}

Interests:
{interests}

Return ONLY valid JSON.

Use exactly this structure:

{{
  "sustainable_tips": [
    {{
      "icon": "🚆",
      "title": "short title",
      "detail": "specific local transport advice"
    }},
    {{
      "icon": "🏡",
      "title": "stay local",
      "detail": "specific accommodation advice"
    }},
    {{
      "icon": "🛍",
      "title": "shop local",
      "detail": "specific local shopping advice"
    }},
    {{
      "icon": "🌿",
      "title": "eco activity",
      "detail": "specific green activity"
    }}
  ],

  "packing_list": [
    "item 1",
    "item 2",
    "item 3",
    "item 4",
    "item 5",
    "item 6",
    "item 7",
    "item 8",
    "item 9",
    "item 10"
  ],

  "phrases": [
    {{
      "original": "Hello",
      "translation": "local language",
      "pronunciation": "phonetic pronunciation"
    }},
    {{
      "original": "Thank you",
      "translation": "local language",
      "pronunciation": "phonetic pronunciation"
    }},
    {{
      "original": "How much?",
      "translation": "local language",
      "pronunciation": "phonetic pronunciation"
    }},
    {{
      "original": "Where is...?",
      "translation": "local language",
      "pronunciation": "phonetic pronunciation"
    }},
    {{
      "original": "Delicious!",
      "translation": "local language",
      "pronunciation": "phonetic pronunciation"
    }}
  ]
}}

Use the actual local language of the destination.
Packing should match the climate in {month}.
"""

    # ========================================================
    # PROMPT C: DAILY ITINERARY
    # ========================================================

    prompt_c = f"""
Create a {duration}-day travel itinerary.

Destination:
{destination}

Month:
{month}

Travel style:
{travel_style}

Trip type:
{trip_type}

Interests:
{interests}

Wishlist:
{wishlist}

Rules:

1. Every day must have a different area or theme.
2. Activities must be realistic.
3. Use real place names.
4. Do not invent attractions.
5. Avoid repeating the same activity.
6. Match activities to the trip type.
7. Include practical local transport.
8. Include real restaurants where possible.
9. Mark wishlist_match true only when an activity genuinely matches the wishlist.
10. Return exactly {duration} days.
11. Return ONLY valid JSON.
12. No markdown.

Use exactly this structure:

{{
  "days": [
    {{
      "day": 1,
      "title": "descriptive title",
      "theme": "area or theme",

      "morning": {{
        "activity": "activity",
        "detail": "real place",
        "cost_usd": 5,
        "wishlist_match": false
      }},

      "afternoon": {{
        "activity": "different activity",
        "detail": "real place",
        "cost_usd": 10,
        "wishlist_match": false
      }},

      "evening": {{
        "activity": "evening activity",
        "detail": "real place",
        "cost_usd": 0,
        "wishlist_match": false
      }},

      "lunch_spot": {{
        "name": "real restaurant",
        "cuisine": "cuisine",
        "avg_cost_usd": 6,
        "rating": 4.2
      }},

      "dinner_spot": {{
        "name": "real restaurant",
        "cuisine": "cuisine",
        "avg_cost_usd": 15,
        "rating": 4.5
      }},

      "transport": "practical local transport"
    }}
  ]
}}

Return exactly {duration} objects inside days.
"""

    # ========================================================
    # GENERATE AI SECTIONS
    # ========================================================

    log.info(
        f"Generating itinerary: "
        f"{destination}, {duration}d, {currency}"
    )

    try:

        raw_a = await ask(
            prompt_a,
            tokens=1000,
            json_mode=True
        )

        await asyncio.sleep(0.5)

        raw_b = await ask(
            prompt_b,
            tokens=800,
            json_mode=True
        )

        await asyncio.sleep(0.5)

        raw_c = await ask(
            prompt_c,
            tokens=max(
                1200,
                250 * duration
            ),
            json_mode=True
        )

    except HTTPException:
        raise

    except Exception as e:

        log.exception(
            f"Itinerary AI generation failed: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not generate itinerary."
        )

    # ========================================================
    # WEATHER
    # ========================================================

    weather = await get_weather(
        destination
    )

    # ========================================================
    # PARSE JSON
    # ========================================================

    meta = jp(raw_a)
    tips = jp(raw_b)
    days_data = jp(raw_c)

    # --------------------------------------------------------
    # META VALIDATION
    # --------------------------------------------------------

    if "_e" in meta:

        log.error(
            f"Meta JSON failed: {raw_a[:500]}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not parse trip overview. "
                "Please try again."
            )
        )

    # --------------------------------------------------------
    # TIPS VALIDATION
    # --------------------------------------------------------

    if "_e" in tips:

        log.error(
            f"Tips JSON failed: {raw_b[:500]}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not parse travel tips. "
                "Please try again."
            )
        )

    # --------------------------------------------------------
    # DAYS VALIDATION
    # --------------------------------------------------------

    if "_e" in days_data:

        log.error(
            f"Days JSON failed: {raw_c[:500]}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not parse itinerary days. "
                "Please try again."
            )
        )

    days = days_data.get(
        "days",
        []
    )

    if not isinstance(days, list) or not days:

        log.error(
            f"Invalid days structure: {days_data}"
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "The AI did not return a valid itinerary. "
                "Please try again."
            )
        )

    # ========================================================
    # NORMALIZE DAYS
    # ========================================================

    days = days[:duration]

    days.sort(
        key=lambda d: d.get(
            "day",
            999
        )
    )

    for index, day in enumerate(days):

        if not isinstance(day, dict):
            continue

        day["day"] = index + 1

        # Make sure expected objects exist
        if not isinstance(
            day.get("morning"),
            dict
        ):
            day["morning"] = {
                "activity": "",
                "detail": "",
                "cost_usd": 0,
                "wishlist_match": False
            }

        if not isinstance(
            day.get("afternoon"),
            dict
        ):
            day["afternoon"] = {
                "activity": "",
                "detail": "",
                "cost_usd": 0,
                "wishlist_match": False
            }

        if not isinstance(
            day.get("evening"),
            dict
        ):
            day["evening"] = {
                "activity": "",
                "detail": "",
                "cost_usd": 0,
                "wishlist_match": False
            }

        if not isinstance(
            day.get("lunch_spot"),
            dict
        ):
            day["lunch_spot"] = {
                "name": "",
                "cuisine": "",
                "avg_cost_usd": 0,
                "rating": 0
            }

        if not isinstance(
            day.get("dinner_spot"),
            dict
        ):
            day["dinner_spot"] = {
                "name": "",
                "cuisine": "",
                "avg_cost_usd": 0,
                "rating": 0
            }

    # ========================================================
    # FINAL RESPONSE
    # ========================================================

    return {
        **meta,
        **tips,

        "days": days,

        "destination": destination,
        "duration": duration,
        "month": month,

        "display_currency": currency,

        "exchange_rate": round(
            rate,
            4
        ),

        "currency_symbol": symbol,

        "weather_forecast": weather
    }