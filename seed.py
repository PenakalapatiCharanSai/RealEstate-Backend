import sys
from app.utils.db import get_db, create_db_indexes
from app.models.category import CategoryModel

DEFAULT_CATEGORIES = [
    {"name": "Apartment", "description": "Residential apartments and luxury flats"},
    {"name": "Villa", "description": "Independent luxury villas and bungalows"},
    {"name": "Commercial", "description": "Office spaces, shops, and commercial buildings"},
    {"name": "House", "description": "Single-family homes and townhouses"},
    {"name": "Land", "description": "Residential and commercial land plots"},
]

def seed_database():
    """
    Seed initial MongoDB database structure, indexes, and default categories.
    Does NOT create fake production user accounts.
    """
    print("Connecting to MongoDB...")
    db = get_db()
    if db is None:
        print("Error: Could not establish MongoDB connection.")
        sys.exit(1)

    print("Configuring collection indexes...")
    index_success = create_db_indexes(db)
    if index_success:
        print("[OK] All collection indexes created/verified successfully.")

    print("\nSeeding default property categories...")
    categories_col = db.categories
    created_count = 0

    for cat in DEFAULT_CATEGORIES:
        existing = categories_col.find_one({"name": cat["name"]})
        if not existing:
            doc = CategoryModel.create_document(name=cat["name"], description=cat["description"])
            categories_col.insert_one(doc)
            print(f"  + Added category: '{cat['name']}'")
            created_count += 1
        else:
            print(f"  - Category already exists: '{cat['name']}'")

    print(f"\nSeeding complete. {created_count} new category documents created.")
    print("Database structure is ready for future modules.")

if __name__ == "__main__":
    seed_database()
