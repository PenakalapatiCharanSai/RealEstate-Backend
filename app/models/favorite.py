from datetime import datetime, timezone
from bson import ObjectId

class FavoriteModel:
    """
    Favorite Document Model Schema & Utility

    Schema:
    {
      "_id": ObjectId,
      "customer_id": ObjectId,
      "property_id": ObjectId,
      "created_at": datetime
    }
    """

    @staticmethod
    def create_document(customer_id, property_id):
        parsed_customer_id = ObjectId(customer_id) if isinstance(customer_id, str) and ObjectId.is_valid(customer_id) else customer_id
        parsed_property_id = ObjectId(property_id) if isinstance(property_id, str) and ObjectId.is_valid(property_id) else property_id

        return {
            "customer_id": parsed_customer_id,
            "property_id": parsed_property_id,
            "created_at": datetime.now(timezone.utc),
        }
