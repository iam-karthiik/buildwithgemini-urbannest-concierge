import os
import subprocess
import google.auth
from google.oauth2 import credentials
from google.cloud import firestore

# HARDCODED PROJECT ID - DO NOT CHANGE TO ENV VAR OR GOOGLE.AUTH.DEFAULT PROJECT
FIRESTORE_PROJECT = "qwiklabs-gcp-03-d5a4eae88bb3"


def get_firestore_client():
    # Get active access token from gcloud
    try:
        token = (
            subprocess.check_output(
                ["gcloud", "auth", "print-access-token"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
        if token:
            creds = credentials.Credentials(token)
            return firestore.Client(project=FIRESTORE_PROJECT, credentials=creds)
    except Exception as e:
        print(f"gcloud token fallback notice: {e}")

    return firestore.Client(project=FIRESTORE_PROJECT)


def seed_database():
    print(f"Connecting to Firestore with project_id='{FIRESTORE_PROJECT}'...")
    db = get_firestore_client()

    listings_ref = db.collection("listings")

    sample_listings = [
        {
            "listing_id": "apt-101",
            "title": "Modern Loft in Downtown",
            "address": "123 Market St, Suite 404",
            "neighborhood": "Downtown",
            "price": 2800,
            "bedrooms": 1,
            "bathrooms": 1.5,
            "amenities": [
                "in-unit laundry",
                "pet-friendly",
                "balcony",
                "fitness center",
            ],
            "description": "Sleek open-concept loft with floor-to-ceiling windows and city skyline views.",
            "image_url": "https://storage.googleapis.com/static-assets/modern_loft.jpg",
            "nearby_amenities": [
                {
                    "category": "hospital",
                    "name": "City General Hospital",
                    "distance_miles": 0.8,
                },
                {
                    "category": "school",
                    "name": "Downtown Elementary School",
                    "distance_miles": 0.4,
                },
                {
                    "category": "college",
                    "name": "State University Downtown Campus",
                    "distance_miles": 1.2,
                },
                {
                    "category": "mall",
                    "name": "Metropolitan Shopping Galleria",
                    "distance_miles": 0.3,
                },
                {
                    "category": "bus_stop",
                    "name": "Market & 4th St Bus Stop",
                    "distance_miles": 0.1,
                },
                {
                    "category": "railway_station",
                    "name": "Central Metro Station",
                    "distance_miles": 0.5,
                },
            ],
        },
        {
            "listing_id": "apt-102",
            "title": "Spacious 2BR Luxury Apartment",
            "address": "456 Oak Avenue",
            "neighborhood": "Westside",
            "price": 3500,
            "bedrooms": 2,
            "bathrooms": 2.0,
            "amenities": [
                "in-unit laundry",
                "parking",
                "swimming pool",
                "rooftop deck",
            ],
            "description": "Generous 2BR unit featuring chef's kitchen, quartz countertops, and underground parking.",
            "image_url": "https://storage.googleapis.com/static-assets/luxury_2br.jpg",
            "nearby_amenities": [
                {
                    "category": "hospital",
                    "name": "Westside Health Center",
                    "distance_miles": 1.1,
                },
                {
                    "category": "school",
                    "name": "Oakridge High School",
                    "distance_miles": 0.6,
                },
                {
                    "category": "college",
                    "name": "Westside Tech Institute",
                    "distance_miles": 2.0,
                },
                {
                    "category": "mall",
                    "name": "Westside Plaza",
                    "distance_miles": 0.9,
                },
                {
                    "category": "bus_stop",
                    "name": "Oak & 5th Ave Bus Stop",
                    "distance_miles": 0.2,
                },
                {
                    "category": "railway_station",
                    "name": "Westside Suburban Rail Station",
                    "distance_miles": 1.0,
                },
            ],
        },
        {
            "listing_id": "apt-103",
            "title": "Cozy Studio near University",
            "address": "789 College Blvd",
            "neighborhood": "University District",
            "price": 1900,
            "bedrooms": 0,
            "bathrooms": 1.0,
            "amenities": ["high-speed internet", "bike storage", "pet-friendly"],
            "description": "Charming garden studio perfect for students or young professionals. Steps away from campus.",
            "image_url": "https://storage.googleapis.com/static-assets/cozy_studio.jpg",
            "nearby_amenities": [
                {
                    "category": "hospital",
                    "name": "University Student Health Hospital",
                    "distance_miles": 0.3,
                },
                {
                    "category": "school",
                    "name": "University Preparatory Academy",
                    "distance_miles": 0.5,
                },
                {
                    "category": "college",
                    "name": "Metropolitan University Main Campus",
                    "distance_miles": 0.2,
                },
                {
                    "category": "mall",
                    "name": "Campus Town Square Malls",
                    "distance_miles": 0.4,
                },
                {
                    "category": "bus_stop",
                    "name": "University Main Gate Bus Stop",
                    "distance_miles": 0.05,
                },
                {
                    "category": "railway_station",
                    "name": "University Park Station",
                    "distance_miles": 0.7,
                },
            ],
        },
    ]

    for item in sample_listings:
        doc_ref = listings_ref.document(item["listing_id"])
        doc_ref.set(item)
        print(f"✓ Seeded listing: {item['listing_id']} - {item['title']}")

    print("✅ Firestore database seeding complete!")


if __name__ == "__main__":
    seed_database()
