from datetime import datetime, timezone
from bson import ObjectId
from app.models.constants import CATEGORY_STATUSES, DEFAULT_CATEGORY_STATUS

DEFAULT_CATEGORIES = [
    {"name": "Apartment", "description": "Multi-family residential units within a shared building complex."},
    {"name": "Villa", "description": "Standalone luxury residential estates with private grounds and amenities."},
    {"name": "Independent House", "description": "Single-family detached houses with private plot ownership."},
    {"name": "Commercial Property", "description": "Real estate spaces intended for retail, business, or investment operations."},
    {"name": "Plot", "description": "Vacant land parcels designated for residential or commercial development."},
    {"name": "Office", "description": "Dedicated corporate office suites, co-working spaces, and commercial floors."}
]

class CategoryModel:
    """
    Category Document Model Schema & Utility

    Schema:
    {
      "_id": ObjectId,
      "name": str,
      "description": str,
      "status": str ("active" | "inactive"),
      "created_at": datetime,
      "updated_at": datetime
    }
    """

    @staticmethod
    def create_document(name, description="", status=DEFAULT_CATEGORY_STATUS):
        if status not in CATEGORY_STATUSES:
            raise ValueError(f"Invalid category status '{status}'. Allowed: {CATEGORY_STATUSES}")

        now = datetime.now(timezone.utc)
        return {
            "name": str(name).strip(),
            "description": str(description).strip(),
            "status": status,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def format_category(doc):
        if not doc:
            return None

        formatted = {
            "id": str(doc.get("_id")),
            "name": doc.get("name", ""),
            "description": doc.get("description", ""),
            "status": doc.get("status", DEFAULT_CATEGORY_STATUS),
        }

        created_at = doc.get("created_at")
        if isinstance(created_at, datetime):
            formatted["created_at"] = created_at.isoformat()
        else:
            formatted["created_at"] = str(created_at) if created_at else None

        updated_at = doc.get("updated_at")
        if isinstance(updated_at, datetime):
            formatted["updated_at"] = updated_at.isoformat()
        else:
            formatted["updated_at"] = str(updated_at) if updated_at else None

        return formatted
