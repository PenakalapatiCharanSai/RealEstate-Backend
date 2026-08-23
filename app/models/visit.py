from datetime import datetime, timezone
from bson import ObjectId
from app.models.constants import VISIT_STATUSES, DEFAULT_VISIT_STATUS

class VisitModel:
    """
    Visit Document Model Schema & Utility

    Schema:
    {
      "_id": ObjectId,
      "customer_id": ObjectId,
      "property_id": ObjectId,
      "agent_id": ObjectId,
      "visit_date": str,
      "visit_time": str,
      "message": str,
      "status": str ("requested" | "confirmed" | "rescheduled" | "completed" | "cancelled"),
      "created_at": datetime
    }
    """

    @staticmethod
    def create_document(
        customer_id,
        property_id,
        agent_id=None,
        visit_date="",
        visit_time="",
        message="",
        status=DEFAULT_VISIT_STATUS
    ):
        if status not in VISIT_STATUSES:
            raise ValueError(f"Invalid visit status '{status}'. Allowed: {VISIT_STATUSES}")

        parsed_customer_id = ObjectId(customer_id) if isinstance(customer_id, str) and ObjectId.is_valid(customer_id) else customer_id
        parsed_property_id = ObjectId(property_id) if isinstance(property_id, str) and ObjectId.is_valid(property_id) else property_id
        parsed_agent_id = ObjectId(agent_id) if isinstance(agent_id, str) and ObjectId.is_valid(agent_id) else agent_id

        return {
            "customer_id": parsed_customer_id,
            "property_id": parsed_property_id,
            "agent_id": parsed_agent_id,
            "visit_date": str(visit_date).strip(),
            "visit_time": str(visit_time).strip(),
            "message": str(message).strip(),
            "status": status,
            "created_at": datetime.now(timezone.utc),
        }
