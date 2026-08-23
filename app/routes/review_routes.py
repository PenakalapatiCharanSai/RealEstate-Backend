from flask import Blueprint, request, jsonify, g
from bson import ObjectId
from datetime import datetime, timezone
from app.utils.db import get_db
from app.middleware.auth_middleware import authenticate_user
from app.models.review import ReviewModel

review_bp = Blueprint("review", __name__, url_prefix="/api/reviews")

@review_bp.route("", methods=["POST"])
@authenticate_user
def create_review():
    """
    Submit Agent Review
    Allowed for customers after an interaction (enquiry or visit).
    Prevents self-reviews and duplicate reviews.
    """
    data = request.get_json() or {}
    agent_id_str = data.get("agent_id")
    property_id_str = data.get("property_id")
    rating_raw = data.get("rating")
    review_text = str(data.get("review", "")).strip()

    if not agent_id_str or not ObjectId.is_valid(agent_id_str):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid agent_id is required."}), 400

    # Validate rating
    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": "Rating must be an integer between 1 and 5."
        }), 400

    if not review_text:
        return jsonify({"success": False, "error": "Validation Error", "message": "Review message text is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    current_user_id = str(g.current_user["_id"])

    # Prevent self review
    if current_user_id == str(agent_id_str):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "You cannot submit a review for yourself."
        }), 403

    # Check agent exists
    agent_doc = db.users.find_one({"_id": ObjectId(agent_id_str)})
    if not agent_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Target agent record not found."}), 404

    cust_oid = ObjectId(current_user_id)
    agent_oid = ObjectId(agent_id_str)
    prop_oid = ObjectId(property_id_str) if property_id_str and ObjectId.is_valid(property_id_str) else None

    # Check for meaningful interaction (enquiry or visit booking)
    has_enquiry = db.enquiries.find_one({
        "customer_id": cust_oid,
        "$or": [{"agent_id": agent_oid}] + ([{"property_id": prop_oid}] if prop_oid else [])
    })

    has_visit = db.visits.find_one({
        "customer_id": cust_oid,
        "$or": [{"agent_id": agent_oid}] + ([{"property_id": prop_oid}] if prop_oid else [])
    })

    if not (has_enquiry or has_visit):
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": "You can only review an agent after making an enquiry or scheduling a site visit."
        }), 400

    # Prevent duplicate review for same agent
    duplicate_query = {"customer_id": cust_oid, "agent_id": agent_oid}
    if prop_oid:
        duplicate_query["property_id"] = prop_oid

    existing_review = db.reviews.find_one(duplicate_query)
    if existing_review:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": "You have already submitted a review for this agent interaction."
        }), 400

    review_doc = ReviewModel.create_document(
        customer_id=cust_oid,
        agent_id=agent_oid,
        rating=rating,
        review=review_text,
        property_id=prop_oid
    )

    result = db.reviews.insert_one(review_doc)
    review_doc["_id"] = result.inserted_id

    # Format result with customer info
    cust_map = {current_user_id: {"name": g.current_user.get("name"), "email": g.current_user.get("email")}}
    agent_map = {agent_id_str: {"name": agent_doc.get("name"), "email": agent_doc.get("email")}}
    formatted = ReviewModel.format_review(review_doc, customer_map=cust_map, agent_map=agent_map)

    return jsonify({
        "success": True,
        "message": "Agent review submitted successfully.",
        "data": {
            "review": formatted
        }
    }), 201


@review_bp.route("/agent/<agent_id>", methods=["GET"])
def get_agent_reviews(agent_id):
    """
    Get Agent Reviews and Rating Summary
    Publicly accessible endpoint.
    """
    if not agent_id or not ObjectId.is_valid(agent_id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid agent_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    agent_oid = ObjectId(agent_id)
    reviews_list = list(db.reviews.find({"agent_id": agent_oid}).sort("created_at", -1))

    total_reviews = len(reviews_list)

    if total_reviews == 0:
        return jsonify({
            "success": True,
            "data": {
                "average_rating": 0.0,
                "total_reviews": 0,
                "rating_breakdown": {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0},
                "reviews": []
            }
        }), 200

    total_score = sum([r.get("rating", 5) for r in reviews_list])
    average_rating = round(total_score / total_reviews, 1)

    breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for r in reviews_list:
        score_str = str(r.get("rating", 5))
        if score_str in breakdown:
            breakdown[score_str] += 1

    # Populate customer names
    cust_ids = list(set([r["customer_id"] for r in reviews_list if r.get("customer_id")]))
    cust_cursor = db.users.find({"_id": {"$in": cust_ids}})
    cust_map = {str(u["_id"]): {"name": u.get("name"), "email": u.get("email")} for u in cust_cursor}

    formatted_reviews = [ReviewModel.format_review(r, customer_map=cust_map) for r in reviews_list]

    return jsonify({
        "success": True,
        "data": {
            "average_rating": average_rating,
            "total_reviews": total_reviews,
            "rating_breakdown": breakdown,
            "reviews": formatted_reviews
        }
    }), 200


@review_bp.route("/my-reviews", methods=["GET"])
@authenticate_user
def get_my_reviews():
    """
    Get My Reviews
    Returns reviews written by customer or received by agent/owner.
    """
    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user = g.current_user
    user_id = str(user["_id"])
    role = user.get("role", "customer").lower()

    if role in ["agent", "owner"]:
        query = {"agent_id": ObjectId(user_id)}
    else:
        query = {"customer_id": ObjectId(user_id)}

    reviews_list = list(db.reviews.find(query).sort("created_at", -1))

    # Populate users
    cust_ids = list(set([r["customer_id"] for r in reviews_list if r.get("customer_id")]))
    agent_ids = list(set([r["agent_id"] for r in reviews_list if r.get("agent_id")]))
    all_user_ids = list(set(cust_ids + agent_ids))

    users_cursor = db.users.find({"_id": {"$in": all_user_ids}})
    user_map = {str(u["_id"]): {"name": u.get("name"), "email": u.get("email")} for u in users_cursor}

    formatted = [ReviewModel.format_review(r, customer_map=user_map, agent_map=user_map) for r in reviews_list]

    return jsonify({
        "success": True,
        "data": {
            "reviews": formatted,
            "total": len(formatted)
        }
    }), 200


@review_bp.route("/<id>", methods=["DELETE"])
@authenticate_user
def delete_review(id):
    """
    Delete / Moderate Review
    Allowed for author customer or Admin.
    """
    if not id or not ObjectId.is_valid(id):
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid review_id is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    review_doc = db.reviews.find_one({"_id": ObjectId(id)})
    if not review_doc:
        return jsonify({"success": False, "error": "Not Found", "message": "Review not found."}), 404

    user = g.current_user
    user_id = str(user["_id"])
    role = user.get("role", "customer").lower()

    is_author = str(review_doc.get("customer_id")) == user_id
    is_admin = role == "admin"

    if not (is_author or is_admin):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "Only the author of the review or an admin can delete this review."
        }), 403

    db.reviews.delete_one({"_id": ObjectId(id)})

    return jsonify({
        "success": True,
        "message": "Review deleted successfully."
    }), 200
