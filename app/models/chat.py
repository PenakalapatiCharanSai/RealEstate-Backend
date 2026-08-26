import uuid
from datetime import datetime, timezone
from bson import ObjectId

class ChatConversationModel:
    """
    MongoDB Chat Conversation Model Schema & Formatter for `chat_conversations` collection.
    
    Schema:
    {
      "_id": ObjectId,
      "user_id": ObjectId or None,
      "conversation_id": str (UUID),
      "title": str,
      "messages": [
         {
           "role": "user" | "assistant",
           "content": str,
           "properties": list[dict],
           "action": dict or None,
           "timestamp": str (ISO datetime)
         }
      ],
      "created_at": datetime,
      "updated_at": datetime
    }
    """

    @staticmethod
    def create_document(user_id=None, conversation_id=None, title="New Conversation", initial_message=None):
        now = datetime.now(timezone.utc)
        parsed_user_id = None
        if user_id:
            parsed_user_id = ObjectId(user_id) if isinstance(user_id, str) and ObjectId.is_valid(user_id) else user_id

        messages = []
        if initial_message:
            messages.append(initial_message)

        return {
            "user_id": parsed_user_id,
            "conversation_id": str(conversation_id) if conversation_id else str(uuid.uuid4()),
            "title": str(title).strip() or "New Property Inquiry",
            "messages": messages,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def format_conversation(doc, include_messages=True):
        if not doc:
            return None

        user_id_str = str(doc.get("user_id")) if doc.get("user_id") else None

        created_at = doc.get("created_at")
        created_iso = created_at.isoformat() if isinstance(created_at, datetime) else str(created_at or "")

        updated_at = doc.get("updated_at")
        updated_iso = updated_at.isoformat() if isinstance(updated_at, datetime) else str(updated_at or "")

        formatted = {
            "id": str(doc.get("_id")),
            "user_id": user_id_str,
            "conversation_id": doc.get("conversation_id", ""),
            "title": doc.get("title", "Property Conversation"),
            "created_at": created_iso,
            "updated_at": updated_iso
        }

        if include_messages:
            raw_messages = doc.get("messages", [])
            formatted_messages = []
            for m in raw_messages:
                formatted_messages.append({
                    "role": m.get("role", "assistant"),
                    "content": m.get("content", ""),
                    "properties": m.get("properties", []),
                    "action": m.get("action"),
                    "timestamp": m.get("timestamp", "")
                })
            formatted["messages"] = formatted_messages
            formatted["message_count"] = len(formatted_messages)

        return formatted
