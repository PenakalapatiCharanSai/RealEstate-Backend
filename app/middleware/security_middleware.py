import re
from flask import request, jsonify

# Blacklisted NoSQL Mongo Operator Patterns used in injection attacks
NOSQL_OPERATOR_PATTERN = re.compile(r"^\$")

def sanitize_payload(data):
    """
    Recursively inspects and sanitizes JSON request payloads to protect against
    MongoDB NoSQL Injection attacks (e.g., {"email": {"$ne": None}}).
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Block keys starting with $ or containing MongoDB operators
            if isinstance(key, str) and NOSQL_OPERATOR_PATTERN.match(key):
                raise ValueError(f"Security Alert: Malicious key '{key}' detected.")
            sanitized[key] = sanitize_payload(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_payload(item) for item in data]
    return data

def apply_security_headers(response):
    """
    Applies OWASP Recommended HTTP Security Headers to every HTTP response.
    Protects against XSS, Clickjacking, MIME-sniffing, and Information Disclosure.
    """
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent Clickjacking by restricting framing to same origin
    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    # Enable browser Cross-Site Scripting (XSS) filtering
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Enforce HTTPS HSTS
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Restrict Referrer leakage
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Restrict Browser Hardware Access
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"

    # Obfuscate Server Signature Header
    response.headers["Server"] = "HavenSpace Secure Engine"

    return response

def request_security_guard():
    """
    Before-request security hook to validate request headers and payload safety.
    """
    if request.is_json and request.get_data():
        try:
            payload = request.get_json(silent=True)
            if payload is not None:
                sanitize_payload(payload)
        except ValueError as ve:
            return jsonify({
                "success": False,
                "error": "Security Violation",
                "message": str(ve)
            }), 400
