from datetime import datetime, timezone
from bson import ObjectId

def create_notification(db, user_id, type_str, title, message, related_id=None):
    """
    Helper function to insert an in-app notification document into MongoDB.
    
    Fields:
      - _id: ObjectId
      - user_id: ObjectId
      - type: str (new_enquiry | visit_request | visit_confirmation | property_approval | property_rejection | property_status_change)
      - title: str
      - message: str
      - read: bool (default: False)
      - related_id: ObjectId | None
      - created_at: ISODate
    """
    if db is None or not user_id:
        return None

    try:
        user_obj_id = ObjectId(user_id) if isinstance(user_id, str) and ObjectId.is_valid(user_id) else user_id
        if not isinstance(user_obj_id, ObjectId):
            return None

        related_obj_id = None
        if related_id:
            related_obj_id = ObjectId(related_id) if isinstance(related_id, str) and ObjectId.is_valid(related_id) else related_id

        doc = {
            "user_id": user_obj_id,
            "type": str(type_str).strip(),
            "title": str(title).strip(),
            "message": str(message).strip(),
            "read": False,
            "related_id": related_obj_id,
            "created_at": datetime.now(timezone.utc)
        }

        result = db.notifications.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None
