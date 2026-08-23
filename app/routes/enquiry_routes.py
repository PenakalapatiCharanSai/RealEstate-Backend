import re
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
from bson import ObjectId
from app.utils.db import get_db
from app.middleware.auth_middleware import authenticate_user
from app.models.constants import ENQUIRY_STATUSES
from app.utils.notification_utils import create_notification

enquiry_bp = Blueprint("enquiry", __name__, url_prefix="/api/enquiries")


def format_enquiry(doc, prop_map=None, user_map=None):
    """
    Format Mongo enquiry document into JSON-serializable structure with populated references.
    """
    if not doc:
        return None

    prop_id_str = str(doc.get("property_id")) if doc.get("property_id") else None
    agent_id_str = str(doc.get("agent_id")) if doc.get("agent_id") else None
    customer_id_str = str(doc.get("customer_id")) if doc.get("customer_id") else None

    prop_info = None
    if prop_map and prop_id_str in prop_map:
        prop_info = prop_map[prop_id_str]

    agent_info = None
    if user_map and agent_id_str in user_map:
        agent_info = user_map[agent_id_str]

    customer_info = {
        "id": customer_id_str,
        "name": doc.get("customer_name", ""),
        "email": doc.get("customer_email", ""),
        "phone": doc.get("phone", "")
    }
    if user_map and customer_id_str in user_map:
        c_user = user_map[customer_id_str]
        customer_info["name"] = c_user.get("name") or customer_info["name"]
        customer_info["email"] = c_user.get("email") or customer_info["email"]
        customer_info["phone"] = c_user.get("phone") or customer_info["phone"]

    return {
        "id": str(doc["_id"]),
        "customer_id": customer_id_str,
        "customer_name": customer_info["name"],
        "customer_email": customer_info["email"],
        "phone": customer_info["phone"],
        "customer": customer_info,
        "property_id": prop_id_str,
        "agent_id": agent_id_str,
        "message": doc.get("message", ""),
        "response_message": doc.get("response_message", ""),
        "status": doc.get("status", "new"),
        "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", "")),
        "property": prop_info,
        "agent": agent_info
    }


@enquiry_bp.route("", methods=["POST"])
@authenticate_user
def create_enquiry():
    """
    Create Property Enquiry
    Validates message and approved property_id, populates customer and assigned agent IDs.
    """
    data = request.get_json() or {}
    property_id = data.get("property_id") or data.get("propertyId")
    message = data.get("message", "").strip()
    phone = data.get("phone", "").strip()

    if not message:
        return jsonify({"success": False, "error": "Validation Error", "message": "Enquiry message is required."}), 400

    if not property_id or not ObjectId.is_valid(property_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid property_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    prop_obj_id = ObjectId(property_id)
    prop_doc = db.properties.find_one({"_id": prop_obj_id, "approval_status": "Approved"})

    if not prop_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Approved property not found."}), 404

    customer_user = g.current_user
    customer_id = ObjectId(customer_user["_id"])
    agent_id = prop_doc.get("agent_id") or prop_doc.get("owner_id")

    enquiry_doc = {
        "customer_id": customer_id,
        "customer_name": customer_user.get("name", "Customer"),
        "customer_email": customer_user.get("email", ""),
        "phone": phone or customer_user.get("phone", ""),
        "property_id": prop_obj_id,
        "agent_id": agent_id,
        "message": message,
        "response_message": "",
        "status": "new",
        "created_at": datetime.now(timezone.utc)
    }

    result = db.enquiries.insert_one(enquiry_doc)
    enquiry_doc["_id"] = result.inserted_id

    # Increment property enquiry counts
    db.properties.update_one({"_id": prop_obj_id}, {"$inc": {"enquiry_count": 1, "enquiries_count": 1}})

    # Send In-App Notification to Property Agent / Owner
    if agent_id:
        create_notification(
            db=db,
            user_id=agent_id,
            type_str="new_enquiry",
            title="New Property Enquiry",
            message=f"New enquiry received for '{prop_doc.get('title')}' from {customer_user.get('name', 'Customer')}.",
            related_id=result.inserted_id
        )

        # Dispatch Resend Email Notification to Agent / Owner
        try:
            agent_user = db.users.find_one({"_id": agent_id})
            if agent_user and agent_user.get("email"):
                from app.services.notification_service import send_property_inquiry_email
                send_property_inquiry_email(
                    owner_email=agent_user["email"],
                    owner_name=agent_user.get("name", "Property Representative"),
                    buyer_name=customer_user.get("name", "Customer"),
                    buyer_email=customer_user.get("email", ""),
                    buyer_phone=phone or customer_user.get("phone", ""),
                    property_title=prop_doc.get("title", "Property"),
                    property_location=prop_doc.get("location", "N/A"),
                    message=message
                )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).error(f"[ENQUIRY EMAIL NOTICE] Non-fatal email error: {mail_err}")

    # Dispatch Resend Confirmation Email to Buyer
    if customer_user.get("email"):
        try:
            from app.services.notification_service import send_inquiry_confirmation_email
            send_inquiry_confirmation_email(
                buyer_email=customer_user["email"],
                buyer_name=customer_user.get("name", "Customer"),
                property_title=prop_doc.get("title", "Property"),
                property_location=prop_doc.get("location", "N/A"),
                message=message
            )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).error(f"[ENQUIRY CONFIRMATION EMAIL NOTICE] Non-fatal email error: {mail_err}")

    return jsonify({
        "success": True,
        "message": "Enquiry submitted successfully.",
        "data": {
            "enquiry": format_enquiry(enquiry_doc, prop_map={str(prop_obj_id): {"title": prop_doc.get("title"), "price": prop_doc.get("price"), "location": prop_doc.get("location")}})
        }
    }), 201


@enquiry_bp.route("", methods=["GET"])
@authenticate_user
def get_enquiries():
    """
    List Enquiries based on User Role:
    - Customer: View sent enquiries (customer_id == user_id)
    - Agent/Owner: View enquiries for assigned properties (agent_id == user_id)
    - Admin: View all marketplace enquiries with search, status filtering, and pagination.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user = g.current_user
    user_id = ObjectId(user["_id"])
    role = user.get("role", "customer").lower()

    search_term = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().lower()

    try:
        page = max(1, int(request.args.get("page", 1)))
        limit = max(1, min(100, int(request.args.get("limit", 10))))
    except ValueError:
        page = 1
        limit = 10

    query = {}

    if role in ["agent", "owner"]:
        query["agent_id"] = user_id
    elif role != "admin":
        query["customer_id"] = user_id

    if status_filter and status_filter != "all":
        query["status"] = status_filter

    if search_term:
        regex = re.compile(re.escape(search_term), re.IGNORECASE)

        # Match properties first for search term
        matching_props = list(db.properties.find({"$or": [{"title": regex}, {"location": regex}]}, {"_id": 1}))
        matching_prop_ids = [p["_id"] for p in matching_props]

        query["$or"] = [
            {"customer_name": regex},
            {"customer_email": regex},
            {"phone": regex},
            {"message": regex},
            {"property_id": {"$in": matching_prop_ids}}
        ]

    total = db.enquiries.count_documents(query)

    skip = (page - 1) * limit
    cursor = db.enquiries.find(query).sort("created_at", -1).skip(skip).limit(limit)
    enquiries_list = list(cursor)

    if not enquiries_list:
        return jsonify({
            "success": True,
            "data": {
                "enquiries": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 1
            }
        }), 200

    # Collect property and user details for population
    prop_ids = list(set([doc["property_id"] for doc in enquiries_list if doc.get("property_id")]))
    agent_ids = list(set([doc["agent_id"] for doc in enquiries_list if doc.get("agent_id")]))
    customer_ids = list(set([doc["customer_id"] for doc in enquiries_list if doc.get("customer_id")]))

    all_user_ids = list(set(agent_ids + customer_ids))

    prop_cursor = db.properties.find({"_id": {"$in": prop_ids}})
    prop_map = {
        str(p["_id"]): {
            "id": str(p["_id"]),
            "title": p.get("title"),
            "location": p.get("location"),
            "price": p.get("price"),
            "type": p.get("type"),
            "transaction_type": p.get("transaction_type"),
            "images": p.get("images", [])
        } for p in prop_cursor
    }

    user_cursor = db.users.find({"_id": {"$in": all_user_ids}})
    user_map = {
        str(u["_id"]): {
            "name": u.get("name"),
            "email": u.get("email"),
            "phone": u.get("phone", ""),
            "role": u.get("role")
        } for u in user_cursor
    }

    formatted = [format_enquiry(doc, prop_map, user_map) for doc in enquiries_list]

    return jsonify({
        "success": True,
        "data": {
            "enquiries": formatted,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
    }), 200


@enquiry_bp.route("/<enquiry_id>", methods=["GET"])
@authenticate_user
def get_enquiry_by_id(enquiry_id):
    """
    Get Single Enquiry Details
    Enforces security authorization per role.
    """
    if not enquiry_id or not ObjectId.is_valid(enquiry_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid enquiry_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    enquiry_doc = db.enquiries.find_one({"_id": ObjectId(enquiry_id)})
    if not enquiry_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Enquiry record not found."}), 404

    user = g.current_user
    user_id = str(user["_id"])
    role = user.get("role", "customer").lower()

    # Authorization Check
    is_customer_owner = str(enquiry_doc.get("customer_id")) == user_id
    is_assigned_agent = str(enquiry_doc.get("agent_id")) == user_id
    is_admin = (role == "admin")

    if not (is_customer_owner or is_assigned_agent or is_admin):
        return jsonify({"success": False, "error": "Forbidden", "message": "You are not authorized to view this enquiry."}), 403

    # Populate details
    prop_doc = db.properties.find_one({"_id": enquiry_doc.get("property_id")}) if enquiry_doc.get("property_id") else None
    agent_doc = db.users.find_one({"_id": enquiry_doc.get("agent_id")}) if enquiry_doc.get("agent_id") else None
    customer_doc = db.users.find_one({"_id": enquiry_doc.get("customer_id")}) if enquiry_doc.get("customer_id") else None

    prop_map = {str(prop_doc["_id"]): {
        "id": str(prop_doc["_id"]),
        "title": prop_doc.get("title"),
        "price": prop_doc.get("price"),
        "location": prop_doc.get("location"),
        "type": prop_doc.get("type"),
        "transaction_type": prop_doc.get("transaction_type"),
        "images": prop_doc.get("images", [])
    }} if prop_doc else None

    user_map = {}
    if agent_doc:
        user_map[str(agent_doc["_id"])] = {"name": agent_doc.get("name"), "email": agent_doc.get("email"), "phone": agent_doc.get("phone", ""), "role": agent_doc.get("role")}
    if customer_doc:
        user_map[str(customer_doc["_id"])] = {"name": customer_doc.get("name"), "email": customer_doc.get("email"), "phone": customer_doc.get("phone", ""), "role": customer_doc.get("role")}

    return jsonify({
        "success": True,
        "data": {
            "enquiry": format_enquiry(enquiry_doc, prop_map, user_map)
        }
    }), 200


@enquiry_bp.route("/<enquiry_id>", methods=["PUT"])
@authenticate_user
def update_enquiry_status(enquiry_id):
    """
    Update Enquiry Status
    Allowed statuses: new, contacted, in_progress, resolved, closed.
    Restricted to assigned agent/owner or admin.
    """
    if not enquiry_id or not ObjectId.is_valid(enquiry_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid enquiry_id is required."}), 400

    data = request.get_json() or {}
    new_status = data.get("status", "").strip().lower()
    response_message = data.get("response_message", "").strip()

    if not new_status or new_status not in ENQUIRY_STATUSES:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": f"Invalid status '{new_status}'. Allowed values: {ENQUIRY_STATUSES}"
        }), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    enquiry_doc = db.enquiries.find_one({"_id": ObjectId(enquiry_id)})
    if not enquiry_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Enquiry record not found."}), 404

    user = g.current_user
    user_id = str(user["_id"])
    role = user.get("role", "customer").lower()

    is_assigned_agent = str(enquiry_doc.get("agent_id")) == user_id
    is_admin = (role == "admin")

    if not (is_assigned_agent or is_admin):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "Only the assigned agent or an admin can update enquiry status."
        }), 403

    update_fields = {
        "status": new_status,
        "updated_at": datetime.now(timezone.utc)
    }

    if response_message:
        update_fields["response_message"] = response_message

    db.enquiries.update_one({"_id": ObjectId(enquiry_id)}, {"$set": update_fields})

    updated_doc = db.enquiries.find_one({"_id": ObjectId(enquiry_id)})

    # Re-populate
    prop_doc = db.properties.find_one({"_id": updated_doc.get("property_id")}) if updated_doc.get("property_id") else None
    agent_doc = db.users.find_one({"_id": updated_doc.get("agent_id")}) if updated_doc.get("agent_id") else None
    customer_doc = db.users.find_one({"_id": updated_doc.get("customer_id")}) if updated_doc.get("customer_id") else None

    prop_map = {str(prop_doc["_id"]): {"id": str(prop_doc["_id"]), "title": prop_doc.get("title"), "price": prop_doc.get("price"), "location": prop_doc.get("location")}} if prop_doc else None
    user_map = {}
    if agent_doc:
        user_map[str(agent_doc["_id"])] = {"name": agent_doc.get("name"), "email": agent_doc.get("email"), "phone": agent_doc.get("phone", ""), "role": agent_doc.get("role")}
    if customer_doc:
        user_map[str(customer_doc["_id"])] = {"name": customer_doc.get("name"), "email": customer_doc.get("email"), "phone": customer_doc.get("phone", ""), "role": customer_doc.get("role")}

    return jsonify({
        "success": True,
        "message": f"Enquiry status updated to '{new_status}' successfully.",
        "data": {
            "enquiry": format_enquiry(updated_doc, prop_map, user_map)
        }
    }), 200
