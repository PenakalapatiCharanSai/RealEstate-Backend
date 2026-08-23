from functools import wraps
from flask import jsonify, g

def role_required(*allowed_roles):
    """
    Decorator middleware for role-based authorization.
    Supports single or multiple allowed roles:
      @role_required("admin")
      @role_required("agent", "owner")
    Must be stacked after @authenticate_user decorator.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(g, "current_user") or not g.current_user:
                return jsonify({
                    "success": False,
                    "error": "Unauthorized",
                    "message": "Authentication required before checking role authorization."
                }), 401

            user_role = g.current_user.get("role")

            if user_role not in allowed_roles:
                allowed_str = ", ".join(allowed_roles)
                return jsonify({
                    "success": False,
                    "error": "Forbidden",
                    "message": f"Access denied. Requires role: [{allowed_str}]. Current role: '{user_role}'."
                }), 403

            return f(*args, **kwargs)
        return decorated
    return decorator


def check_ownership(resource_agent_id):
    """
    Helper function to enforce resource ownership security.
    Rules:
    - Admin users are granted platform-wide management access to any resource.
    - Agents/Owners can only access/modify resources where resource_agent_id matches their own user _id.
    
    Returns:
      (is_authorized: bool, error_response_tuple: tuple | None)
    """
    if not hasattr(g, "current_user") or not g.current_user:
        return False, (jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": "Authentication required."
        }), 401)

    user_role = g.current_user.get("role")
    user_id = str(g.current_user.get("_id"))

    # Admin bypasses individual resource ownership checks
    if user_role == "admin":
        return True, None

    # Check matching agent/owner user id
    if str(resource_agent_id) == user_id:
        return True, None

    # Access denied for another user's resource
    return False, (jsonify({
        "success": False,
        "error": "Forbidden",
        "message": "Access denied. You do not have permission to modify another user's property/resource."
    }), 403)
