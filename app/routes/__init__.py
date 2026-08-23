from .health import health_bp
from .test_rbac_routes import test_rbac_bp
from .auth_routes import auth_bp
from .property_routes import property_bp
from .category_routes import category_bp, seed_default_categories
from .image_routes import image_bp
from .admin_routes import admin_bp
from .favorite_routes import favorite_bp
from .enquiry_routes import enquiry_bp
from .visit_routes import visit_bp
from .notification_routes import notification_bp
from .review_routes import review_bp

__all__ = [
    "health_bp",
    "test_rbac_bp",
    "auth_bp",
    "property_bp",
    "category_bp",
    "image_bp",
    "admin_bp",
    "favorite_bp",
    "enquiry_bp",
    "visit_bp",
    "notification_bp",
    "review_bp",
    "seed_default_categories",
]
