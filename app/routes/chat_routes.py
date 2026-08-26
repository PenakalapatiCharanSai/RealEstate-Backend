import logging
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db
from app.middleware.auth_middleware import authenticate_user
from app.utils.jwt_utils import decode_token
from app.models.chat import ChatConversationModel
from app.services.chatbot_service import process_chat_message

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__, url_prefix="/api/chat")


def extract_user_from_request():
    """
    Optional helper to extract user object from request headers if token is present.
    Returns user dict or None.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id or not ObjectId.is_valid(user_id):
            return None

        db = get_db()
        if db is None:
            return None

        user = db.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("status") == "active":
            return user
    except Exception as e:
        logger.debug(f"Optional token extraction error: {e}")

    return None


@chat_bp.route("", methods=["POST"])
def post_chat_message():
    """
    POST /api/chat
    Primary chatbot messaging endpoint.
    Accepts: { "message": "...", "conversation_id": "...", "current_property_id": "..." }
    Supports both authenticated users (with persistent DB history) and temporary guest sessions.
    """
    data = request.get_json() or {}
    message = str(data.get("message", "")).strip()
    conversation_id = data.get("conversation_id") or data.get("conversationId")
    current_property_id = data.get("current_property_id") or data.get("currentPropertyId") or data.get("property_id")

    if not message:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": "Message parameter is required."
        }), 400

    user = extract_user_from_request()

    res = process_chat_message(
        user=user,
        user_message=message,
        conversation_id=conversation_id,
        current_property_id=current_property_id
    )

    if not res.get("success"):
        status_code = 400
        if res.get("error") == "FORBIDDEN":
            status_code = 403
        elif res.get("error") == "DATABASE_ERROR":
            status_code = 500
        return jsonify(res), status_code

    return jsonify(res), 200


@chat_bp.route("/conversations", methods=["GET"])
@authenticate_user
def get_conversations():
    """
    GET /api/chat/conversations
    Lists authenticated user's saved chatbot conversations.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_id = ObjectId(g.user_id)
    cursor = db.chat_conversations.find({"user_id": user_id}).sort("updated_at", -1).limit(50)
    raw_docs = list(cursor)

    formatted_list = [ChatConversationModel.format_conversation(doc, include_messages=False) for doc in raw_docs]

    return jsonify({
        "success": True,
        "conversations": formatted_list,
        "total": len(formatted_list)
    }), 200


@chat_bp.route("/conversations/<conversation_id>", methods=["GET"])
@authenticate_user
def get_conversation_by_id(conversation_id):
    """
    GET /api/chat/conversations/<conversation_id>
    Retrieves full message history of a specific conversation.
    Enforces strict authorization user isolation.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    conv_doc = db.chat_conversations.find_one({"conversation_id": conversation_id})
    if not conv_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Conversation not found."}), 404

    # User isolation check
    if conv_doc.get("user_id") and str(conv_doc.get("user_id")) != g.user_id:
        return jsonify({"success": False, "error": "Forbidden", "message": "You are not authorized to view this conversation."}), 403

    formatted = ChatConversationModel.format_conversation(conv_doc, include_messages=True)

    return jsonify({
        "success": True,
        "conversation": formatted
    }), 200


@chat_bp.route("/conversations/<conversation_id>", methods=["DELETE"])
@authenticate_user
def delete_conversation(conversation_id):
    """
    DELETE /api/chat/conversations/<conversation_id>
    Deletes a specific conversation history session.
    Enforces user isolation.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_id = ObjectId(g.user_id)
    result = db.chat_conversations.delete_one({"conversation_id": conversation_id, "user_id": user_id})

    if result.deleted_count == 0:
        return jsonify({"success": False, "error": "Not Found", "message": "Conversation not found or unauthorized."}), 404

    return jsonify({
        "success": True,
        "message": "Conversation deleted successfully."
    }), 200
