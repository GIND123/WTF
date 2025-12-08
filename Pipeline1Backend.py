import os
import re
import json
import requests
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from google import genai
from google.genai import types

import uvicorn
from dotenv import load_dotenv


# ============================================================================
# ENV + CLIENTS
# ============================================================================
load_dotenv()

GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
YELP_API_KEY = os.environ.get("YELP_API_KEY")
YELP_AI_ENDPOINT = os.environ.get(
    "YELP_AI_ENDPOINT", "https://api.yelp.com/ai/chat/v2"
)

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY or GEMINI_API_KEY in environment")

if not YELP_API_KEY:
    raise RuntimeError("Missing YELP_API_KEY in environment")

client = genai.Client(api_key=GEMINI_API_KEY)

# ✅ Correct model from your rate-limit dashboard
MODEL_FAST = "gemini-2.5-flash-lite"


# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(title="Yelp AI Backend", version="1.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# GUARDRAIL PROMPT
# ============================================================================
GUARDRAIL_SYS = """
You are a safety + relevance gate for an app that ONLY helps users find places to GET, EAT, or USE
food, drinks, groceries, desserts, and restaurant/hotel services.

You will see:
- An IMAGE
- A short USER INTENT

Output ONLY valid JSON:

{
  "allowed": true/false,
  "reason": "<short safety/relevance explanation>",
  "category": "<food_or_venue | face_only | adult_or_nudity | violence_or_gore |
               drugs_or_weapons | hate_or_extremism | unrelated | uncertain>"
}

Rules:
- If anything unsafe (nudity, violence, drugs, weapons, hate) is detected → allowed=false.
- If user intent is unrelated to food/venues → allowed=false.
- Otherwise → allowed=true.
"""


# ============================================================================
# JSON / TEXT HELPERS
# ============================================================================
_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_code_fences(text: str) -> str:
    return _CODE_FENCE_RE.sub("", (text or "").strip())


def _extract_json_obj_substring(text: str) -> Optional[str]:
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        return text[s:e + 1]
    return None


def _safe_json_parse(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    cleaned = _strip_code_fences(text)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    sub = _extract_json_obj_substring(cleaned)
    if sub:
        try:
            parsed = json.loads(sub)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None

    return None


def _truncate_to_sentence(text: str, max_len: int = 1000) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text

    truncated = text[:max_len]
    p = max(
        truncated.rfind("."),
        truncated.rfind("!"),
        truncated.rfind("?"),
    )

    return truncated[: p + 1] if p != -1 else truncated


# ============================================================================
# PROMPT BUILDERS
# ============================================================================
def _build_prompt(
    location: str,
    latitude: str,
    longitude: str,
    date: str,
    time: str,
) -> str:

    latlon_block = ""
    if latitude or longitude:
        latlon_block = f"Latitude: {latitude or 'N/A'}\nLongitude: {longitude or 'N/A'}\n"

    return (
        "Write exactly ONE natural-language Yelp search sentence.\n"
        f"Location: {location}\n"
        f"{latlon_block}"
        f"Date: {date}\n"
        f"Time: {time}\n"
        "Goal:\n"
        "- Find places serving the food shown OR\n"
        "- Find TRENDING / POPULAR nearby food or venues if asked.\n"
        "Rules:\n"
        "- Ask for MANY options sorted by popularity/reviews.\n"
        "- Use clear first-person phrasing.\n"
        "- Output a single sentence only.\n"
        "- No meta or markdown.\n"
        "- Under 900 characters.\n"
    )


# ============================================================================
# GEMINI FUNCTIONS
# ============================================================================
def _guardrail_check_image(
    image_bytes: bytes,
    mime_type: str,
    user_intent: str,
) -> Tuple[bool, str, str]:

    try:
        resp = client.models.generate_content(
            model=MODEL_FAST,
            contents=[
                GUARDRAIL_SYS,
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                f"User intent: {user_intent}",
            ],
            config={"response_mime_type": "application/json"},
        )

        raw = (getattr(resp, "text", "") or "").strip()
        data = _safe_json_parse(raw) or {}

    except Exception:
        return False, "Safety validation failed.", "uncertain"

    allowed = bool(data.get("allowed", False))
    reason = str(data.get("reason") or "").strip()
    category = str(data.get("category") or "uncertain").strip()

    if not reason:
        return False, "Unable to verify image safety and relevance.", "uncertain"

    return allowed, reason, category


def _gemini_image_to_query(
    image_bytes: bytes,
    mime_type: str,
    user_query: str,
    location: str,
    latitude: str,
    longitude: str,
    date: str,
    time: str,
) -> str:

    instruction = _build_prompt(location, latitude, longitude, date, time)

    resp = client.models.generate_content(
        model=MODEL_FAST,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            instruction,
            f"User intent: {user_query}",
        ],
    )

    return _truncate_to_sentence(getattr(resp, "text", "") or "")


def _gemini_caption_to_query(
    user_query: str,
    location: str,
    latitude: str,
    longitude: str,
    date: str,
    time: str,
) -> str:

    instruction = _build_prompt(location, latitude, longitude, date, time)

    resp = client.models.generate_content(
        model=MODEL_FAST,
        contents=[
            instruction,
            f"User intent: {user_query}",
        ],
    )

    return _truncate_to_sentence(getattr(resp, "text", "") or "")


# ============================================================================
# YELP CALL
# ============================================================================
def _call_yelp_ai(yelp_query: str) -> Dict[str, Any]:

    headers = {
        "Authorization": f"Bearer {YELP_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {"query": yelp_query}

    r = requests.post(
        YELP_AI_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=45,
    )

    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    return r.json()


# ============================================================================
# RESULT EXTRACTION
# ============================================================================
def _extract_results(data: Dict[str, Any], yelp_query: str) -> Dict[str, Any]:

    ai_text = (data.get("response") or {}).get("text", "") or ""

    results = {
        "chat_id": data.get("chat_id"),
        "query": yelp_query,
        "ai_response_text": ai_text,
        "businesses": [],
    }

    for entity in data.get("entities") or []:
        for biz in entity.get("businesses") or []:

            loc = biz.get("location") or {}
            coords = biz.get("coordinates") or {}
            summaries = biz.get("summaries") or {}
            contextual = biz.get("contextual_info") or {}

            photos = contextual.get("photos") or []
            hours = contextual.get("business_hours") or []
            openings = (biz.get("reservation_availability") or {}).get("openings") or []

            addr = (
                loc.get("formatted_address")
                or ", ".join(
                    p
                    for p in [
                        loc.get("address1"),
                        loc.get("city"),
                        loc.get("state"),
                        loc.get("zip_code"),
                        loc.get("country"),
                    ]
                    if p
                )
                or "N/A"
            )

            photo_url = (
                photos[0].get("original_url")
                if photos and isinstance(photos[0], dict)
                else "N/A"
            )

            hours_list = []
            for h in hours:
                slots = []
                for s in h.get("business_hours", []):
                    if s.get("open_time") and s.get("close_time"):
                        slots.append(f"{s['open_time']} to {s['close_time']}")
                hours_list.append({
                    "day_of_week": h.get("day_of_week", "N/A"),
                    "hours": slots,
                })

            opening_list = []
            for d in openings:
                opening_list.append({
                    "date": d.get("date", "N/A"),
                    "slots": [
                        {
                            "time": s.get("time", "N/A"),
                            "seating_areas": s.get("seating_areas", []),
                        }
                        for s in d.get("slots", [])
                    ],
                })

            results["businesses"].append({

                "id": biz.get("id"),

                "name": biz.get("name", "N/A"),
                "address": addr,
                "yelp_url": biz.get("url", "N/A"),

                "rating": biz.get("rating", "N/A"),
                "review_count": biz.get("review_count", "N/A"),
                "price": biz.get("price", "N/A"),

                "latitude": coords.get("latitude", "N/A"),
                "longitude": coords.get("longitude", "N/A"),

                "short_summary": summaries.get("short") or contextual.get("summary") or "N/A",

                "photo_url": photo_url,
                "business_hours": hours_list,
                "reservation_openings": opening_list,

                "phone": biz.get("phone", "N/A"),
            })

    results["businesses"].sort(
        key=lambda b: (
            float(b["rating"]) if isinstance(b["rating"], (int, float)) else -1,
            int(b["review_count"]) if isinstance(b["review_count"], int) else -1,
        ),
        reverse=True,
    )

    return results


# ============================================================================
# ROUTES
# ============================================================================
@app.get("/")
def root():
    return {"status": "running", "docs": "/docs", "health": "/health"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/search-image")
async def search_image(
    image: UploadFile = File(...),
    user_query: str = Form(...),
    Location: str = Form(""),
    Latitude: str = Form(""),
    Longitude: str = Form(""),
    Date: str = Form("12/11/2025"),
    Time: str = Form("8pm"),
):

    img = await image.read()
    mime = image.content_type or "image/jpeg"

    allowed, reason, cat = _guardrail_check_image(img, mime, user_query)
    if not allowed:
        return JSONResponse(
            status_code=422,
            content={
                "status": 422,
                "message": reason,
                "category": cat,
            },
        )

    yelp_query = _gemini_image_to_query(
        img,
        mime,
        user_query,
        Location,
        Latitude,
        Longitude,
        Date,
        Time,
    )

    data = _call_yelp_ai(yelp_query)

    return _extract_results(data, yelp_query)


@app.post("/search-caption")
async def search_caption(
    user_query: str = Form(...),

    Location: str = Form(""),
    Latitude: str = Form(""),
    Longitude: str = Form(""),

    Date: str = Form("12/11/2025"),
    Time: str = Form("8pm"),
):

    yelp_query = _gemini_caption_to_query(
        user_query,
        Location,
        Latitude,
        Longitude,
        Date,
        Time,
    )

    data = _call_yelp_ai(yelp_query)

    return _extract_results(data, yelp_query)


# ============================================================================
# LOCAL RUN
# ============================================================================
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        log_level="info",
    )
