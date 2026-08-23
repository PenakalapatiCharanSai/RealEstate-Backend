from datetime import datetime, timezone
from bson import ObjectId

class ReviewModel:
    """
    Review Document Model Schema & Utility

    Schema:
    {
      "_id": ObjectId,
      "customer_id": ObjectId,
      "agent_id": ObjectId,
      "property_id": ObjectId (optional),
      "rating": int (1-5),
      "review": str,
      "created_at": datetime,
      "updated_at": datetime
    }
    """

    @staticmethod
    def create_document(
        customer_id,
        agent_id,
        rating,
        review,
        property_id=None
    ):
        now = datetime.now(timezone.utc)

        parsed_cust_id = ObjectId(customer_id) if isinstance(customer_id, str) and ObjectId.is_valid(customer_id) else customer_id
        parsed_agent_id = ObjectId(agent_id) if isinstance(agent_id, str) and ObjectId.is_valid(agent_id) else agent_id

        parsed_prop_id = None
        if property_id:
            parsed_prop_id = ObjectId(property_id) if isinstance(property_id, str) and ObjectId.is_valid(property_id) else property_id

        try:
            rating_val = int(rating)
        except (ValueError, TypeError):
            rating_val = 5

        if rating_val < 1:
            rating_val = 1
        elif rating_val > 5:
            rating_val = 5

        return {
            "customer_id": parsed_cust_id,
            "agent_id": parsed_agent_id,
            "property_id": parsed_prop_id,
            "rating": rating_val,
            "review": str(review).strip(),
            "created_at": now,
            "updated_at": now,
        }

    @staticmethod
    def format_review(doc, customer_map=None, agent_map=None, prop_map=None):
        if not doc:
            return None

        cust_id_str = str(doc.get("customer_id")) if doc.get("customer_id") else None
        agent_id_str = str(doc.get("agent_id")) if doc.get("agent_id") else None
        prop_id_str = str(doc.get("property_id")) if doc.get("property_id") else None

        cust_info = customer_map.get(cust_id_str, {}) if customer_map else {}
        agent_info = agent_map.get(agent_id_str, {}) if agent_map else {}
        prop_info = prop_map.get(prop_id_str, {}) if prop_map else {}

        created_at = doc.get("created_at")
        if isinstance(created_at, datetime):
            created_at_str = created_at.isoformat()
        else:
            created_at_str = str(created_at) if created_at else None

        return {
            "id": str(doc.get("_id")),
            "customer_id": cust_id_str,
            "agent_id": agent_id_str,
            "property_id": prop_id_str,
            "rating": int(doc.get("rating", 5)),
            "review": doc.get("review", ""),
            "created_at": created_at_str,
            "customer": {
                "name": cust_info.get("name", "Customer"),
                "email": cust_info.get("email", ""),
            },
            "agent": {
                "name": agent_info.get("name", "Agent"),
                "email": agent_info.get("email", ""),
            },
            "property": {
                "title": prop_info.get("title", ""),
                "location": prop_info.get("location", ""),
            } if prop_id_str else None
        }
