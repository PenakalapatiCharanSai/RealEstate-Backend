from datetime import datetime, timezone
from bson import ObjectId
from app.models.constants import ENQUIRY_STATUSES, DEFAULT_ENQUIRY_STATUS

class EnquiryModel:
    """
    Enquiry Document Model Schema & Utility

    Schema:
    {
      "_id": ObjectId,
      "customer_id": ObjectId,
      "property_id": ObjectId,
      "agent_id": ObjectId,
      "message": str,
      "status": str ("new" | "contacted" | "in_progress" | "resolved" | "closed"),
      "created_at": datetime
    }
    """

    @staticmethod
    def create_document(customer_id, property_id, agent_id=None, message="", status=DEFAULT_ENQUIRY_STATUS):
        if status not in ENQUIRY_STATUSES:
            raise ValueError(f"Invalid enquiry status '{status}'. Allowed: {ENQUIRY_STATUSES}")

        parsed_customer_id = ObjectId(customer_id) if isinstance(customer_id, str) and ObjectId.is_valid(customer_id) else customer_id
        parsed_property_id = ObjectId(property_id) if isinstance(property_id, str) and ObjectId.is_valid(property_id) else property_id
        parsed_agent_id = ObjectId(agent_id) if isinstance(agent_id, str) and ObjectId.is_valid(agent_id) else agent_id

        return {
            "customer_id": parsed_customer_id,
            "property_id": parsed_property_id,
            "agent_id": parsed_agent_id,
            "message": str(message).strip(),
            "status": status,
            "created_at": datetime.now(timezone.utc),
        }
