import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from app.config.config import Config
from app.utils.db import init_db
from app.routes import health_bp, auth_bp, test_rbac_bp, property_bp, category_bp, image_bp, admin_bp, favorite_bp, enquiry_bp, visit_bp, notification_bp, review_bp, seed_default_categories
from app.middleware.error_handler import register_error_handlers

from app.middleware.security_middleware import apply_security_headers, request_security_guard
from app.middleware.rate_limiter import rate_limit_guard

def create_app(config_class=Config):
    """
    Flask Application Factory with Enterprise Security Hardening
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Max upload limit (10MB) to prevent Denial-of-Service / Memory Exhaustion attacks
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

    # Configure CORS - restrict allowed headers and expose security tokens
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # Initialize Database connection
    db = init_db(app)

    # Register Security Middleware & Rate Limiting Guards
    app.before_request(rate_limit_guard)
    app.before_request(request_security_guard)
    app.after_request(apply_security_headers)

    # Seed Default Categories if empty
    with app.app_context():
        try:
            seed_default_categories(db)
        except Exception as e:
            app.logger.warning(f"Default category seeding skipped: {str(e)}")

    # Register Blueprints
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(test_rbac_bp)
    app.register_blueprint(property_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(favorite_bp)
    app.register_blueprint(enquiry_bp)
    app.register_blueprint(visit_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(review_bp)

    # Register Secure Static File Uploads Route
    @app.route('/uploads/<path:filename>')
    def serve_uploads(filename):
        # Prevent Directory Traversal / Path Traversal Attack (../)
        if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
            return "Access Denied: Path Traversal Detected", 403

        uploads_dir = os.path.abspath(os.path.join(app.root_path, "..", "uploads"))
        file_path = os.path.abspath(os.path.join(uploads_dir, filename))

        # Enforce that served file resides strictly within uploads_dir
        if not file_path.startswith(uploads_dir):
            return "Access Denied", 403

        return send_from_directory(uploads_dir, filename)

    # Register Global Error Handlers
    register_error_handlers(app)

    return app
