import re
from flask import Blueprint, request, jsonify, g
from datetime import datetime, timezone
from bson import ObjectId
from app.utils.db import get_db
from app.middleware.auth_middleware import authenticate_user
from app.models.constants import VISIT_STATUSES
from app.utils.notification_utils import create_notification

visit_bp = Blueprint("visit", __name__, url_prefix="/api/visits")


def format_visit(doc, prop_map=None, user_map=None):
    """
    Format Mongo visit document into JSON-serializable structure with populated references
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
        "visit_date": doc.get("visit_date", ""),
        "visit_time": doc.get("visit_time", ""),
        "message": doc.get("message", ""),
        "status": doc.get("status", "requested"),
        "created_at": doc.get("created_at").isoformat() if isinstance(doc.get("created_at"), datetime) else str(doc.get("created_at", "")),
        "property": prop_info,
        "agent": agent_info
    }


@visit_bp.route("", methods=["POST"])
@authenticate_user
def create_visit():
    """
    Create Property Visit Request
    Validates visit_date, visit_time, and approved property_id.
    """
    data = request.get_json() or {}
    property_id = data.get("property_id") or data.get("propertyId")
    visit_date = data.get("visit_date") or data.get("visitDate")
    visit_time = data.get("visit_time") or data.get("visitTime")
    message = data.get("message", "").strip()
    phone = data.get("phone", "").strip()

    if not visit_date or not str(visit_date).strip():
        return jsonify({"success": False, "error": "Validation Error", "message": "Preferred visit date is required."}), 400

    if not visit_time or not str(visit_time).strip():
        return jsonify({"success": False, "error": "Validation Error", "message": "Preferred visit time is required."}), 400

    if not property_id or not ObjectId.is_valid(property_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid property_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    prop_obj_id = ObjectId(property_id)
    prop_doc = db.properties.find_one({"_id": prop_obj_id, "approval_status": "Approved"})

    if not prop_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Approved property listing not found."}), 404

    customer_user = g.current_user
    customer_id = ObjectId(customer_user["_id"])
    agent_id = prop_doc.get("agent_id") or prop_doc.get("owner_id")

    visit_doc = {
        "customer_id": customer_id,
        "customer_name": customer_user.get("name", "Customer"),
        "customer_email": customer_user.get("email", ""),
        "phone": phone or customer_user.get("phone", ""),
        "property_id": prop_obj_id,
        "agent_id": agent_id,
        "visit_date": str(visit_date).strip(),
        "visit_time": str(visit_time).strip(),
        "message": message,
        "status": "requested",
        "created_at": datetime.now(timezone.utc)
    }

    result = db.visits.insert_one(visit_doc)
    visit_doc["_id"] = result.inserted_id

    # Send Notification to Property Agent / Owner
    if agent_id:
        create_notification(
            db=db,
            user_id=agent_id,
            type_str="visit_request",
            title="New Visit Request",
            message=f"Visit request for '{prop_doc.get('title')}' on {visit_date} from {customer_user.get('name', 'Customer')}.",
            related_id=result.inserted_id
        )

        # Dispatch Resend Email Notification to Agent / Owner
        try:
            agent_user = db.users.find_one({"_id": agent_id})
            if agent_user and agent_user.get("email"):
                from app.services.notification_service import send_appointment_request_email
                send_appointment_request_email(
                    owner_email=agent_user["email"],
                    owner_name=agent_user.get("name", "Property Representative"),
                    buyer_name=customer_user.get("name", "Customer"),
                    buyer_email=customer_user.get("email", ""),
                    buyer_phone=phone or customer_user.get("phone", ""),
                    property_title=prop_doc.get("title", "Property"),
                    property_location=prop_doc.get("location", "N/A"),
                    visit_date=str(visit_date).strip(),
                    visit_time=str(visit_time).strip(),
                    message=message
                )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).error(f"[VISIT REQUEST EMAIL NOTICE] Non-fatal error: {mail_err}")

    # Dispatch Resend Confirmation Email to Buyer
    if customer_user.get("email"):
        try:
            from app.services.notification_service import send_appointment_confirmation_email
            send_appointment_confirmation_email(
                buyer_email=customer_user["email"],
                buyer_name=customer_user.get("name", "Customer"),
                property_title=prop_doc.get("title", "Property"),
                property_location=prop_doc.get("location", "N/A"),
                visit_date=str(visit_date).strip(),
                visit_time=str(visit_time).strip()
            )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).error(f"[VISIT CONFIRMATION EMAIL NOTICE] Non-fatal error: {mail_err}")

    return jsonify({
        "success": True,
        "message": "Property visit request submitted successfully.",
        "data": {
            "visit": format_visit(visit_doc, prop_map={str(prop_obj_id): {"title": prop_doc.get("title"), "price": prop_doc.get("price"), "location": prop_doc.get("location")}})
        }
    }), 201


@visit_bp.route("", methods=["GET"])
@authenticate_user
def get_visits():
    """
    List Visit Requests based on User Role:
    - Customer: View own visit requests (customer_id == user_id)
    - Agent/Owner: View visit requests for assigned properties (agent_id == user_id)
    - Admin: View all marketplace visit requests with search, status filtering, date filtering, and pagination.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user = g.current_user
    user_id = ObjectId(user["_id"])
    role = user.get("role", "customer").lower()

    search_term = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip().lower()
    date_filter = request.args.get("date", "").strip()

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

    if date_filter:
        query["visit_date"] = date_filter

    if search_term:
        regex = re.compile(re.escape(search_term), re.IGNORECASE)

        matching_props = list(db.properties.find({"$or": [{"title": regex}, {"location": regex}]}, {"_id": 1}))
        matching_prop_ids = [p["_id"] for p in matching_props]

        query["$or"] = [
            {"customer_name": regex},
            {"customer_email": regex},
            {"phone": regex},
            {"message": regex},
            {"property_id": {"$in": matching_prop_ids}}
        ]

    total = db.visits.count_documents(query)

    skip = (page - 1) * limit
    cursor = db.visits.find(query).sort("created_at", -1).skip(skip).limit(limit)
    visits_list = list(cursor)

    if not visits_list:
        return jsonify({
            "success": True,
            "data": {
                "visits": [],
                "total": 0,
                "page": page,
                "limit": limit,
                "total_pages": 1
            }
        }), 200

    # Collect property and agent/customer details
    prop_ids = list(set([doc["property_id"] for doc in visits_list if doc.get("property_id")]))
    agent_ids = list(set([doc["agent_id"] for doc in visits_list if doc.get("agent_id")]))
    customer_ids = list(set([doc["customer_id"] for doc in visits_list if doc.get("customer_id")]))

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

    formatted = [format_visit(doc, prop_map, user_map) for doc in visits_list]

    return jsonify({
        "success": True,
        "data": {
            "visits": formatted,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if total > 0 else 1
        }
    }), 200


@visit_bp.route("/<visit_id>", methods=["GET"])
@authenticate_user
def get_visit_by_id(visit_id):
    """
    Get Single Visit Request Details
    Enforces authorization per role.
    """
    if not visit_id or not ObjectId.is_valid(visit_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid visit_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    visit_doc = db.visits.find_one({"_id": ObjectId(visit_id)})
    if not visit_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Visit request not found."}), 404

    user = g.current_user
    user_id = str(user["_id"])
    role = user.get("role", "customer").lower()

    is_customer_owner = str(visit_doc.get("customer_id")) == user_id
    is_assigned_agent = str(visit_doc.get("agent_id")) == user_id
    is_admin = (role == "admin")

    if not (is_customer_owner or is_assigned_agent or is_admin):
        return jsonify({"success": False, "error": "Forbidden", "message": "You are not authorized to view this visit request."}), 403

    prop_doc = db.properties.find_one({"_id": visit_doc.get("property_id")}) if visit_doc.get("property_id") else None
    agent_doc = db.users.find_one({"_id": visit_doc.get("agent_id")}) if visit_doc.get("agent_id") else None
    customer_doc = db.users.find_one({"_id": visit_doc.get("customer_id")}) if visit_doc.get("customer_id") else None

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
            "visit": format_visit(visit_doc, prop_map, user_map)
        }
    }), 200


@visit_bp.route("/<visit_id>", methods=["PUT"])
@authenticate_user
def update_visit(visit_id):
    """
    Update Visit Request Status or Details
    Rules:
    - Customer: Cannot directly alter status of a 'confirmed' visit. Can cancel 'requested' or 'rescheduled' visits.
    - Agent/Owner/Admin: Can confirm, reschedule, complete, or cancel visit requests.
    """
    if not visit_id or not ObjectId.is_valid(visit_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid visit_id is required."}), 400

    data = request.get_json() or {}
    new_status = data.get("status", "").strip().lower()

    if new_status and new_status not in VISIT_STATUSES:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": f"Invalid visit status '{new_status}'. Allowed values: {VISIT_STATUSES}"
        }), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    visit_doc = db.visits.find_one({"_id": ObjectId(visit_id)})
    if not visit_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Visit request not found."}), 404

    user = g.current_user
    user_id = str(user["_id"])
    role = user.get("role", "customer").lower()

    is_customer_owner = str(visit_doc.get("customer_id")) == user_id
    is_assigned_agent = str(visit_doc.get("agent_id")) == user_id
    is_admin = (role == "admin")

    # Customer specific rules
    if is_customer_owner and not (is_assigned_agent or is_admin):
        # Do not allow customers to change a confirmed visit directly
        if visit_doc.get("status") == "confirmed":
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "You cannot directly modify a confirmed visit schedule. Please contact the property agent."
            }), 403

        # Customers can only set status to 'cancelled'
        if new_status and new_status != "cancelled":
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "Customers are only allowed to cancel their visit requests."
            }), 403

    elif not (is_assigned_agent or is_admin):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "You are not authorized to update this visit request."
        }), 403

    update_fields = {
        "updated_at": datetime.now(timezone.utc)
    }

    if new_status:
        update_fields["status"] = new_status
    if "visit_date" in data and data["visit_date"]:
        update_fields["visit_date"] = str(data["visit_date"]).strip()
    if "visit_time" in data and data["visit_time"]:
        update_fields["visit_time"] = str(data["visit_time"]).strip()
    if "message" in data:
        update_fields["message"] = str(data["message"]).strip()

    db.visits.update_one({"_id": ObjectId(visit_id)}, {"$set": update_fields})
    updated_doc = db.visits.find_one({"_id": ObjectId(visit_id)})

    prop_doc = db.properties.find_one({"_id": updated_doc.get("property_id")}) if updated_doc.get("property_id") else None
    agent_doc = db.users.find_one({"_id": updated_doc.get("agent_id")}) if updated_doc.get("agent_id") else None
    customer_doc = db.users.find_one({"_id": updated_doc.get("customer_id")}) if updated_doc.get("customer_id") else None

    prop_map = {str(prop_doc["_id"]): {"id": str(prop_doc["_id"]), "title": prop_doc.get("title"), "price": prop_doc.get("price"), "location": prop_doc.get("location")}} if prop_doc else None
    user_map = {}
    if agent_doc:
        user_map[str(agent_doc["_id"])] = {"name": agent_doc.get("name"), "email": agent_doc.get("email"), "phone": agent_doc.get("phone", ""), "role": agent_doc.get("role")}
    if customer_doc:
        user_map[str(customer_doc["_id"])] = {"name": customer_doc.get("name"), "email": customer_doc.get("email"), "phone": customer_doc.get("phone", ""), "role": customer_doc.get("role")}

    # Send Notification on Visit Status Changes
    cust_id = updated_doc.get("customer_id")
    ag_id = updated_doc.get("agent_id")
    prop_title = prop_doc.get("title", "Property") if prop_doc else "Property"
    v_date = updated_doc.get("visit_date", "")

    if new_status == "confirmed" and cust_id:
        create_notification(
            db=db,
            user_id=cust_id,
            type_str="visit_confirmation",
            title="Visit Request Confirmed",
            message=f"Your visit request for '{prop_title}' on {v_date} has been confirmed.",
            related_id=updated_doc["_id"]
        )
    elif new_status == "rescheduled" and cust_id:
        create_notification(
            db=db,
            user_id=cust_id,
            type_str="visit_confirmation",
            title="Visit Rescheduled",
            message=f"Your visit schedule for '{prop_title}' has been rescheduled to {v_date} at {updated_doc.get('visit_time', '')}.",
            related_id=updated_doc["_id"]
        )
    elif new_status == "cancelled":
        target_user = ag_id if str(g.current_user["_id"]) == str(cust_id) else cust_id
        if target_user:
            create_notification(
                db=db,
                user_id=target_user,
                type_str="visit_confirmation",
                title="Visit Cancelled",
                message=f"The scheduled visit for '{prop_title}' on {v_date} has been cancelled.",
            )

    # Dispatch Resend Email Notification for Visit Status Update
    if new_status and customer_doc and customer_doc.get("email"):
        try:
            from app.services.notification_service import send_appointment_status_email
            send_appointment_status_email(
                buyer_email=customer_doc["email"],
                buyer_name=customer_doc.get("name", "Customer"),
                property_title=prop_title,
                status=new_status,
                notes=updated_doc.get("message")
            )
        except Exception as mail_err:
            import logging
            logging.getLogger(__name__).error(f"[VISIT STATUS EMAIL NOTICE] Non-fatal error: {mail_err}")

    return jsonify({
        "success": True,
        "message": f"Visit request updated successfully.",
        "data": {
            "visit": format_visit(updated_doc, prop_map, user_map)
        }
    }), 200


@visit_bp.route("/<visit_id>", methods=["DELETE"])
@authenticate_user
def cancel_or_delete_visit(visit_id):
    """
    Cancel/Delete Visit Request
    Sets status to 'cancelled' or removes record.
    """
    if not visit_id or not ObjectId.is_valid(visit_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid visit_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    visit_doc = db.visits.find_one({"_id": ObjectId(visit_id)})
    if not visit_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Visit request not found."}), 404

    user = g.current_user
    user_id = str(user["_id"])
    role = user.get("role", "customer").lower()

    is_customer_owner = str(visit_doc.get("customer_id")) == user_id
    is_assigned_agent = str(visit_doc.get("agent_id")) == user_id
    is_admin = (role == "admin")

    if not (is_customer_owner or is_assigned_agent or is_admin):
        return jsonify({"success": False, "error": "Forbidden", "message": "You are not authorized to cancel this visit request."}), 403

    db.visits.update_one({"_id": ObjectId(visit_id)}, {"$set": {"status": "cancelled", "updated_at": datetime.now(timezone.utc)}})

    return jsonify({
        "success": True,
        "message": "Visit request cancelled successfully."
    }), 200
