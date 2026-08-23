import re
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db
from app.middleware import authenticate_user, role_required
from app.models import CategoryModel

category_bp = Blueprint("categories", __name__, url_prefix="/api/categories")


def seed_default_categories(db):
    """
    Ensure all 6 default categories exist in MongoDB collection.
    """
    from app.models import DEFAULT_CATEGORIES
    if db is None:
        return

    for cat in DEFAULT_CATEGORIES:
        escaped = re.escape(cat["name"])
        existing = db.categories.find_one({"name": {"$regex": f"^{escaped}$", "$options": "i"}})
        if not existing:
            doc = CategoryModel.create_document(
                name=cat["name"],
                description=cat["description"],
                status="active"
            )
            db.categories.insert_one(doc)
            print(f"[SEED] Seeded missing property category '{cat['name']}'.")


@category_bp.route("", methods=["GET"])
def get_categories():
    """
    Get Categories Endpoint
    Public access defaults to returning active categories only.
    Query parameters:
    - search: regex search on category name or description
    - status: 'all', 'active', 'inactive'
    - all: 'true' to include inactive categories
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    query = {}
    include_all = request.args.get("all", "false").lower() == "true"
    status_filter = request.args.get("status", "").strip().lower()
    search_term = request.args.get("search", "").strip()

    if status_filter and status_filter != "all":
        query["status"] = status_filter
    elif not include_all:
        # Default public behavior: active categories only
        query["status"] = "active"

    if search_term:
        regex = re.compile(re.escape(search_term), re.IGNORECASE)
        query["$or"] = [
            {"name": regex},
            {"description": regex}
        ]

    cursor = db.categories.find(query).sort("name", 1)
    categories = [CategoryModel.format_category(doc) for doc in cursor]

    return jsonify({
        "success": True,
        "data": {
            "categories": categories,
            "total": len(categories)
        }
    }), 200


@category_bp.route("", methods=["POST"])
@authenticate_user
@role_required("admin")
def create_category():
    """
    Create Category Endpoint (Admin only)
    Validates name uniqueness (case-insensitive).
    """
    data = request.get_json() or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    status = str(data.get("status", "active")).strip().lower()

    if not name:
        return jsonify({"success": False, "error": "Validation Error", "message": "Category name is required."}), 400

    if status not in ["active", "inactive"]:
        status = "active"

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    # Duplicate name check
    escaped_name = re.escape(name)
    existing = db.categories.find_one({"name": {"$regex": f"^{escaped_name}$", "$options": "i"}})
    if existing:
        return jsonify({
            "success": False,
            "error": "Conflict",
            "message": f"A category with the name '{name}' already exists."
        }), 400

    cat_doc = CategoryModel.create_document(name=name, description=description, status=status)
    result = db.categories.insert_one(cat_doc)
    cat_doc["_id"] = result.inserted_id

    formatted = CategoryModel.format_category(cat_doc)

    return jsonify({
        "success": True,
        "message": "Category created successfully.",
        "data": {
            "category": formatted
        }
    }), 201


@category_bp.route("/<id>", methods=["PUT"])
@authenticate_user
@role_required("admin")
def update_category(id):
    """
    Edit Category Endpoint (Admin only)
    Allows updating name, description, status.
    Prevents duplicate names.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Category not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    existing_cat = db.categories.find_one({"_id": ObjectId(id)})
    if not existing_cat:
        return jsonify({"success": False, "error": "Not Found", "message": "Category not found."}), 404

    data = request.get_json() or {}
    name = str(data.get("name", existing_cat.get("name"))).strip()
    description = str(data.get("description", existing_cat.get("description", ""))).strip()
    status = str(data.get("status", existing_cat.get("status", "active"))).strip().lower()

    if not name:
        return jsonify({"success": False, "error": "Validation Error", "message": "Category name is required."}), 400

    if status not in ["active", "inactive"]:
        status = existing_cat.get("status", "active")

    # Duplicate name check if name modified
    if name.lower() != existing_cat.get("name", "").lower():
        escaped_name = re.escape(name)
        duplicate = db.categories.find_one({
            "_id": {"$ne": ObjectId(id)},
            "name": {"$regex": f"^{escaped_name}$", "$options": "i"}
        })
        if duplicate:
            return jsonify({
                "success": False,
                "error": "Conflict",
                "message": f"A category with the name '{name}' already exists."
            }), 400

    now = datetime.now(timezone.utc)
    update_fields = {
        "name": name,
        "description": description,
        "status": status,
        "updated_at": now
    }

    db.categories.update_one({"_id": ObjectId(id)}, {"$set": update_fields})
    updated_doc = db.categories.find_one({"_id": ObjectId(id)})

    formatted = CategoryModel.format_category(updated_doc)

    return jsonify({
        "success": True,
        "message": "Category updated successfully.",
        "data": {
            "category": formatted
        }
    }), 200


@category_bp.route("/<id>", methods=["DELETE"])
@authenticate_user
@role_required("admin")
def delete_category(id):
    """
    Delete Category Endpoint (Admin only)
    Prevents deletion if category name is used by active properties.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Category not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    existing_cat = db.categories.find_one({"_id": ObjectId(id)})
    if not existing_cat:
        return jsonify({"success": False, "error": "Not Found", "message": "Category not found."}), 404

    cat_name = existing_cat.get("name", "")
    escaped_name = re.escape(cat_name)

    # Check if any property uses this category name as its 'type'
    usage_count = db.properties.count_documents({"type": {"$regex": f"^{escaped_name}$", "$options": "i"}})
    if usage_count > 0:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": f"Cannot delete category '{cat_name}' because it is currently assigned to {usage_count} property listing(s). Please deactivate it instead."
        }), 400

    db.categories.delete_one({"_id": ObjectId(id)})

    return jsonify({
        "success": True,
        "message": f"Category '{cat_name}' deleted successfully."
    }), 200
