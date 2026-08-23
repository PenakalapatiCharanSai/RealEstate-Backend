from datetime import datetime, timezone
from bson import ObjectId
from app.models.constants import (
    TRANSACTION_TYPES, DEFAULT_TRANSACTION_TYPE,
    PROPERTY_STATUSES, DEFAULT_PROPERTY_STATUS,
    APPROVAL_STATUSES, DEFAULT_APPROVAL_STATUS,
    PROPERTY_TYPES, DEFAULT_PROPERTY_TYPE,
    FURNISHING_TYPES, DEFAULT_FURNISHING
)

class PropertyModel:
    """
    Property Document Model Schema & Utility

    Schema:
    {
      "_id": ObjectId,
      "title": str,
      "type": str,
      "description": str,
      "transaction_type": str ("Sale" | "Rent"),
      "price": float,
      "location": str,
      "address": str,
      "area": float,
      "bedrooms": int,
      "bathrooms": int,
      "parking": bool,
      "furnishing": str,
      "images": list[str],
      "agent_id": ObjectId,
      "status": str ("Available" | "Sold" | "Rented" | "Unavailable"),
      "approval_status": str ("Pending" | "Approved" | "Rejected"),
      "rejection_reason": str,
      "created_at": datetime,
      "updated_at": datetime
    }
    """

    @staticmethod
    def create_document(
        title,
        type_=DEFAULT_PROPERTY_TYPE,
        description="",
        transaction_type=DEFAULT_TRANSACTION_TYPE,
        price=0.0,
        location="",
        address="",
        area=0.0,
        bedrooms=0,
        bathrooms=0,
        parking=False,
        furnishing=DEFAULT_FURNISHING,
        images=None,
        agent_id=None,
        status=DEFAULT_PROPERTY_STATUS,
        approval_status=DEFAULT_APPROVAL_STATUS,
        rejection_reason="",
        latitude=None,
        longitude=None
    ):
        if images is None:
            images = []

        now = datetime.now(timezone.utc)

        parsed_agent_id = None
        if agent_id:
            parsed_agent_id = ObjectId(agent_id) if isinstance(agent_id, str) and ObjectId.is_valid(agent_id) else agent_id

        lat_val = None
        if latitude is not None and latitude != "":
            try:
                lat_val = float(latitude)
            except (ValueError, TypeError):
                lat_val = None

        lng_val = None
        if longitude is not None and longitude != "":
            try:
                lng_val = float(longitude)
            except (ValueError, TypeError):
                lng_val = None

        return {
            "title": str(title).strip(),
            "type": str(type_).strip(),
            "description": str(description).strip(),
            "transaction_type": str(transaction_type).strip(),
            "price": float(price),
            "location": str(location).strip(),
            "address": str(address).strip(),
            "area": float(area),
            "bedrooms": int(bedrooms),
            "bathrooms": int(bathrooms),
            "parking": bool(parking),
            "furnishing": str(furnishing).strip(),
            "images": [str(img).strip() for img in images if img],
            "agent_id": parsed_agent_id,
            "status": str(status).strip(),
            "approval_status": str(approval_status).strip(),
            "rejection_reason": str(rejection_reason).strip(),
            "latitude": lat_val,
            "longitude": lng_val,
            "views_count": 0,
            "favorites_count": 0,
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def format_property(doc):
        """
        Format a MongoDB property document for API response (converts ObjectIds & Datetimes).
        """
        if not doc:
            return None

        lat_val = None
        if doc.get("latitude") is not None and doc.get("latitude") != "":
            try:
                lat_val = float(doc.get("latitude"))
            except (ValueError, TypeError):
                lat_val = None

        lng_val = None
        if doc.get("longitude") is not None and doc.get("longitude") != "":
            try:
                lng_val = float(doc.get("longitude"))
            except (ValueError, TypeError):
                lng_val = None

        formatted = {
            "id": str(doc.get("_id")),
            "title": doc.get("title", ""),
            "type": doc.get("type", DEFAULT_PROPERTY_TYPE),
            "description": doc.get("description", ""),
            "transaction_type": doc.get("transaction_type", DEFAULT_TRANSACTION_TYPE),
            "price": float(doc.get("price", 0)),
            "location": doc.get("location", ""),
            "address": doc.get("address", ""),
            "area": float(doc.get("area", 0)),
            "bedrooms": int(doc.get("bedrooms", 0)),
            "bathrooms": int(doc.get("bathrooms", 0)),
            "parking": bool(doc.get("parking", False)),
            "furnishing": doc.get("furnishing", DEFAULT_FURNISHING),
            "images": doc.get("images", []),
            "agent_id": str(doc.get("agent_id")) if doc.get("agent_id") else None,
            "status": doc.get("status", DEFAULT_PROPERTY_STATUS),
            "approval_status": doc.get("approval_status", DEFAULT_APPROVAL_STATUS),
            "rejection_reason": doc.get("rejection_reason", ""),
            "latitude": lat_val,
            "longitude": lng_val,
            "views_count": int(doc.get("views_count", 0)),
            "favorites_count": int(doc.get("favorites_count", 0)),
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
