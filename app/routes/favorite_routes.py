from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db
from app.models.favorite import FavoriteModel
from app.models.property import PropertyModel
from app.middleware.auth_middleware import authenticate_user

favorite_bp = Blueprint("favorite", __name__, url_prefix="/api/favorites")


@favorite_bp.route("", methods=["GET"])
@authenticate_user
def get_favorites():
    """
    Get Logged-in Customer Favorites List
    Returns populated approved property objects.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    customer_id = ObjectId(g.current_user["_id"])
    cursor = db.favorites.find({"customer_id": customer_id}).sort("created_at", -1)
    favorite_docs = list(cursor)

    if not favorite_docs:
        return jsonify({
            "success": True,
            "data": {
                "favorites": [],
                "total": 0
            }
        }), 200

    property_ids = [doc["property_id"] for doc in favorite_docs if doc.get("property_id")]
    
    # Query approved properties matching favorited IDs
    prop_cursor = db.properties.find({"_id": {"$in": property_ids}, "approval_status": "Approved"})
    prop_map = {str(p["_id"]): PropertyModel.format_property(p) for p in prop_cursor}

    # Maintain created_at order from favorites collection
    formatted_favorites = []
    for f in favorite_docs:
        pid_str = str(f["property_id"])
        if pid_str in prop_map:
            formatted_favorites.append(prop_map[pid_str])

    return jsonify({
        "success": True,
        "data": {
            "favorites": formatted_favorites,
            "total": len(formatted_favorites)
        }
    }), 200


@favorite_bp.route("", methods=["POST"])
@authenticate_user
def add_favorite():
    """
    Add Property to Logged-in Customer Favorites List
    Enforces uniqueness per customer & increments property favorites metric.
    """
    data = request.get_json() or {}
    property_id = data.get("property_id") or data.get("propertyId")

    if not property_id or not ObjectId.is_valid(property_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid property_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    prop_obj_id = ObjectId(property_id)

    # Verify property exists and is approved
    prop_doc = db.properties.find_one({"_id": prop_obj_id, "approval_status": "Approved"})
    if not prop_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Approved property not found."}), 404

    customer_id = ObjectId(g.current_user["_id"])

    # Check for duplicate favorite document
    existing = db.favorites.find_one({"customer_id": customer_id, "property_id": prop_obj_id})
    if existing:
        return jsonify({"success": False, "error": "Conflict", "message": "Property is already in your favorites list."}), 400

    # Insert Favorite record
    fav_doc = FavoriteModel.create_document(customer_id, prop_obj_id)
    db.favorites.insert_one(fav_doc)

    # Increment property favorites_count metric for popularity sorting
    db.properties.update_one({"_id": prop_obj_id}, {"$inc": {"favorites_count": 1}})

    return jsonify({
        "success": True,
        "message": "Property added to favorites successfully.",
        "data": {
            "property_id": str(prop_obj_id)
        }
    }), 201


@favorite_bp.route("/<property_id>", methods=["DELETE"])
@authenticate_user
def remove_favorite(property_id):
    """
    Remove Property from Customer Favorites List
    Restricted to logged-in customer's own favorites.
    """
    if not property_id or not ObjectId.is_valid(property_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid property_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    customer_id = ObjectId(g.current_user["_id"])
    prop_obj_id = ObjectId(property_id)

    # Delete favorite record belonging to logged-in user
    deleted = db.favorites.find_one_and_delete({"customer_id": customer_id, "property_id": prop_obj_id})

    if not deleted:
        return jsonify({"success": False, "error": "Not Found", "message": "Favorite record not found for this customer."}), 404

    # Decrement property favorites_count metric
    db.properties.update_one({"_id": prop_obj_id, "favorites_count": {"$gt": 0}}, {"$inc": {"favorites_count": -1}})

    return jsonify({
        "success": True,
        "message": "Property removed from favorites successfully.",
        "data": {
            "property_id": str(prop_obj_id)
        }
    }), 200
