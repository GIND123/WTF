import os
import json
import requests
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import uvicorn
from dotenv import load_dotenv

# Load `.env` for local development so environment variables like
# `GOOGLE_API_KEY` and `YELP_API_KEY` are available to the app.
load_dotenv()

GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
YELP_API_KEY = os.environ.get("YELP_API_KEY")
YELP_AI_ENDPOINT = os.environ.get("YELP_AI_ENDPOINT", "https://api.yelp.com/ai/chat/v2")

if not GEMINI_API_KEY:
    raise RuntimeError("Missing GOOGLE_API_KEY or GEMINI_API_KEY in environment")
if not YELP_API_KEY:
    raise RuntimeError("Missing YELP_API_KEY in environment")

client = genai.Client(api_key=GEMINI_API_KEY)

app = FastAPI(title="Yelp AI Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _truncate_to_sentence(text, max_len=1000):
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_period = truncated.rfind(".")
    last_excl = truncated.rfind("!")
    last_q = truncated.rfind("?")
    last_punc = max(last_period, last_excl, last_q)
    return truncated[: last_punc + 1] if last_punc != -1 else truncated

def _build_prompt(Location, Date, Time):
    return (
        "Create a single natural-language Yelp search query.\n"
        f"Location: {Location}\n"
        f"Date: {Date}\n"
        f"Time: {Time}\n"
        "Use the image content and the user's question to craft a clear, specific, natural first-person request.\n"
        "Ask Yelp to return many relevant options and prioritize higher-rated, more popular places first.\n"
        "Write one well-structured sentence describing what to find, where, and when.\n"
        "Rules:\n"
        "- Make the description from the image as specific as possible.\n"
        "- Integrate the user's question naturally.\n"
        "- Mention location, date, and time explicitly.\n"
        "- Request multiple options ordered by rating and popularity.\n"
        "- No explanations, no meta text, no references to prompts, APIs, or images.\n"
        "- Output only the final query sentence.\n"
        "- Keep it under 900 characters."
    )

def _gemini_to_yelp_query(image_bytes, mime_type, user_query, Location, Date, Time):
    instruction = _build_prompt(Location, Date, Time)
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            instruction,
            f"User question: {user_query}",
        ],
    )
    return _truncate_to_sentence(getattr(resp, "text", ""), 1000)

def _call_yelp_ai(yelp_query):
    headers = {
        "Authorization": f"Bearer {YELP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"query": yelp_query}
    r = requests.post(YELP_AI_ENDPOINT, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json()

def _extract_results(data, yelp_query):
    ai_text = (data.get("response") or {}).get("text", "") or ""
    results = {
        "chat_id": data.get("chat_id"),
        "query": yelp_query,
        "ai_response_text": ai_text,
        "businesses": [],
    }

    entities = data.get("entities") or []
    for entity in entities:
        for biz in (entity.get("businesses") or []):
            loc = biz.get("location") or {}
            coords = biz.get("coordinates") or {}
            summaries = biz.get("summaries") or {}
            contextual = biz.get("contextual_info") or {}
            photos = contextual.get("photos") or []
            business_hours = contextual.get("business_hours") or []
            openings = (biz.get("reservation_availability") or {}).get("openings") or []

            formatted_address = loc.get("formatted_address")
            if not formatted_address:
                parts = [loc.get("address1"), loc.get("address2"), loc.get("address3")]
                city_parts = [loc.get("city"), loc.get("state"), loc.get("zip_code"), loc.get("country")]
                formatted_address = ", ".join([p for p in parts if p] + [p for p in city_parts if p])

            first_photo_url = photos[0].get("original_url") if photos and isinstance(photos[0], dict) else None

            hours_list = []
            for h in business_hours:
                day = h.get("day_of_week")
                slots = h.get("business_hours") or []
                slot_strs = []
                for s in slots:
                    ot = s.get("open_time")
                    ct = s.get("close_time")
                    if ot and ct:
                        slot_strs.append(f"{ot} to {ct}")
                hours_list.append({"day_of_week": day, "hours": slot_strs})

            opening_list = []
            for op in openings:
                date_val = op.get("date")
                slots = op.get("slots") or []
                slot_list = []
                for sl in slots:
                    slot_list.append({
                        "time": sl.get("time"),
                        "seating_areas": sl.get("seating_areas") or [],
                    })
                opening_list.append({"date": date_val, "slots": slot_list})

            biz_out = {
                "id": biz.get("id"),
                "name": biz.get("name") or "N/A",
                "address": formatted_address or "N/A",
                "yelp_url": biz.get("url") or "N/A",
                "rating": biz.get("rating") if biz.get("rating") is not None else "N/A",
                "review_count": biz.get("review_count") if biz.get("review_count") is not None else "N/A",
                "price": biz.get("price") or "N/A",
                "latitude": coords.get("latitude") if coords.get("latitude") is not None else "N/A",
                "longitude": coords.get("longitude") if coords.get("longitude") is not None else "N/A",
                "short_summary": summaries.get("short") or (contextual.get("summary") if isinstance(contextual, dict) else None) or "N/A",
                "business_hours": hours_list,
                "photo_url": first_photo_url or "N/A",
                "reservation_openings": opening_list,
            }

            results["businesses"].append(biz_out)

    return results

@app.post("/search-image")
async def search_image(
    image: UploadFile = File(...),
    user_query: str = Form(...),
    Location: str = Form("College Park, Maryland"),
    Date: str = Form("12/11/2025"),
    Time: str = Form("8pm"),
    save_to_file: bool = Form(True),
):
    try:
        image_bytes = await image.read()
        mime_type = image.content_type or "image/jpeg"
        yelp_query = _gemini_to_yelp_query(image_bytes, mime_type, user_query, Location, Date, Time)
        data = _call_yelp_ai(yelp_query)
        results = _extract_results(data, yelp_query)
        if save_to_file:
            with open("search_results.json", "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
