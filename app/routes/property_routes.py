from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db
from app.middleware import authenticate_user, role_required, check_ownership
from app.models import PropertyModel
from app.utils.notification_utils import create_notification
from app.models.constants import (
    PROPERTY_TYPES, TRANSACTION_TYPES, FURNISHING_TYPES, PROPERTY_STATUSES, APPROVAL_STATUSES
)

property_bp = Blueprint("properties", __name__, url_prefix="/api/properties")

VALID_PROPERTY_TYPES = ["Apartment", "Villa", "Independent House", "Commercial Property", "Plot", "Office"]
VALID_TRANSACTION_TYPES = ["Sale", "Rent"]
VALID_FURNISHING = ["Unfurnished", "Semi-Furnished", "Fully Furnished"]
VALID_STATUSES = ["Available", "Sold", "Rented", "Unavailable"]
VALID_APPROVAL_STATUSES = ["Pending", "Approved", "Rejected"]

def validate_property_input(data):
    """
    Server-side property input validation helper.
    Returns: (is_valid: bool, error_message: str | None, cleaned_data: dict)
    """
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    type_ = str(data.get("type", "Apartment")).strip()
    transaction_type = str(data.get("transaction_type", "Sale")).strip()
    location = str(data.get("location", "")).strip()
    address = str(data.get("address", "")).strip()
    furnishing = str(data.get("furnishing", "Unfurnished")).strip()
    status = str(data.get("status", "Available")).strip()
    images = data.get("images", [])

    if not title:
        return False, "Property title is required.", None

    if not description:
        return False, "Property description is required.", None

    if not location:
        return False, "Property location (city/area) is required.", None

    try:
        price = float(data.get("price", 0))
        if price <= 0:
            return False, "Price must be a positive number greater than 0.", None
    except (ValueError, TypeError):
        return False, "Price must be a valid positive number.", None

    try:
        area = float(data.get("area", 0))
        if area <= 0:
            return False, "Area must be a positive number greater than 0.", None
    except (ValueError, TypeError):
        return False, "Area must be a valid positive number.", None

    try:
        bedrooms = int(data.get("bedrooms", 0))
        if bedrooms < 0:
            return False, "Bedrooms count cannot be negative.", None
    except (ValueError, TypeError):
        return False, "Bedrooms must be a valid non-negative integer.", None

    try:
        bathrooms = int(data.get("bathrooms", 0))
        if bathrooms < 0:
            return False, "Bathrooms count cannot be negative.", None
    except (ValueError, TypeError):
        return False, "Bathrooms must be a valid non-negative integer.", None

    # Case-tolerant type check
    matched_type = next((t for t in VALID_PROPERTY_TYPES if t.lower() == type_.lower()), None)
    if not matched_type:
        return False, f"Invalid property type '{type_}'. Allowed: {', '.join(VALID_PROPERTY_TYPES)}", None

    matched_tx = next((tx for tx in VALID_TRANSACTION_TYPES if tx.lower() == transaction_type.lower()), None)
    if not matched_tx:
        return False, f"Invalid transaction type '{transaction_type}'. Allowed: {', '.join(VALID_TRANSACTION_TYPES)}", None

    matched_furnish = next((f for f in VALID_FURNISHING if f.lower() == furnishing.lower()), None)
    if not matched_furnish:
        matched_furnish = "Unfurnished"

    matched_status = next((s for s in VALID_STATUSES if s.lower() == status.lower()), None)
    if not matched_status:
        matched_status = "Available"

    parking = bool(data.get("parking", False))

    if not isinstance(images, list):
        images = []

    # Latitude validation (-90 to 90)
    lat_val = None
    if "latitude" in data and data["latitude"] is not None and str(data["latitude"]).strip() != "":
        try:
            lat_val = float(data["latitude"])
            if not (-90.0 <= lat_val <= 90.0):
                return False, "Latitude must be a valid coordinate between -90 and 90 degrees.", None
        except (ValueError, TypeError):
            return False, "Latitude must be a valid numeric value.", None

    # Longitude validation (-180 to 180)
    lng_val = None
    if "longitude" in data and data["longitude"] is not None and str(data["longitude"]).strip() != "":
        try:
            lng_val = float(data["longitude"])
            if not (-180.0 <= lng_val <= 180.0):
                return False, "Longitude must be a valid coordinate between -180 and 180 degrees.", None
        except (ValueError, TypeError):
            return False, "Longitude must be a valid numeric value.", None

    cleaned = {
        "title": title,
        "description": description,
        "type": matched_type,
        "transaction_type": matched_tx,
        "price": price,
        "location": location,
        "address": address or location,
        "area": area,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "parking": parking,
        "furnishing": matched_furnish,
        "status": matched_status,
        "images": images,
        "latitude": lat_val,
        "longitude": lng_val,
    }

    return True, None, cleaned


@property_bp.route("", methods=["GET"])
def get_properties():
    """
    Public List & Advanced Search Properties Endpoint
    Supports query param filters:
    - location: Substring regex match on location, address, title
    - type: Category property type (e.g. Apartment, Villa, Plot)
    - transaction_type: Transaction type (Sale, Rent)
    - min_price: Minimum price bound (numeric >= min_price)
    - max_price: Maximum price bound (numeric <= max_price)
    - bedrooms: Minimum bedrooms count (numeric >= bedrooms)
    - furnishing: Furnishing status (Unfurnished, Semi-Furnished, Fully Furnished)
    - agent_id, status, approval_status

    Public listings MUST ONLY return approval_status = "Approved" properties.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    query = {}

    # Approval Status Filter (Public always defaults to Approved)
    approval_status = request.args.get("approval_status")
    if approval_status and approval_status.strip():
        query["approval_status"] = {"$regex": f"^{approval_status.strip()}$", "$options": "i"}
    else:
        query["approval_status"] = {"$regex": "^Approved$", "$options": "i"}

    # Agent ID Filter
    agent_id = request.args.get("agent_id")
    if agent_id and ObjectId.is_valid(agent_id.strip()):
        query["agent_id"] = ObjectId(agent_id.strip())

    # Availability Status Filter
    status = request.args.get("status")
    if status and status.strip():
        query["status"] = {"$regex": f"^{status.strip()}$", "$options": "i"}

    # Property Type Filter
    type_ = request.args.get("type")
    if type_ and type_.strip():
        query["type"] = {"$regex": f"^{type_.strip()}$", "$options": "i"}

    # Transaction Type Filter (Sale / Rent)
    tx_type = request.args.get("transaction_type")
    if tx_type and tx_type.strip():
        query["transaction_type"] = {"$regex": f"^{tx_type.strip()}$", "$options": "i"}

    # Furnishing Filter
    furnishing = request.args.get("furnishing")
    if furnishing and furnishing.strip():
        query["furnishing"] = {"$regex": f"^{furnishing.strip()}$", "$options": "i"}

    # Location / Search Substring Filter
    location = request.args.get("location") or request.args.get("search")
    if location and location.strip():
        loc_str = location.strip()
        try:
            db.search_logs.insert_one({
                "location": loc_str.lower(),
                "query": loc_str,
                "created_at": datetime.now(timezone.utc)
            })
        except Exception:
            pass

        query["$or"] = [
            {"location": {"$regex": loc_str, "$options": "i"}},
            {"address": {"$regex": loc_str, "$options": "i"}},
            {"title": {"$regex": loc_str, "$options": "i"}},
        ]

    # Price Filtering (min_price and/or max_price)
    price_query = {}
    min_price = request.args.get("min_price")
    if min_price and min_price.strip():
        try:
            min_val = float(min_price.strip())
            if min_val >= 0:
                price_query["$gte"] = min_val
        except (ValueError, TypeError):
            pass

    max_price = request.args.get("max_price")
    if max_price and max_price.strip():
        try:
            max_val = float(max_price.strip())
            if max_val >= 0:
                price_query["$lte"] = max_val
        except (ValueError, TypeError):
            pass

    if price_query:
        query["price"] = price_query

    # Bedrooms Filter (numeric >= bedrooms)
    bedrooms = request.args.get("bedrooms")
    if bedrooms and bedrooms.strip():
        try:
            beds_val = int(bedrooms.strip())
            if beds_val >= 0:
                query["bedrooms"] = {"$gte": beds_val}
        except (ValueError, TypeError):
            pass

    # Sorting parameter mapping
    sort_param = (request.args.get("sort") or "newest").strip().lower()
    if sort_param == "price_asc":
        sort_spec = [("price", 1)]
    elif sort_param == "price_desc":
        sort_spec = [("price", -1)]
    elif sort_param == "oldest":
        sort_spec = [("created_at", 1)]
    elif sort_param == "popular":
        sort_spec = [("views_count", -1), ("favorites_count", -1), ("created_at", -1)]
    else:  # "newest" or default
        sort_spec = [("created_at", -1)]

    cursor = db.properties.find(query).sort(sort_spec)
    properties = [PropertyModel.format_property(doc) for doc in cursor]

    return jsonify({
        "success": True,
        "data": {
            "properties": properties,
            "total": len(properties)
        }
    }), 200


@property_bp.route("/my-properties", methods=["GET"])
@authenticate_user
@role_required("agent", "owner", "admin")
def get_my_properties():
    """
    Get Current Agent/Owner Properties (Includes Pending, Approved, Rejected)
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_id = ObjectId(g.current_user["_id"])
    cursor = db.properties.find({"agent_id": user_id}).sort("created_at", -1)
    properties = [PropertyModel.format_property(doc) for doc in cursor]

    return jsonify({
        "success": True,
        "data": {
            "properties": properties,
            "total": len(properties)
        }
    }), 200


@property_bp.route("/agent/dashboard-stats", methods=["GET"])
@authenticate_user
@role_required("agent", "owner", "admin")
def get_agent_dashboard_stats():
    """
    Get Agent/Owner Real Database Dashboard Statistics
    Metrics:
    - Total Properties
    - Pending Properties
    - Approved Properties
    - Rejected Properties
    - Available Properties
    - Sold Properties
    - Rented Properties
    - Unavailable Properties
    - Total Enquiries
    - Pending Visit Requests
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user_id = ObjectId(g.current_user["_id"])

    # Property statistics for current agent
    total_properties = db.properties.count_documents({"agent_id": user_id})
    pending_properties = db.properties.count_documents({"agent_id": user_id, "approval_status": {"$regex": "^Pending$", "$options": "i"}})
    approved_properties = db.properties.count_documents({"agent_id": user_id, "approval_status": {"$regex": "^Approved$", "$options": "i"}})
    rejected_properties = db.properties.count_documents({"agent_id": user_id, "approval_status": {"$regex": "^Rejected$", "$options": "i"}})

    available_properties = db.properties.count_documents({"agent_id": user_id, "status": {"$regex": "^Available$", "$options": "i"}})
    sold_properties = db.properties.count_documents({"agent_id": user_id, "status": {"$regex": "^Sold$", "$options": "i"}})
    rented_properties = db.properties.count_documents({"agent_id": user_id, "status": {"$regex": "^Rented$", "$options": "i"}})
    unavailable_properties = db.properties.count_documents({"agent_id": user_id, "status": {"$regex": "^Unavailable$", "$options": "i"}})

    # Total enquiries for current agent
    total_enquiries = db.enquiries.count_documents({"agent_id": user_id})

    # Pending visit requests for current agent
    pending_visits = db.visits.count_documents({
        "agent_id": user_id,
        "status": {"$regex": "^requested$", "$options": "i"}
    })

    return jsonify({
        "success": True,
        "data": {
            "stats": {
                "total_properties": total_properties,
                "pending_properties": pending_properties,
                "approved_properties": approved_properties,
                "rejected_properties": rejected_properties,
                "available_properties": available_properties,
                "sold_properties": sold_properties,
                "rented_properties": rented_properties,
                "unavailable_properties": unavailable_properties,
                "total_enquiries": total_enquiries,
                "pending_visits": pending_visits
            }
        }
    }), 200


@property_bp.route("/<id>", methods=["GET"])
def get_property_by_id(id):
    """
    Get Single Property by ID & Increment Popularity Views Count Metric
    Populates assigned Agent/Owner contact details.
    Restricts non-Approved listings from public view.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    doc = db.properties.find_one({"_id": ObjectId(id)})
    if not doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    # Approval protection: Only approved properties are visible publicly
    approval_status = str(doc.get("approval_status", "")).strip().lower()
    if approval_status != "approved":
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"success": False, "error": "Not Found", "message": "Property not found or pending approval."}), 404

    # Increment views_count for real popularity metrics
    db.properties.update_one({"_id": ObjectId(id)}, {"$inc": {"views_count": 1}})

    formatted = PropertyModel.format_property(doc)

    # Populate Agent / Owner contact information
    agent_info = None
    if doc.get("agent_id"):
        agent_doc = db.users.find_one({"_id": ObjectId(doc["agent_id"])})
        if agent_doc:
            raw_phone = agent_doc.get("phone", "")
            # Check if requester is privileged (admin or listing owner)
            is_privileged = False
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                try:
                    token = auth_header.split(" ")[1]
                    payload = decode_token(token)
                    user_id = payload.get("sub")
                    user_role = payload.get("role")
                    if user_role == "admin" or str(user_id) == str(doc.get("agent_id")):
                        is_privileged = True
                except Exception:
                    pass

            masked_phone = raw_phone
            if not is_privileged and raw_phone:
                phone_str = str(raw_phone).strip()
                if len(phone_str) > 5:
                    masked_phone = phone_str[:5] + " *****"
                else:
                    masked_phone = "••••••••••"

            agent_info = {
                "id": str(agent_doc["_id"]),
                "name": agent_doc.get("name", "Marketplace Agent"),
                "email": agent_doc.get("email", "agent@havenspace.com"),
                "phone": masked_phone,
                "role": agent_doc.get("role", "agent"),
            }

    formatted["agent"] = agent_info

    return jsonify({
        "success": True,
        "data": {
            "property": formatted
        }
    }), 200


@property_bp.route("", methods=["POST"])
@authenticate_user
@role_required("agent", "owner", "admin")
def create_property():
    """
    Create Property Endpoint
    Restricted to authenticated agents, owners, and admins.
    Automatically assigns agent_id = current user _id.
    Forces approval_status = 'Pending'.
    """
    data = request.get_json() or {}

    is_valid, err_msg, cleaned = validate_property_input(data)
    if not is_valid:
        return jsonify({"success": False, "error": "Validation Error", "message": err_msg}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    current_user_id = ObjectId(g.current_user["_id"])

    # New properties created by agents/owners are ALWAYS 'Pending' approval
    approval_status = "Pending"

    lat_input = data.get("latitude") if "latitude" in data else data.get("lat")
    lng_input = data.get("longitude") if "longitude" in data else (data.get("lng") if "lng" in data else data.get("lon"))

    prop_doc = PropertyModel.create_document(
        title=cleaned["title"],
        type_=cleaned["type"],
        description=cleaned["description"],
        transaction_type=cleaned["transaction_type"],
        price=cleaned["price"],
        location=cleaned["location"],
        address=cleaned["address"],
        area=cleaned["area"],
        bedrooms=cleaned["bedrooms"],
        bathrooms=cleaned["bathrooms"],
        parking=cleaned["parking"],
        furnishing=cleaned["furnishing"],
        images=cleaned["images"],
        agent_id=current_user_id,
        status=cleaned["status"],
        approval_status=approval_status,
        latitude=cleaned["latitude"],
        longitude=cleaned["longitude"]
    )

    result = db.properties.insert_one(prop_doc)
    prop_doc["_id"] = result.inserted_id

    formatted = PropertyModel.format_property(prop_doc)

    return jsonify({
        "success": True,
        "message": "Property listing created successfully and submitted for admin approval.",
        "data": {
            "property": formatted
        }
    }), 201


@property_bp.route("/<id>", methods=["PUT"])
@authenticate_user
@role_required("agent", "owner", "admin")
def update_property(id):
    """
    Edit Property Endpoint
    Requires ownership check or admin.
    Resets approval_status to 'Pending' when edited by an agent/owner.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    existing_prop = db.properties.find_one({"_id": ObjectId(id)})
    if not existing_prop:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    # Ownership check
    is_owner, error_resp = check_ownership(existing_prop.get("agent_id"))
    if not is_owner:
        return error_resp

    data = request.get_json() or {}
    merged_data = {
        "title": data.get("title", existing_prop.get("title")),
        "description": data.get("description", existing_prop.get("description")),
        "type": data.get("type", existing_prop.get("type")),
        "transaction_type": data.get("transaction_type", existing_prop.get("transaction_type")),
        "price": data.get("price", existing_prop.get("price")),
        "location": data.get("location", existing_prop.get("location")),
        "address": data.get("address", existing_prop.get("address")),
        "area": data.get("area", existing_prop.get("area")),
        "bedrooms": data.get("bedrooms", existing_prop.get("bedrooms")),
        "bathrooms": data.get("bathrooms", existing_prop.get("bathrooms")),
        "parking": data.get("parking", existing_prop.get("parking")),
        "furnishing": data.get("furnishing", existing_prop.get("furnishing")),
        "status": data.get("status", existing_prop.get("status")),
        "images": data.get("images", existing_prop.get("images", [])),
    }

    # Extract latitude/longitude input or fallback to existing
    if "latitude" in data or "lat" in data:
        merged_data["latitude"] = data.get("latitude") if "latitude" in data else data.get("lat")
    else:
        merged_data["latitude"] = existing_prop.get("latitude")

    if "longitude" in data or "lng" in data or "lon" in data:
        merged_data["longitude"] = data.get("longitude") if "longitude" in data else (data.get("lng") if "lng" in data else data.get("lon"))
    else:
        merged_data["longitude"] = existing_prop.get("longitude")

    is_valid, err_msg, cleaned = validate_property_input(merged_data)
    if not is_valid:
        return jsonify({"success": False, "error": "Validation Error", "message": err_msg}), 400

    # If agent/owner edits, reset approval_status to 'Pending'
    new_approval_status = existing_prop.get("approval_status", "Pending")
    if g.current_user.get("role") != "admin":
        new_approval_status = "Pending"

    now = datetime.now(timezone.utc)

    update_fields = {
        "title": cleaned["title"],
        "description": cleaned["description"],
        "type": cleaned["type"],
        "transaction_type": cleaned["transaction_type"],
        "price": cleaned["price"],
        "location": cleaned["location"],
        "address": cleaned["address"],
        "area": cleaned["area"],
        "bedrooms": cleaned["bedrooms"],
        "bathrooms": cleaned["bathrooms"],
        "parking": cleaned["parking"],
        "furnishing": cleaned["furnishing"],
        "status": cleaned["status"],
        "approval_status": new_approval_status,
        "images": cleaned["images"],
        "latitude": cleaned["latitude"],
        "longitude": cleaned["longitude"],
        "updated_at": now,
    }

    db.properties.update_one({"_id": ObjectId(id)}, {"$set": update_fields})
    updated_doc = db.properties.find_one({"_id": ObjectId(id)})

    formatted = PropertyModel.format_property(updated_doc)

    return jsonify({
        "success": True,
        "message": "Property listing updated successfully.",
        "data": {
            "property": formatted
        }
    }), 200


@property_bp.route("/<id>/status", methods=["PATCH", "PUT"])
@authenticate_user
@role_required("agent", "owner", "admin")
def update_property_status(id):
    """
    Update Property Availability & Approval Status Endpoint
    - Agent/Owner: Can update availability status (Available, Sold, Rented, Unavailable) for own property.
    - Admin: Can update availability status and approval_status (Pending, Approved, Rejected).
    - Unauthorized users or attempts by Agent to self-approve are blocked with 403.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    existing_prop = db.properties.find_one({"_id": ObjectId(id)})
    if not existing_prop:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    # Ownership check
    is_owner, error_resp = check_ownership(existing_prop.get("agent_id"))
    if not is_owner:
        return error_resp

    data = request.get_json() or {}
    user_role = g.current_user.get("role")

    updates = {}
    now = datetime.now(timezone.utc)

    # 1. Availability Status Update
    if "status" in data:
        new_status = str(data["status"]).strip()
        matched_status = next((s for s in VALID_STATUSES if s.lower() == new_status.lower()), None)
        if not matched_status:
            return jsonify({
                "success": False,
                "error": "Validation Error",
                "message": f"Invalid status '{new_status}'. Allowed: {', '.join(VALID_STATUSES)}"
            }), 400

        # Rule constraint: Only admin-approved properties can be marked as Available
        if matched_status == "Available":
            current_approval = str(existing_prop.get("approval_status", "")).strip().lower()
            requested_approval = str(data.get("approval_status", "")).strip().lower() if "approval_status" in data else current_approval
            if requested_approval != "approved":
                return jsonify({
                    "success": False,
                    "error": "Validation Error",
                    "message": "Only admin-approved properties can be marked as Available."
                }), 400

        updates["status"] = matched_status

    # 2. Approval Status Update (Admin Only)
    if "approval_status" in data:
        new_approval = str(data["approval_status"]).strip()
        matched_approval = next((a for a in VALID_APPROVAL_STATUSES if a.lower() == new_approval.lower()), None)

        if not matched_approval:
            return jsonify({
                "success": False,
                "error": "Validation Error",
                "message": f"Invalid approval_status '{new_approval}'. Allowed: {', '.join(VALID_APPROVAL_STATUSES)}"
            }), 400

        if user_role != "admin":
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "Only Administrators are authorized to modify property approval status."
            }), 403

        updates["approval_status"] = matched_approval

    if not updates:
        return jsonify({"success": False, "error": "Validation Error", "message": "No valid status fields provided for update."}), 400

    updates["updated_at"] = now

    db.properties.update_one({"_id": ObjectId(id)}, {"$set": updates})
    updated_doc = db.properties.find_one({"_id": ObjectId(id)})

    formatted = PropertyModel.format_property(updated_doc)

    # Send Notification if availability status changed
    if "status" in updates:
        agent_id = updated_doc.get("agent_id") or updated_doc.get("owner_id")
        if agent_id:
            create_notification(
                db=db,
                user_id=agent_id,
                type_str="property_status_change",
                title="Property Status Change",
                message=f"Status for '{formatted.get('title')}' changed to '{updates['status']}'.",
                related_id=updated_doc["_id"]
            )

    return jsonify({
        "success": True,
        "message": "Property status updated successfully.",
        "data": {
            "property": formatted
        }
    }), 200


@property_bp.route("/<id>", methods=["DELETE"])
@authenticate_user
@role_required("agent", "owner", "admin")
def delete_property(id):
    """
    Delete Property Endpoint
    Requires ownership check or admin.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    existing_prop = db.properties.find_one({"_id": ObjectId(id)})
    if not existing_prop:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    # Ownership check
    is_owner, error_resp = check_ownership(existing_prop.get("agent_id"))
    if not is_owner:
        return error_resp

    db.properties.delete_one({"_id": ObjectId(id)})

    return jsonify({
        "success": True,
        "message": "Property listing deleted successfully."
    }), 200
