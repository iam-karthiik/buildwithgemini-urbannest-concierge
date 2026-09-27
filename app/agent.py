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

import os
import uuid
import datetime
import json
import urllib.parse
import urllib.request
from typing import Optional, List, Dict, Any
import logging
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
load_dotenv()

FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-d5a4eae88bb3"
ASSETS_BUCKET_NAME = "urbannest-concierge-assets-qwiklabs-gcp-03-d5a4eae88bb3"


def _get_agent_engine_resource_name() -> str:
    """Retrieves the Agent Engine resource name from deployment_metadata.json."""
    metadata_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json")
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("remote_agent_runtime_id", "")
    return ""


def _create_code_executor() -> Optional[AgentEngineSandboxCodeExecutor]:
    """Instantiates AgentEngineSandboxCodeExecutor bound to the project Agent Engine."""
    engine_resource_name = _get_agent_engine_resource_name()
    if engine_resource_name:
        return AgentEngineSandboxCodeExecutor(
            agent_engine_resource_name=engine_resource_name
        )
    return None


def _get_maps_api_key() -> str:
    """Helper to retrieve Google Maps API key from environment."""
    key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not key:
        raise ValueError("GOOGLE_MAPS_API_KEY environment variable is not set.")
    return key


def _get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with hardcoded GCP Project ID."""
    return firestore.Client(project=FIRESTORE_PROJECT_ID)


def search_listings(
    neighborhood: str = "",
    max_price: Optional[int] = None,
    bedrooms: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Search available property listings in Firestore. All parameters are optional; omit neighborhood to search all listings across the entire city.

    Args:
        neighborhood: Optional filter by neighborhood name (e.g., 'Downtown', 'Westside', 'University District'). Omit or pass empty string to search all neighborhoods.
        max_price: Optional maximum monthly rent budget.
        bedrooms: Optional minimum number of bedrooms required.

    Returns:
        List of matching listing objects.
    """
    db = _get_firestore_client()
    docs = db.collection("listings").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if neighborhood and neighborhood.lower() not in data.get("neighborhood", "").lower():
            continue
        if max_price is not None and data.get("price", 0) > max_price:
            continue
        if bedrooms is not None and data.get("bedrooms", 0) < bedrooms:
            continue
        results.append(data)
    return results


def get_listing_details(listing_id: str) -> Dict[str, Any]:
    """Get complete details for a specific property listing by listing ID.

    Args:
        listing_id: Unique listing identifier (e.g. 'apt-101', 'apt-102', 'apt-103').

    Returns:
        Listing details object including amenities, price, specs, and nearby amenities.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("listings").document(listing_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return {"error": f"Listing with ID '{listing_id}' not found."}


def get_nearby_amenities(listing_id: str, category: str = "") -> Dict[str, Any]:
    """Find nearby amenities for a property listing such as hospitals, schools, colleges, malls, bus stops, and railway stations.

    Args:
        listing_id: Unique listing identifier (e.g. 'apt-101').
        category: Optional category filter: 'hospital', 'school', 'college', 'mall', 'bus_stop', 'railway_station'.

    Returns:
        List of nearby amenities matching the specified criteria.
    """
    details = get_listing_details(listing_id)
    if "error" in details:
        return details

    amenities = details.get("nearby_amenities", [])
    if category:
        amenities = [a for a in amenities if category.lower() in a.get("category", "").lower()]

    return {
        "listing_id": listing_id,
        "title": details.get("title"),
        "nearby_amenities": amenities,
    }


def save_favorite(user_id: str, listing_id: str) -> Dict[str, Any]:
    """Save a property listing to a user's saved favorites list in Firestore.

    Args:
        user_id: User identifier or username (e.g. 'user123', 'student').
        listing_id: Unique listing ID to save.

    Returns:
        Confirmation response object.
    """
    db = _get_firestore_client()
    fav_id = f"{user_id}_{listing_id}"
    fav_doc = {
        "favorite_id": fav_id,
        "user_id": user_id,
        "listing_id": listing_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    db.collection("favorites").document(fav_id).set(fav_doc)
    return {
        "status": "success",
        "message": f"Listing '{listing_id}' saved to favorites for user '{user_id}'.",
        "favorite": fav_doc,
    }


def update_listing_amenities(listing_id: str, amenities: List[str]) -> Dict[str, Any]:
    """Update the list of amenities for a specific property listing in Firestore.

    Args:
        listing_id: Unique listing identifier (e.g. 'apt-101').
        amenities: New complete list of amenity strings for the property.

    Returns:
        Confirmation response object with updated amenities list.
    """
    db = _get_firestore_client()
    doc_ref = db.collection("listings").document(listing_id)
    doc = doc_ref.get()
    if not doc.exists:
        return {"error": f"Listing with ID '{listing_id}' not found."}

    doc_ref.update({"amenities": amenities})
    return {
        "status": "success",
        "message": f"Amenities for listing '{listing_id}' updated successfully.",
        "listing_id": listing_id,
        "updated_amenities": amenities,
    }


def calculate_affordability(
    monthly_income: float,
    monthly_rent: float,
    monthly_debts: float = 0.0,
) -> Dict[str, Any]:
    """Calculate rental affordability based on monthly gross income, proposed rent cost, and existing monthly debt payments.

    Args:
        monthly_income: Gross monthly income in dollars.
        monthly_rent: Proposed monthly rent in dollars.
        monthly_debts: Total existing monthly debt payments in dollars (e.g. student loans, car payments).

    Returns:
        Affordability summary including rent-to-income ratio, max recommended rent, and evaluation.
    """
    if monthly_income <= 0:
        return {"error": "Monthly income must be greater than zero."}

    rent_ratio = (monthly_rent / monthly_income) * 100
    max_recommended_rent = monthly_income * 0.30
    total_debt_and_rent_ratio = ((monthly_rent + monthly_debts) / monthly_income) * 100
    is_affordable = rent_ratio <= 30.0 and total_debt_and_rent_ratio <= 43.0

    return {
        "monthly_income": monthly_income,
        "monthly_rent": monthly_rent,
        "rent_to_income_ratio_percent": round(rent_ratio, 1),
        "max_recommended_rent": round(max_recommended_rent, 2),
        "total_debt_ratio_percent": round(total_debt_and_rent_ratio, 1),
        "is_affordable": is_affordable,
        "assessment": (
            "Affordable (within recommended 30% rent limit)"
            if is_affordable
            else "Above recommended 30% rent-to-income limit"
        ),
    }


def lookup_zipcode_info(zip_code: str) -> Dict[str, Any]:
    """Fetch geographic location details (city, state, coordinates) for a US 5-digit ZIP code using Zippopotam.us API.

    Args:
        zip_code: 5-digit US postal ZIP code (e.g., '10001', '90210').

    Returns:
        Location information including city, state, state abbreviation, latitude, and longitude.
    """
    clean_zip = zip_code.strip()
    url = f"https://api.zippopotam.us/us/{clean_zip}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "UrbanNestConcierge/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
            places = data.get("places", [])
            if not places:
                return {"error": f"No location found for ZIP code {zip_code}"}
            primary_place = places[0]
            return {
                "zip_code": clean_zip,
                "city": primary_place.get("place name"),
                "state": primary_place.get("state"),
                "state_abbreviation": primary_place.get("state abbreviation"),
                "latitude": primary_place.get("latitude"),
                "longitude": primary_place.get("longitude"),
                "country": data.get("country"),
            }
    except Exception as e:
        return {"error": f"Failed to fetch location data for ZIP code '{zip_code}': {str(e)}"}


def geocode_address(address: str) -> Dict[str, Any]:
    """Convert a human-readable physical address or place name into geographic latitude and longitude coordinates using Google Geocoding API.

    Args:
        address: Full street address or place name (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        Dictionary containing name, formatted address, and location (latitude, longitude).
    """
    try:
        api_key = _get_maps_api_key()
        encoded_address = urllib.parse.quote(address)
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") != "OK" or not data.get("results"):
                return {"error": f"Could not geocode address: {data.get('status', 'No results')}"}
            result = data["results"][0]
            location = result["geometry"]["location"]
            return {
                "name": result.get("formatted_address"),
                "address": result.get("formatted_address"),
                "location": {
                    "latitude": location.get("lat"),
                    "longitude": location.get("lng"),
                },
            }
    except Exception as e:
        return {"error": f"Geocoding API error: {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> Dict[str, Any]:
    """Find nearby places (e.g. restaurants, schools, hospitals, cafes) around coordinates using Google Places API (New).

    Args:
        latitude: Center point latitude.
        longitude: Center point longitude.
        place_type: Type of place to search for (e.g., 'restaurant', 'school', 'hospital', 'cafe', 'park').
        radius_meters: Search radius distance in meters (default 1000m).

    Returns:
        List of nearby places with name, formatted address, and location coordinates.
    """
    try:
        api_key = _get_maps_api_key()
        url = "https://places.googleapis.com/v1/places:searchNearby"
        payload = json.dumps({
            "includedTypes": [place_type],
            "maxResultCount": 10,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": latitude, "longitude": longitude},
                    "radius": float(radius_meters),
                }
            },
        }).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location,places.types",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_places = data.get("places", [])
            results = []
            for p in raw_places:
                display_name = p.get("displayName", {}).get("text", "")
                loc = p.get("location", {})
                results.append({
                    "name": display_name,
                    "address": p.get("formattedAddress"),
                    "location": {
                        "latitude": loc.get("latitude"),
                        "longitude": loc.get("longitude"),
                    },
                    "types": p.get("types", []),
                })
            return {
                "search_center": {"latitude": latitude, "longitude": longitude},
                "place_type": place_type,
                "radius_meters": radius_meters,
                "places": results,
            }
    except Exception as e:
        return {"error": f"Places API (New) error: {str(e)}"}


def generate_property_image(
    prompt: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """Generate an AI rendering/visualization image for a real estate property, interior room design, or architectural concept using gemini-3.1-flash-lite-image in the global region. Saves the image as an ADK session artifact and uploads it to public Cloud Storage.

    Args:
        prompt: Description of the property image, room interior, or architecture concept to render (e.g. 'Modern studio living room with natural light and wood accents').
        tool_context: Injected ADK ToolContext for saving session artifacts.

    Returns:
        Dictionary containing image status, prompt, filename, and public Cloud Storage URL.
    """
    try:
        genai_client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT_ID, location="global")
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=f"Real estate architecture and interior design rendering of: {prompt}",
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.parts:
            for part in response.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or mime_type
                    break
                elif hasattr(part, "as_image") and callable(part.as_image):
                    img = part.as_image()
                    if img:
                        import io
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG")
                        image_bytes = buf.getvalue()
                        mime_type = "image/jpeg"
                        break

        if not image_bytes:
            return {"error": "No image data was generated by the model."}

        filename = f"property_rendering_{uuid.uuid4().hex[:8]}.jpg"

        # 1. Save artifact with ToolContext (ADK Web / Playground Artifacts panel)
        if tool_context:
            artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
            tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes to public Cloud Storage bucket
        object_key = f"generated_images/{filename}"
        storage_client = storage.Client(project=FIRESTORE_PROJECT_ID)
        bucket = storage_client.bucket(ASSETS_BUCKET_NAME)
        blob = bucket.blob(object_key)
        blob.upload_from_string(image_bytes, content_type=mime_type)
        public_url = f"https://storage.googleapis.com/{ASSETS_BUCKET_NAME}/{object_key}"

        return {
            "status": "success",
            "prompt": prompt,
            "filename": filename,
            "public_url": public_url,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload image: {str(e)}"}


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: After each turn, send the session to Memory Bank for fact extraction."""
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        logger.warning(f"Could not save memory bank session: {e}")
    return None


def memory_bank_service_builder():
    """Builds VertexAiMemoryBankService for deployed Agent Runtime app."""
    resource_name = _get_agent_engine_resource_name()
    engine_id = resource_name.split("/")[-1] if resource_name else "2094303569099358208"
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT_ID,
        location="us-east1",
        agent_engine_id=engine_id,
    )


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are UrbanNest Concierge, an AI real estate assistant. "
        "You help users search for apartments, explore nearby amenities (hospitals, schools, colleges, malls, bus stops, railway stations), "
        "geocode addresses into coordinates, search Google Places (New) for nearby places, calculate financial affordability, "
        "lookup US ZIP code location details, view detailed property specs, update listing details, save their favorite listings to Firestore, "
        "generate property architectural & interior renderings using gemini-3.1-flash-lite-image, "
        "and safely execute Python code in an Agent Engine sandbox. "
        "You use Vertex AI Memory Bank to remember user preferences across sessions, paying special attention to "
        "remembering each user's budget limits (e.g. maximum monthly rent) and hospital proximity preferences (e.g. maximum distance to a hospital)."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
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
    name="urbannest_concierge",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=_create_code_executor(),
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
    tools=[
        PreloadMemoryTool(),
        search_listings,
        get_listing_details,
        get_nearby_amenities,
        save_favorite,
        update_listing_amenities,
        calculate_affordability,
        lookup_zipcode_info,
        geocode_address,
        find_nearby_places,
        generate_property_image,
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)

