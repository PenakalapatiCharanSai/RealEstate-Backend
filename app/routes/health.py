from flask import Blueprint, jsonify, request
from app.services.notification_service import send_welcome_email
from app.services.email_service import send_email

health_bp = Blueprint("health", __name__)

@health_bp.route("/api/health", methods=["GET"])
def health_check():
    """
    Health check endpoint to verify API server status.
    """
    return jsonify({
        "success": True,
        "message": "Real Estate Marketplace API is running"
    }), 200


@health_bp.route("/api/test/test-email", methods=["GET", "POST"])
def test_email_endpoint():
    """
    Development & Admin Test Email Endpoint using Resend.
    """
    target_email = request.args.get("email") or request.json.get("email") if request.is_json else None
    if not target_email:
        target_email = "customer@havenspace.in"

    result = send_welcome_email(target_email, "Test User", "customer")

    if result.get("success"):
        return jsonify({
            "success": True,
            "message": "Test email sent successfully",
            "data": result.get("data")
        }), 200
    else:
        return jsonify({
            "success": False,
            "message": f"Failed to send test email: {result.get('error') or result.get('message')}"
        }), 400
