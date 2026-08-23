from functools import wraps
from flask import request, jsonify, g
from bson import ObjectId
from app.utils.jwt_utils import decode_token
from app.utils.db import get_db
from app.models import UserModel

def authenticate_user(f):
    """
    Decorator middleware to protect endpoints.
    Validates JWT token in 'Authorization: Bearer <token>' header and attaches user document to g.current_user.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": "Authentication token is missing."
            }), 401

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": "Invalid Authorization header format. Expected 'Bearer <token>'."
            }), 401

        token = parts[1]

        try:
            payload = decode_token(token)
            user_id = payload.get("sub")

            if not user_id or not ObjectId.is_valid(user_id):
                return jsonify({
                    "success": False,
                    "error": "Unauthorized",
                    "message": "Invalid token subject payload."
                }), 401

            db = get_db()
            if db is None:
                return jsonify({
                    "success": False,
                    "error": "Database Error",
                    "message": "Database connection unavailable."
                }), 500

            user = db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                return jsonify({
                    "success": False,
                    "error": "Unauthorized",
                    "message": "User account no longer exists."
                }), 401

            if user.get("status") != "active":
                return jsonify({
                    "success": False,
                    "error": "Forbidden",
                    "message": "User account is inactive or suspended."
                }), 403

            # Attach authenticated user to Flask global request context g
            g.current_user = user
            g.user_id = str(user["_id"])
            g.user_role = user.get("role")

        except ValueError as ve:
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": str(ve)
            }), 401
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": "Authentication failed."
            }), 401

        return f(*args, **kwargs)

    return decorated
