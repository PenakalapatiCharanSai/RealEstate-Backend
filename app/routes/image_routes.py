from datetime import datetime, timezone
from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from app.utils.db import get_db
from app.middleware import authenticate_user, role_required, check_ownership
from app.models import PropertyModel, PropertyImageModel
from app.utils import validate_image_file, save_image_file, delete_storage_image

image_bp = Blueprint("property_images", __name__, url_prefix="/api/properties")

@image_bp.route("/<id>/images", methods=["POST"])
@authenticate_user
@role_required("agent", "owner", "admin")
def upload_property_images(id):
    """
    Upload Multiple Property Images Endpoint
    Accepts multipart/form-data with 'images' files array.
    Validates file extensions & size limit (max 5MB per file).
    Restricted to property owner or admin.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    property_doc = db.properties.find_one({"_id": ObjectId(id)})
    if not property_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    # Ownership check
    is_owner, error_resp = check_ownership(property_doc.get("agent_id"))
    if not is_owner:
        return error_resp

    # Extract files from request
    files = request.files.getlist("images")
    if not files or len(files) == 0:
        return jsonify({"success": False, "error": "Validation Error", "message": "No image files provided for upload."}), 400

    uploaded_records = []
    new_urls = []
    now = datetime.now(timezone.utc)

    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue

        # Validate file format and size
        is_valid, err_msg = validate_image_file(file_storage)
        if not is_valid:
            return jsonify({"success": False, "error": "Validation Error", "message": err_msg}), 400

        # Upload image using storage provider
        image_info = save_image_file(file_storage, upload_folder="properties")

        img_doc = PropertyImageModel.create_document(
            property_id=ObjectId(id),
            url=image_info["url"],
            public_id=image_info["public_id"]
        )
        img_doc["provider"] = image_info["provider"]

        result = db.property_images.insert_one(img_doc)
        img_doc["_id"] = result.inserted_id

        uploaded_records.append(PropertyImageModel.format_image(img_doc))
        new_urls.append(image_info["url"])

    if not uploaded_records:
        return jsonify({"success": False, "error": "Validation Error", "message": "No valid image files were uploaded."}), 400

    # Update property images array in MongoDB
    db.properties.update_one(
        {"_id": ObjectId(id)},
        {
            "$push": {"images": {"$each": new_urls}},
            "$set": {"updated_at": now}
        }
    )

    updated_property = db.properties.find_one({"_id": ObjectId(id)})
    formatted_prop = PropertyModel.format_property(updated_property)

    return jsonify({
        "success": True,
        "message": f"Successfully uploaded {len(uploaded_records)} image(s).",
        "data": {
            "images": uploaded_records,
            "property": formatted_prop
        }
    }), 201


@image_bp.route("/<id>/images", methods=["GET"])
def get_property_images(id):
    """
    Get Property Images Endpoint
    Returns list of property image records.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    cursor = db.property_images.find({"property_id": ObjectId(id)}).sort("created_at", -1)
    images = [PropertyImageModel.format_image(doc) for doc in cursor]

    return jsonify({
        "success": True,
        "data": {
            "images": images,
            "total": len(images)
        }
    }), 200


@image_bp.route("/<id>/images/<image_ref>", methods=["DELETE"])
@authenticate_user
@role_required("agent", "owner", "admin")
def delete_property_image(id, image_ref):
    """
    Delete Property Image Endpoint
    image_ref can be the property_images document _id or an image URL / index.
    Restricted to property owner or admin.
    """
    if not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    property_doc = db.properties.find_one({"_id": ObjectId(id)})
    if not property_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Property not found."}), 404

    # Ownership check
    is_owner, error_resp = check_ownership(property_doc.get("agent_id"))
    if not is_owner:
        return error_resp

    target_image_doc = None
    target_url = None

    # Check if image_ref is ObjectId
    if ObjectId.is_valid(image_ref):
        target_image_doc = db.property_images.find_one({
            "_id": ObjectId(image_ref),
            "property_id": ObjectId(id)
        })

    if target_image_doc:
        target_url = target_image_doc.get("url")
        db.property_images.delete_one({"_id": target_image_doc["_id"]})
        delete_storage_image(
            target_image_doc.get("public_id"),
            provider=target_image_doc.get("provider", "local")
        )
    else:
        # Check by matching image URL in property.images array
        current_images = property_doc.get("images", [])
        matched = [url for url in current_images if image_ref in url]
        if matched:
            target_url = matched[0]
            # Delete corresponding doc if exists
            img_doc = db.property_images.find_one({"property_id": ObjectId(id), "url": target_url})
            if img_doc:
                db.property_images.delete_one({"_id": img_doc["_id"]})
                delete_storage_image(img_doc.get("public_id"), provider=img_doc.get("provider", "local"))

    if not target_url:
        return jsonify({"success": False, "error": "Not Found", "message": "Image reference not found for this property."}), 404

    now = datetime.now(timezone.utc)

    # Remove URL from property images array
    db.properties.update_one(
        {"_id": ObjectId(id)},
        {
            "$pull": {"images": target_url},
            "$set": {"updated_at": now}
        }
    )

    updated_property = db.properties.find_one({"_id": ObjectId(id)})
    formatted_prop = PropertyModel.format_property(updated_property)

    return jsonify({
        "success": True,
        "message": "Property image deleted successfully.",
        "data": {
            "property": formatted_prop
        }
    }), 200
