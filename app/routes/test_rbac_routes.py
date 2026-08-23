from flask import Blueprint, jsonify, g
from app.middleware import authenticate_user, role_required, check_ownership

test_rbac_bp = Blueprint("test_rbac", __name__, url_prefix="/api/test")

@test_rbac_bp.route("/admin-only", methods=["GET"])
@authenticate_user
@role_required("admin")
def admin_only_endpoint():
    return jsonify({
        "success": True,
        "message": "Welcome Admin. You have accessed an Admin-restricted resource.",
        "user": g.current_user.get("name"),
        "role": g.current_user.get("role")
    }), 200


@test_rbac_bp.route("/agent-or-owner", methods=["GET"])
@authenticate_user
@role_required("agent", "owner")
def agent_or_owner_endpoint():
    return jsonify({
        "success": True,
        "message": "Welcome Agent/Owner. You have accessed an Agent/Owner resource.",
        "user": g.current_user.get("name"),
        "role": g.current_user.get("role")
    }), 200


@test_rbac_bp.route("/customer-only", methods=["GET"])
@authenticate_user
@role_required("customer")
def customer_only_endpoint():
    return jsonify({
        "success": True,
        "message": "Welcome Customer. You have accessed a Customer resource.",
        "user": g.current_user.get("name"),
        "role": g.current_user.get("role")
    }), 200


@test_rbac_bp.route("/resource-ownership/<agent_id>", methods=["POST"])
@authenticate_user
@role_required("agent", "owner", "admin")
def test_ownership_endpoint(agent_id):
    is_owner, error_resp = check_ownership(agent_id)
    if not is_owner:
        return error_resp

    return jsonify({
        "success": True,
        "message": "Ownership check passed. Resource modification permitted.",
        "resource_agent_id": agent_id,
        "requestor_id": str(g.current_user.get("_id")),
        "requestor_role": g.current_user.get("role")
    }), 200
