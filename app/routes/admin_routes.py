from datetime import datetime, timezone
import re
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db
from app.middleware import authenticate_user, role_required
from app.models import PropertyModel, UserModel
from app.utils.notification_utils import create_notification

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")

# ==========================================
# MODULE 9 / MODULE 22 — ADMIN PROPERTY ENDPOINTS
# ==========================================

@admin_bp.route("/properties", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_all_admin_properties():
    """
    Get All Platform Properties (Admin Only)
    Supports search (title, location, address, agent name), approval_status filter, availability status filter, and pagination.
    Attaches populated agent/owner details to each property object.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    search_term = request.args.get("search", "").strip()
    approval_filter = request.args.get("approval_status", "").strip().lower()
    status_filter = request.args.get("status", "").strip().lower()

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = max(1, min(100, int(request.args.get("limit", 10))))
    except ValueError:
        page = 1
        limit = 10

    query = {}

    if approval_filter and approval_filter != "all":
        # Case insensitive regex match for Pending, Approved, Rejected
        query["approval_status"] = re.compile(f"^{re.escape(approval_filter)}$", re.IGNORECASE)

    if status_filter and status_filter != "all":
        # Case insensitive regex match for Available, Sold, Rented, Unavailable
        query["status"] = re.compile(f"^{re.escape(status_filter)}$", re.IGNORECASE)

    if search_term:
        regex = re.compile(re.escape(search_term), re.IGNORECASE)
        # Find matching agent user IDs first
        matching_users = list(db.users.find({"$or": [{"name": regex}, {"email": regex}]}, {"_id": 1}))
        matching_user_ids = [u["_id"] for u in matching_users]

        query["$or"] = [
            {"title": regex},
            {"location": regex},
            {"address": regex},
            {"type": regex},
            {"agent_id": {"$in": matching_user_ids}}
        ]

    total = db.properties.count_documents(query)

    skip = (page - 1) * limit
    cursor = db.properties.find(query).sort("created_at", -1).skip(skip).limit(limit)

    properties = []
    for doc in cursor:
        formatted = PropertyModel.format_property(doc)
        # Populate Agent Info
        agent_id = doc.get("agent_id")
        if agent_id and ObjectId.is_valid(agent_id):
            agent_doc = db.users.find_one({"_id": ObjectId(agent_id)})
            if agent_doc:
                formatted["agent"] = UserModel.format_user(agent_doc)
        properties.append(formatted)

    return jsonify({
        "success": True,
        "data": {
            "properties": properties,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
    }), 200


@admin_bp.route("/properties/pending", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_pending_properties():
    """
    Get Pending Property Submissions (Admin Only)
    Retrieves all properties currently awaiting admin approval.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    query = {"approval_status": "Pending"}
    cursor = db.properties.find(query).sort("created_at", -1)
    properties = []
    for doc in cursor:
        formatted = PropertyModel.format_property(doc)
        agent_id = doc.get("agent_id")
        if agent_id and ObjectId.is_valid(agent_id):
            agent_doc = db.users.find_one({"_id": ObjectId(agent_id)})
            if agent_doc:
                formatted["agent"] = UserModel.format_user(agent_doc)
        properties.append(formatted)

    return jsonify({
        "success": True,
        "data": {
            "properties": properties,
            "total": len(properties)
        }
    }), 200


@admin_bp.route("/properties/<id>", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_admin_property_details(id):
    """
    Get Single Property Full Details (Admin Only)
    Returns property document populated with owner/agent credentials and platform stats.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    property_doc = db.properties.find_one({"_id": ObjectId(id)})
    if not property_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    formatted = PropertyModel.format_property(property_doc)
    agent_id = property_doc.get("agent_id")
    if agent_id and ObjectId.is_valid(agent_id):
        agent_doc = db.users.find_one({"_id": ObjectId(agent_id)})
        if agent_doc:
            formatted["agent"] = UserModel.format_user(agent_doc)

    prop_obj_id = ObjectId(id)
    enquiries_count = db.enquiries.count_documents({"property_id": prop_obj_id})
    visits_count = db.visits.count_documents({"property_id": prop_obj_id})

    return jsonify({
        "success": True,
        "data": {
            "property": formatted,
            "stats": {
                "enquiries_count": enquiries_count,
                "visits_count": visits_count
            }
        }
    }), 200


@admin_bp.route("/properties/<id>/approve", methods=["PUT"])
@authenticate_user
@role_required("admin")
def approve_property(id):
    """
    Approve Property Listing (Admin Only)
    Sets approval_status = 'Approved' and status = 'Available'.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    property_doc = db.properties.find_one({"_id": ObjectId(id)})
    if not property_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    now = datetime.now(timezone.utc)
    update_data = {
        "approval_status": "Approved",
        "status": "Available",
        "rejection_reason": "",
        "updated_at": now
    }

    db.properties.update_one({"_id": ObjectId(id)}, {"$set": update_data})
    updated_doc = db.properties.find_one({"_id": ObjectId(id)})
    formatted_prop = PropertyModel.format_property(updated_doc)

    # Notify Listing Agent
    agent_id = updated_doc.get("agent_id") or updated_doc.get("owner_id")
    if agent_id:
        create_notification(
            db=db,
            user_id=agent_id,
            type_str="property_approval",
            title="Property Listing Approved",
            message=f"Your property listing '{formatted_prop.get('title')}' has been approved and is now live.",
            related_id=updated_doc["_id"]
        )

        try:
            agent_user = db.users.find_one({"_id": ObjectId(agent_id)}) if ObjectId.is_valid(agent_id) else None
            if agent_user and agent_user.get("email"):
                from app.services.notification_service import send_property_approved_email
                send_property_approved_email(
                    owner_email=agent_user["email"],
                    owner_name=agent_user.get("name", "Property Representative"),
                    property_title=formatted_prop.get("title", "Property"),
                    property_location=formatted_prop.get("location", "N/A")
                )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).error(f"[PROPERTY APPROVED EMAIL NOTICE] Non-fatal error: {mail_err}")

    return jsonify({
        "success": True,
        "message": f"Property '{formatted_prop.get('title')}' has been approved successfully and is now publicly available.",
        "data": {
            "property": formatted_prop
        }
    }), 200


@admin_bp.route("/properties/<id>/reject", methods=["PUT"])
@authenticate_user
@role_required("admin")
def reject_property(id):
    """
    Reject Property Listing (Admin Only)
    Sets approval_status = 'Rejected' and records optional rejection_reason.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    property_doc = db.properties.find_one({"_id": ObjectId(id)})
    if not property_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    data = request.get_json() or {}
    rejection_reason = data.get("rejection_reason", "").strip()
    if not rejection_reason:
        rejection_reason = "Listing does not meet verification standards."

    now = datetime.now(timezone.utc)
    update_data = {
        "approval_status": "Rejected",
        "rejection_reason": rejection_reason,
        "updated_at": now
    }

    db.properties.update_one({"_id": ObjectId(id)}, {"$set": update_data})
    updated_doc = db.properties.find_one({"_id": ObjectId(id)})
    formatted_prop = PropertyModel.format_property(updated_doc)

    # Notify Listing Agent
    agent_id = updated_doc.get("agent_id") or updated_doc.get("owner_id")
    if agent_id:
        create_notification(
            db=db,
            user_id=agent_id,
            type_str="property_rejection",
            title="Property Listing Rejected",
            message=f"Your property listing '{formatted_prop.get('title')}' was rejected. Reason: {rejection_reason}",
            related_id=updated_doc["_id"]
        )

        try:
            agent_user = db.users.find_one({"_id": ObjectId(agent_id)}) if ObjectId.is_valid(agent_id) else None
            if agent_user and agent_user.get("email"):
                from app.services.notification_service import send_property_rejected_email
                send_property_rejected_email(
                    owner_email=agent_user["email"],
                    owner_name=agent_user.get("name", "Property Representative"),
                    property_title=formatted_prop.get("title", "Property"),
                    property_location=formatted_prop.get("location", "N/A"),
                    rejection_reason=rejection_reason
                )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).error(f"[PROPERTY REJECTED EMAIL NOTICE] Non-fatal error: {mail_err}")

    return jsonify({
        "success": True,
        "message": f"Property '{formatted_prop.get('title')}' has been rejected.",
        "data": {
            "property": formatted_prop
        }
    }), 200


@admin_bp.route("/properties/<id>/deactivate", methods=["PUT"])
@authenticate_user
@role_required("admin")
def deactivate_property(id):
    """
    Deactivate Property Listing Endpoint (Admin Only)
    Sets availability status = 'Unavailable' without changing approval_status.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    property_doc = db.properties.find_one({"_id": ObjectId(id)})
    if not property_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    now = datetime.now(timezone.utc)
    db.properties.update_one({"_id": ObjectId(id)}, {"$set": {"status": "Unavailable", "updated_at": now}})
    updated_doc = db.properties.find_one({"_id": ObjectId(id)})
    formatted_prop = PropertyModel.format_property(updated_doc)

    return jsonify({
        "success": True,
        "message": f"Property '{formatted_prop.get('title')}' has been deactivated (marked Unavailable).",
        "data": {
            "property": formatted_prop
        }
    }), 200


@admin_bp.route("/properties/<id>", methods=["DELETE"])
@authenticate_user
@role_required("admin")
def delete_admin_property(id):
    """
    Delete Property Listing Endpoint (Admin Only)
    Permanently deletes a property listing document from MongoDB.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    property_doc = db.properties.find_one({"_id": ObjectId(id)})
    if not property_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db.properties.delete_one({"_id": ObjectId(id)})

    return jsonify({
        "success": True,
        "message": f"Property listing '{property_doc.get('title')}' deleted successfully."
    }), 200


# ==========================================
# MODULE 21 — ADMIN USER MANAGEMENT ENDPOINTS
# ==========================================

@admin_bp.route("/users", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_all_users():
    """
    List Registered Users Endpoint (Admin Only)
    Supports search (name, email, phone), role filter, status filter, and pagination.
    Passes formatted users excluding password fields.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    search_term = request.args.get("search", "").strip()
    role_filter = request.args.get("role", "").strip().lower()
    status_filter = request.args.get("status", "").strip().lower()

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = max(1, min(100, int(request.args.get("limit", 10))))
    except ValueError:
        page = 1
        limit = 10

    query = {}

    if search_term:
        regex = re.compile(re.escape(search_term), re.IGNORECASE)
        query["$or"] = [
            {"name": regex},
            {"email": regex},
            {"phone": regex}
        ]

    if role_filter and role_filter != "all":
        query["role"] = role_filter

    if status_filter and status_filter != "all":
        query["status"] = status_filter

    total = db.users.count_documents(query)

    skip = (page - 1) * limit
    cursor = db.users.find(query).sort("created_at", -1).skip(skip).limit(limit)

    users = [UserModel.format_user(doc) for doc in cursor]

    return jsonify({
        "success": True,
        "data": {
            "users": users,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
    }), 200


@admin_bp.route("/users/<id>", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_user_details(id):
    """
    Get Single User Profile Details Endpoint (Admin Only)
    Retrieves complete user record + platform stats (property listings count, enquiries, visit requests).
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "User not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_doc = db.users.find_one({"_id": ObjectId(id)})
    if not user_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "User not found."}), 404

    user_id = user_doc["_id"]
    formatted_user = UserModel.format_user(user_doc)

    # Activity Metrics
    properties_count = db.properties.count_documents({"agent_id": user_id})
    enquiries_count = db.enquiries.count_documents({"$or": [{"user_id": user_id}, {"agent_id": user_id}]})
    visits_count = db.visits.count_documents({"$or": [{"user_id": user_id}, {"agent_id": user_id}]})

    return jsonify({
        "success": True,
        "data": {
            "user": formatted_user,
            "stats": {
                "properties_count": properties_count,
                "enquiries_count": enquiries_count,
                "visits_count": visits_count
            }
        }
    }), 200


@admin_bp.route("/users/<id>/status", methods=["PUT", "PATCH"])
@authenticate_user
@role_required("admin")
def update_user_status(id):
    """
    Activate / Deactivate User Account Endpoint (Admin Only)
    Payload: { "status": "active" | "inactive" }
    Enforces sole admin safety rule: Prevents deactivating the sole remaining active administrator.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "User not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_doc = db.users.find_one({"_id": ObjectId(id)})
    if not user_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "User not found."}), 404

    data = request.get_json() or {}
    new_status = str(data.get("status", "")).strip().lower()

    if new_status not in ["active", "inactive"]:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": "Invalid status. Allowed values: 'active', 'inactive'."
        }), 400

    current_role = user_doc.get("role", "").lower()
    current_status = user_doc.get("status", "").lower()

    # Safety Guard: Do not allow deactivating the sole remaining active admin
    if current_role == "admin" and new_status == "inactive" and current_status == "active":
        active_admin_count = db.users.count_documents({"role": "admin", "status": "active"})
        if active_admin_count <= 1:
            return jsonify({
                "success": False,
                "error": "Action Blocked",
                "message": "Action blocked. Cannot deactivate the sole remaining active administrator."
            }), 400

    now = datetime.now(timezone.utc)
    db.users.update_one({"_id": ObjectId(id)}, {"$set": {"status": new_status, "updated_at": now}})
    updated_doc = db.users.find_one({"_id": ObjectId(id)})
    formatted_user = UserModel.format_user(updated_doc)

    return jsonify({
        "success": True,
        "message": f"User account '{formatted_user.get('name')}' is now {new_status}.",
        "data": {
            "user": formatted_user
        }
    }), 200


# ==========================================
# MODULE 26 — ADMIN ANALYTICS ENDPOINTS
# ==========================================

@admin_bp.route("/analytics", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_admin_analytics():
    """
    Get System-Wide Real Analytics (Admin Only)
    Calculates statistics directly from MongoDB:
    1. Summary metrics (total_users, total_properties, total_enquiries, total_visits)
    2. Property listing creation trends over time
    3. User registrations over time
    4. Property type distribution (Apartment, Villa, Plot, etc.)
    5. Transaction type distribution (Sale vs Rent)
    6. Enquiry status distribution
    7. Visit status distribution
    8. Most searched locations (from db.search_logs & db.properties)
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    # Summary metric totals
    total_users = db.users.count_documents({})
    total_properties = db.properties.count_documents({})
    total_enquiries = db.enquiries.count_documents({})
    total_visits = db.visits.count_documents({})

    # 1. Property Type Distribution
    prop_types_pipeline = [
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    prop_type_cursor = list(db.properties.aggregate(prop_types_pipeline))
    property_types = [
        {"type": item["_id"] or "Uncategorized", "count": item["count"]}
        for item in prop_type_cursor
    ]

    # 2. Sale vs Rent Distribution
    tx_pipeline = [
        {"$group": {"_id": "$transaction_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    tx_cursor = list(db.properties.aggregate(tx_pipeline))
    sale_vs_rent = [
        {"transaction_type": item["_id"] or "Other", "count": item["count"]}
        for item in tx_cursor
    ]

    # 3. Enquiry Status Breakdown
    enq_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    enq_cursor = list(db.enquiries.aggregate(enq_pipeline))
    enquiry_statuses = [
        {"status": item["_id"] or "new", "count": item["count"]}
        for item in enq_cursor
    ]

    # 4. Visit Status Breakdown
    visit_pipeline = [
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}
    ]
    visit_cursor = list(db.visits.aggregate(visit_pipeline))
    visit_statuses = [
        {"status": item["_id"] or "requested", "count": item["count"]}
        for item in visit_cursor
    ]

    # 5. Most Searched Locations
    top_search_pipeline = [
        {"$group": {"_id": "$location", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    search_log_cursor = list(db.search_logs.aggregate(top_search_pipeline))
    searched_locations = []
    if search_log_cursor:
        searched_locations = [
            {"location": str(item["_id"]).title(), "count": item["count"]}
            for item in search_log_cursor if item["_id"]
        ]

    if len(searched_locations) < 5:
        prop_loc_pipeline = [
            {"$group": {"_id": "$location", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        prop_loc_cursor = list(db.properties.aggregate(prop_loc_pipeline))
        existing_locs = {l["location"].lower() for l in searched_locations}
        for item in prop_loc_cursor:
            if item["_id"] and str(item["_id"]).lower() not in existing_locs:
                searched_locations.append({"location": str(item["_id"]).title(), "count": item["count"]})
                existing_locs.add(str(item["_id"]).lower())
                if len(searched_locations) >= 5:
                    break

    # 6. Properties Creation Trend
    months_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    prop_trend_pipeline = [
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"}
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1}},
        {"$limit": 12}
    ]
    prop_trend_cursor = list(db.properties.aggregate(prop_trend_pipeline))
    property_trends = [
        {
            "label": f"{months_names[item['_id']['month']]} {item['_id']['year']}" if item["_id"].get("month") else "Recent",
            "count": item["count"]
        }
        for item in prop_trend_cursor if item["_id"]
    ]

    # 7. User Registration Trend
    user_trend_pipeline = [
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"}
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": {"_id.year": 1, "_id.month": 1}},
        {"$limit": 12}
    ]
    user_trend_cursor = list(db.users.aggregate(user_trend_pipeline))
    user_trends = [
        {
            "label": f"{months_names[item['_id']['month']]} {item['_id']['year']}" if item["_id"].get("month") else "Recent",
            "count": item["count"]
        }
        for item in user_trend_cursor if item["_id"]
    ]

    return jsonify({
        "success": True,
        "data": {
            "summary": {
                "total_users": total_users,
                "total_properties": total_properties,
                "total_enquiries": total_enquiries,
                "total_visits": total_visits
            },
            "property_types": property_types,
            "sale_vs_rent": sale_vs_rent,
            "enquiry_statuses": enquiry_statuses,
            "visit_statuses": visit_statuses,
            "searched_locations": searched_locations,
            "property_trends": property_trends,
            "user_trends": user_trends
        }
    }), 200


@admin_bp.route("/enquiries", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_all_admin_enquiries():
    """
    Get Master Platform Enquiries List (Admin Only)
    """
    from app.routes.enquiry_routes import get_enquiries
    return get_enquiries()


@admin_bp.route("/visits", methods=["GET"])
@authenticate_user
@role_required("admin")
def get_all_admin_visits():
    """
    Get Master Platform Visit Schedules (Admin Only)
    """
    from app.routes.visit_routes import get_visits
    return get_visits()

