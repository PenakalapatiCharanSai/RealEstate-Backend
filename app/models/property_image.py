from datetime import datetime, timezone
from bson import ObjectId

class PropertyImageModel:
    """
    Property Image Document Schema helper for MongoDB property_images collection.
    Fields:
      - _id: ObjectId
      - property_id: ObjectId
      - url: str
      - public_id: str
      - caption: str
      - is_primary: bool
      - created_at: datetime
    """

    @staticmethod
    def create_document(property_id, url, public_id="", caption="", is_primary=False):
        now = datetime.now(timezone.utc)
        return {
            "property_id": ObjectId(property_id) if isinstance(property_id, str) else property_id,
            "url": str(url).strip(),
            "public_id": str(public_id).strip(),
            "caption": str(caption).strip(),
            "is_primary": bool(is_primary),
            "created_at": now,
        }

    @staticmethod
    def format_image(doc):
        if not doc:
            return None
        return {
            "id": str(doc.get("_id", "")),
            "property_id": str(doc.get("property_id", "")),
            "url": doc.get("url", ""),
            "public_id": doc.get("public_id", ""),
            "caption": doc.get("caption", ""),
            "is_primary": doc.get("is_primary", False),
            "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at"),
        }
