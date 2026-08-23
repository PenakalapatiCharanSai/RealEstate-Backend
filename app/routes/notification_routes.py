from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db
from app.middleware.auth_middleware import authenticate_user

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

def format_notification(doc):
    if not doc:
        return None
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc.get("user_id")) if doc.get("user_id") else None,
        "type": doc.get("type", ""),
        "title": doc.get("title", ""),
        "message": doc.get("message", ""),
        "read": bool(doc.get("read", False)),
        "related_id": str(doc.get("related_id")) if doc.get("related_id") else None,
        "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", ""))
    }

@notification_bp.route("", methods=["GET"])
@authenticate_user
def get_user_notifications():
    """
    Get In-App Notifications for Current Authenticated User
    Returns notifications list sorted by created_at DESC and unread count.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_id = ObjectId(g.current_user["_id"])

    cursor = db.notifications.find({"user_id": user_id}).sort("created_at", -1).limit(50)
    notifications_list = [format_notification(doc) for doc in cursor]

    unread_count = db.notifications.count_documents({"user_id": user_id, "read": False})

    return jsonify({
        "success": True,
        "data": {
            "notifications": notifications_list,
            "unread_count": unread_count,
            "total": len(notifications_list)
        }
    }), 200

@notification_bp.route("/<id>/read", methods=["PUT"])
@authenticate_user
def mark_notification_read(id):
    """
    Mark Single Notification as Read
    Ensures users can only mark their own notifications as read.
    """
    if not id or not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid notification id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_id = ObjectId(g.current_user["_id"])
    notif_obj_id = ObjectId(id)

    doc = db.notifications.find_one({"_id": notif_obj_id})
    if not doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Notification not found."}), 404

    if str(doc.get("user_id")) != str(user_id):
        return jsonify({"success": False, "error": "Forbidden", "message": "You are not authorized to update this notification."}), 403

    db.notifications.update_one({"_id": notif_obj_id}, {"$set": {"read": True, "updated_at": datetime.now(timezone.utc)}})
    updated_doc = db.notifications.find_one({"_id": notif_obj_id})

    unread_count = db.notifications.count_documents({"user_id": user_id, "read": False})

    return jsonify({
        "success": True,
        "message": "Notification marked as read.",
        "data": {
            "notification": format_notification(updated_doc),
            "unread_count": unread_count
        }
    }), 200

@notification_bp.route("/read-all", methods=["PUT"])
@authenticate_user
def mark_all_notifications_read():
    """
    Mark All Notifications as Read for Authenticated User
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_id = ObjectId(g.current_user["_id"])

    result = db.notifications.update_many(
        {"user_id": user_id, "read": False},
        {"$set": {"read": True, "updated_at": datetime.now(timezone.utc)}}
    )

    return jsonify({
        "success": True,
        "message": f"All unread notifications ({result.modified_count}) marked as read.",
        "data": {
            "marked_read_count": result.modified_count,
            "unread_count": 0
        }
    }), 200
