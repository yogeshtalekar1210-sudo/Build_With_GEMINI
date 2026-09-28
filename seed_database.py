"""Seed script for travel-concierge-agent Firestore database.

Populates the 'destinations' collection with initial travel destinations.
Hardcodes the project ID to avoid Agent Platform runtime resolution issues.
"""

from google.cloud import firestore

# Hardcode the GCP Project ID as requested to prevent Agent Platform issues
FIRESTORE_PROJECT_ID = "qwiklabs-gcp-03-11269a8adae1"

INITIAL_DESTINATIONS = [
    {
        "id": "kyoto-japan",
        "name": "Kyoto, Japan",
        "country": "Japan",
        "description": "Historic city famous for classical Buddhist temples, gardens, imperial palaces, and traditional wooden houses.",
        "best_season": "Spring (Cherry Blossoms) & Autumn (Foliage)",
        "estimated_cost_per_day_usd": 180,
        "tags": ["culture", "history", "food", "temples", "scenic"],
        "highlights": ["Fushimi Inari Shrine", "Arashiyama Bamboo Grove", "Kinkaku-ji Temple"],
    },
    {
        "id": "santorini-greece",
        "name": "Santorini, Greece",
        "country": "Greece",
        "description": "Stunning Cycladic island known for whitewashed cliffside villages, dramatic caldera views, and romantic sunsets.",
        "best_season": "Late Spring to Early Autumn (May - October)",
        "estimated_cost_per_day_usd": 250,
        "tags": ["beaches", "romance", "scenic", "island", "sunset"],
        "highlights": ["Oia Sunset Viewpoint", "Red Beach", "Akrotiri Archaeological Site"],
    },
    {
        "id": "banff-canada",
        "name": "Banff National Park, Canada",
        "country": "Canada",
        "description": "Breathtaking national park in the Canadian Rockies with turquoise glacial lakes, majestic peaks, and abundant wildlife.",
        "best_season": "Summer (Hiking) & Winter (Skiing)",
        "estimated_cost_per_day_usd": 210,
        "tags": ["nature", "hiking", "mountains", "wildlife", "adventure"],
        "highlights": ["Lake Louise", "Moraine Lake", "Icefields Parkway"],
    },
    {
        "id": "marrakech-morocco",
        "name": "Marrakech, Morocco",
        "country": "Morocco",
        "description": "Vibrant imperial city filled with bustling medina souks, ornate palaces, aromatic spice markets, and historic riads.",
        "best_season": "Spring (March - May) & Autumn (September - November)",
        "estimated_cost_per_day_usd": 120,
        "tags": ["culture", "shopping", "food", "history", "architecture"],
        "highlights": ["Jemaa el-Fnaa Square", "Jardin Majorelle", "Bahia Palace"],
    },
]


def seed_destinations():
    db = firestore.Client(project=FIRESTORE_PROJECT_ID)
    collection_ref = db.collection("destinations")

    print(f"Seeding Firestore collection 'destinations' in project '{FIRESTORE_PROJECT_ID}'...")
    for item in INITIAL_DESTINATIONS:
        doc_id = item["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(item)
        print(f"  ✓ Seeded destination: {item['name']} (ID: {doc_id})")

    print("Seeding complete! Successfully added destinations.")


if __name__ == "__main__":
    seed_destinations()
