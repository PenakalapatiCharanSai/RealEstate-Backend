from datetime import datetime, timezone
from bson import ObjectId
from app.models.constants import (
    USER_ROLES, DEFAULT_USER_ROLE,
    USER_STATUSES, DEFAULT_USER_STATUS
)

class UserModel:
    """
    User Document Model Schema & Utility

    Schema:
    {
      "_id": ObjectId,
      "name": str,
      "email": str,
      "password": str,
      "phone": str,
      "role": str ("admin" | "agent" | "owner" | "customer"),
      "status": str ("active" | "inactive" | "pending_verification" | "pending_approval"),
      "email_verified": bool,
      "is_verified": bool,
      "otp_hash": str | None,
      "otp_expires_at": datetime | None,
      "otp_attempts": int,
      "last_otp_sent_at": datetime | None,
      "created_at": datetime
    }
    """

    @staticmethod
    def create_document(
        name,
        email,
        password,
        phone="",
        role=DEFAULT_USER_ROLE,
        status=DEFAULT_USER_STATUS,
        email_verified=False,
        is_verified=False,
        otp_hash=None,
        otp_expires_at=None,
        otp_attempts=0,
        last_otp_sent_at=None
    ):
        if role not in USER_ROLES:
            raise ValueError(f"Invalid role '{role}'. Allowed roles: {USER_ROLES}")

        if status not in USER_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Allowed statuses: {USER_STATUSES}")

        # Sync is_verified and email_verified
        verified = bool(email_verified or is_verified)

        return {
            "name": str(name).strip(),
            "email": str(email).strip().lower(),
            "password": str(password),
            "phone": str(phone).strip(),
            "role": role,
            "status": status,
            "email_verified": verified,
            "is_verified": verified,
            "otp_hash": otp_hash,
            "otp_expires_at": otp_expires_at,
            "otp_attempts": int(otp_attempts),
            "last_otp_sent_at": last_otp_sent_at,
            "created_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def format_user(user_doc):
        """Format MongoDB user document for JSON responses (excluding password & security hashes)."""
        if not user_doc:
            return None
        is_verified = bool(user_doc.get("email_verified", user_doc.get("is_verified", False)))
        return {
            "id": str(user_doc["_id"]),
            "name": user_doc.get("name"),
            "email": user_doc.get("email"),
            "phone": user_doc.get("phone", ""),
            "role": user_doc.get("role", DEFAULT_USER_ROLE),
            "status": user_doc.get("status", DEFAULT_USER_STATUS),
            "email_verified": is_verified,
            "is_verified": is_verified,
            "created_at": user_doc.get("created_at").isoformat() if isinstance(user_doc.get("created_at"), datetime) else user_doc.get("created_at"),
        }
