# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv
from google import genai
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory.vertex_ai_memory_bank_service import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.load_memory_tool import load_memory_tool
from google.adk.tools.preload_memory_tool import preload_memory_tool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# Load local .env environment variables if present
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-11269a8adae1"
GCS_BUCKET_NAME = "travel-concierge-media-11269a8adae1"

# Load Agent Engine resource name from deployment_metadata.json if available
metadata_file = Path(__file__).parent.parent / "deployment_metadata.json"
agent_engine_resource_name = None
if metadata_file.exists():
    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)

# Memory service for Vertex AI Memory Bank
agent_engine_id = agent_engine_resource_name.split("/")[-1] if agent_engine_resource_name else "6759540201845948416"
memory_service = VertexAiMemoryBankService(
    project=FIRESTORE_PROJECT_ID,
    location="us-east1",
    agent_engine_id=agent_engine_id,
)


def _get_firestore_client() -> firestore.Client:
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


async def generate_destination_artwork(
    prompt: str,
    tool_context: ToolContext,
) -> dict:
    """Generate a visual artwork image for a travel destination or landmark using gemini-3.1-flash-lite-image in the global region.

    Args:
        prompt: Detailed description of the travel destination or landmark scene to generate artwork for.
        tool_context: ADK ToolContext used to save the generated image as an artifact for the Playground.

    Returns:
        A dict containing the public Cloud Storage image URL (https://storage.googleapis.com/<bucket>/<object>) and status.
    """
    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    response = genai_client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
    )

    image_bytes = None
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                break

    if not image_bytes:
        return {"error": "Failed to generate image bytes from model."}

    # Generate a clean filename for the artifact and Cloud Storage object
    safe_slug = "".join(c if c.isalnum() else "_" for c in prompt[:30]).lower().strip("_")
    filename = f"artwork_{safe_slug}_{int(datetime.datetime.now().timestamp())}.jpg"

    # 1. Save artifact with tool_context for Playground Artifacts panel
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
    await tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 2. Upload image bytes directly to Cloud Storage bucket without saving to local file
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob_path = f"destinations/{filename}"
    blob = bucket.blob(blob_path)
    blob.upload_from_string(image_bytes, content_type="image/jpeg")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob_path}"
    return {
        "status": "success",
        "prompt": prompt,
        "filename": filename,
        "public_url": public_url,
    }


async def generate_destination_video(
    prompt: str,
    tool_context: ToolContext,
) -> dict:
    """Generate a short video preview for a travel destination or landmark using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Args:
        prompt: Description of the travel destination, landmark, or scene to generate a video for (e.g. 'Kyoto cherry blossoms in spring' or 'Eiffel Tower illuminated at night').
        tool_context: ADK ToolContext used to save the generated video as an artifact for the Playground.

    Returns:
        A dict containing the public Cloud Storage video URL (https://storage.googleapis.com/<bucket>/<object>) and status.
    """
    genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
    interaction = genai_client.interactions.create(
        model="gemini-omni-flash-preview",
        input=f"A scenic short video loop of {prompt}",
    )

    video_bytes = None
    if hasattr(interaction, "output_video") and interaction.output_video and getattr(interaction.output_video, "data", None):
        data = interaction.output_video.data
        if isinstance(data, str):
            video_bytes = base64.b64decode(data)
        elif isinstance(data, bytes):
            video_bytes = data

    if not video_bytes and hasattr(interaction, "outputs") and interaction.outputs:
        for out in interaction.outputs:
            output_list = getattr(out, "output", []) or []
            for item in output_list:
                if getattr(item, "type", None) == "video" or getattr(item, "mime_type", "").startswith("video/"):
                    data = getattr(item, "data", None)
                    if data:
                        if isinstance(data, str):
                            video_bytes = base64.b64decode(data)
                        elif isinstance(data, bytes):
                            video_bytes = data
                        break

    if not video_bytes:
        return {"status": "error", "message": "Failed to generate video or extract video bytes from gemini-omni-flash-preview response."}

    # 1. Save artifact for Playground's Artifacts panel
    filename = f"destination_video_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    try:
        tool_context.save_artifact(
            filename=filename,
            contents=video_bytes,
            mime_type="video/mp4",
        )
    except Exception as e:
        print(f"Warning: Failed to save video artifact: {e}")

    # 2. Upload video bytes to public Cloud Storage bucket
    object_name = f"videos/{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
    bucket = storage_client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(object_name)
    blob.upload_from_string(video_bytes, content_type="video/mp4")

    public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{object_name}"
    return {
        "status": "success",
        "video_url": public_url,
        "message": f"Successfully generated video preview for '{prompt}'",
    }


def geocode_address(address: str) -> dict:
    """Convert an address or location name into geographic coordinates (latitude and longitude) using Google Maps Geocoding API.

    Args:
        address: The address or location query (e.g. 'Kyoto Station, Japan' or 'Eiffel Tower, Paris').

    Returns:
        A dict containing formatted_address and location (lat, lng coordinates).
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    query = urllib.parse.quote(address)
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={query}&key={api_key}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "OK" and data.get("results"):
                first = data["results"][0]
                loc = first["geometry"]["location"]
                return {
                    "query_address": address,
                    "formatted_address": first.get("formatted_address"),
                    "location": {"latitude": loc.get("lat"), "longitude": loc.get("lng")},
                }
            return {"error": f"Geocoding failed for address '{address}'. Status: {data.get('status')}"}
    except Exception as e:
        return {"error": f"Failed to geocode address: {e}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> list[dict]:
    """Find nearby places of a given type around coordinates using Google Places API (New).

    Args:
        latitude: Geographic latitude coordinate (e.g. 35.0116).
        longitude: Geographic longitude coordinate (e.g. 135.7681).
        place_type: Type of places to search for (e.g. 'restaurant', 'cafe', 'tourist_attraction', 'museum', 'hotel', 'ramen_restaurant').
        radius_meters: Search radius in meters around coordinates (default: 1000.0).

    Returns:
        A list of nearby place dicts containing name, address, location coordinates, and types.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types",
    }
    body = {
        "includedTypes": [place_type.lower().strip()],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius_meters,
            }
        },
    }

    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            places_list = data.get("places", [])
            results = []
            for p in places_list:
                display_name = p.get("displayName", {}).get("text", "Unknown")
                results.append(
                    {
                        "name": display_name,
                        "address": p.get("formattedAddress"),
                        "location": p.get("location"),
                        "types": p.get("types", []),
                    }
                )
            return results
    except Exception as e:
        return [{"error": f"Failed to fetch nearby places: {e}"}]


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The string query containing city or timezone request.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


def convert_currency(amount: float, from_currency: str = "USD", to_currency: str = "JPY") -> dict:
    """Convert a monetary amount between currencies using live exchange rates.

    Args:
        amount: The monetary amount to convert (e.g. 100.0 or 180.0).
        from_currency: 3-letter currency code to convert from (e.g., 'USD', 'EUR').
        to_currency: 3-letter target currency code to convert to (e.g., 'JPY', 'EUR', 'GBP').

    Returns:
        A dict containing conversion details and the calculated converted amount.
    """
    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()

    url = f"https://open.er-api.com/v6/latest/{from_curr}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data.get("result") == "success" and to_curr in data.get("rates", {}):
                rate = data["rates"][to_curr]
                converted = round(amount * rate, 2)
                return {
                    "amount": amount,
                    "from_currency": from_curr,
                    "to_currency": to_curr,
                    "exchange_rate": rate,
                    "converted_amount": converted,
                }
    except Exception:
        pass

    fallback_rates = {
        "USD": {"JPY": 150.0, "EUR": 0.92, "GBP": 0.78, "CAD": 1.35, "AUD": 1.50, "MAD": 10.0},
        "EUR": {"USD": 1.09, "JPY": 163.0, "GBP": 0.85},
    }
    rate = fallback_rates.get(from_curr, {}).get(to_curr, 1.0)
    return {
        "amount": amount,
        "from_currency": from_curr,
        "to_currency": to_curr,
        "exchange_rate": rate,
        "converted_amount": round(amount * rate, 2),
        "note": "Rate retrieved using fallback standard exchange table.",
    }


def get_destination_wiki_summary(location_name: str) -> dict:
    """Fetch factual background summary, location description, and image URL from Wikipedia for a destination.

    Args:
        location_name: The name of the city, landmark, or region (e.g. 'Kyoto', 'Santorini', 'Mount Fuji').

    Returns:
        A dict containing title, description, summary, coordinates, image URL, and wiki link.
    """
    clean_name = location_name.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_name}"

    user_agent = os.environ.get("WIKI_USER_AGENT", "TravelConciergeAgent/1.0 (contact@example.com)")
    headers = {"User-Agent": user_agent}
    api_key = os.environ.get("WIKI_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return {
                "title": data.get("title"),
                "description": data.get("description"),
                "summary": data.get("extract"),
                "coordinates": data.get("coordinates"),
                "image_url": data.get("thumbnail", {}).get("source"),
                "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page"),
            }
    except Exception as e:
        return {"error": f"Could not retrieve Wikipedia summary for '{location_name}': {e}"}


def search_destinations(query: str = "", max_budget_usd: int = None) -> list[dict]:
    """Search for travel destinations in the Firestore database.

    Args:
        query: Optional search keyword to match against destination name, country, or tags (e.g. 'Japan', 'beach', 'hiking').
        max_budget_usd: Optional maximum estimated daily budget in USD.

    Returns:
        A list of matching destination records from Firestore.
    """
    db = _get_firestore_client()
    docs = db.collection("destinations").stream()
    results = []
    q_lower = query.lower().strip() if query else ""

    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id

        if max_budget_usd is not None and data.get("estimated_cost_per_day_usd", 0) > max_budget_usd:
            continue

        if q_lower:
            searchable_text = f"{data.get('name', '')} {data.get('country', '')} {data.get('description', '')} {' '.join(data.get('tags', []))}".lower()
            if q_lower not in searchable_text:
                continue

        results.append(data)

    return results


def add_destination(
    name: str,
    country: str,
    description: str,
    best_season: str,
    estimated_cost_per_day_usd: int,
    tags: list[str] = None,
) -> dict:
    """Add a new travel destination to the Firestore database.

    Args:
        name: Name of the destination (e.g., 'Kyoto').
        country: Country where destination is located (e.g., 'Japan').
        description: Summary of highlights and attraction features.
        best_season: Best time/season of the year to visit.
        estimated_cost_per_day_usd: Estimated average daily cost in USD.
        tags: List of descriptive tags (e.g. ['culture', 'temples', 'food']).

    Returns:
        A dict indicating success and the newly created document ID.
    """
    db = _get_firestore_client()
    if tags is None:
        tags = []

    doc_id = f"{name.lower().replace(' ', '-')}-{country.lower().replace(' ', '-')}"
    doc_ref = db.collection("destinations").document(doc_id)

    item_data = {
        "name": name,
        "country": country,
        "description": description,
        "best_season": best_season,
        "estimated_cost_per_day_usd": estimated_cost_per_day_usd,
        "tags": tags,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    doc_ref.set(item_data)
    return {"status": "success", "id": doc_id, "data": item_data}


def get_destination_details(destination_id: str) -> dict:
    """Retrieve detailed information about a specific travel destination by ID from Firestore.

    Args:
        destination_id: The document ID of the destination (e.g. 'kyoto-japan').

    Returns:
        The destination record dict or an error message if not found.
    """
    db = _get_firestore_client()
    doc = db.collection("destinations").document(destination_id).get()
    if doc.exists:
        data = doc.to_dict()
        data["id"] = doc.id
        return data
    else:
        return {"error": f"Destination with ID '{destination_id}' not found."}


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description="You are an expert AI Travel Concierge Assistant with Memory Bank integration.",
    workflow_description="""Analyze the travel request and return structured UI when appropriate.
IMPORTANT: You MUST remember, retrieve, and strictly respect all user allergies (e.g., food allergies such as peanuts, shellfish, dairy, gluten, or environmental/medical allergies).
- Whenever a user shares an allergy, dietary restriction, or health preference, remember it so it persists in the Memory Bank.
- Whenever making recommendations (restaurants, places, foods, activities, or travel itineraries), check user memory to ensure no recommended items conflict with the user's allergies or dietary restrictions.
- Use load_memory_tool and preload_memory_tool to search and recall past user conversation memory.
- Use generate_destination_artwork for destination visuals, generate_destination_video for short video previews, geocode_address for coordinate lookup, find_nearby_places for nearby spots, Wikipedia tools for background facts, convert_currency for budget planning, and Firestore destination tools for recommendations.""",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=instruction,
    after_model_callback=a2ui_callback,
    tools=[
        preload_memory_tool,
        load_memory_tool,
        get_weather,
        get_current_time,
        convert_currency,
        geocode_address,
        find_nearby_places,
        generate_destination_artwork,
        generate_destination_video,
        get_destination_wiki_summary,
        search_destinations,
        add_destination,
        get_destination_details,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)





