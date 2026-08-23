"""
Domain constants and allowed value enumerations for Real Estate Marketplace collections.
"""

USER_ROLES = ["admin", "agent", "owner", "customer"]
DEFAULT_USER_ROLE = "customer"

USER_STATUSES = ["active", "inactive", "pending_verification", "pending_approval"]
DEFAULT_USER_STATUS = "active"

TRANSACTION_TYPES = ["sale", "rent", "Sale", "Rent"]
DEFAULT_TRANSACTION_TYPE = "Sale"

PROPERTY_TYPES = [
    "Apartment",
    "Villa",
    "Independent House",
    "Commercial Property",
    "Plot",
    "Office",
    "apartment",
    "villa",
    "house",
    "commercial",
    "plot",
    "office"
]
DEFAULT_PROPERTY_TYPE = "Apartment"

FURNISHING_TYPES = [
    "Unfurnished",
    "Semi-Furnished",
    "Fully Furnished",
    "unfurnished",
    "semi-furnished",
    "fully-furnished"
]
DEFAULT_FURNISHING = "Unfurnished"

PROPERTY_STATUSES = [
    "Available",
    "Sold",
    "Rented",
    "Unavailable",
    "available",
    "sold",
    "rented",
    "unavailable"
]
DEFAULT_PROPERTY_STATUS = "Available"

APPROVAL_STATUSES = [
    "Pending",
    "Approved",
    "Rejected",
    "pending",
    "approved",
    "rejected"
]
DEFAULT_APPROVAL_STATUS = "Pending"

CATEGORY_STATUSES = ["active", "inactive"]
DEFAULT_CATEGORY_STATUS = "active"

ENQUIRY_STATUSES = ["new", "contacted", "in_progress", "resolved", "closed"]
DEFAULT_ENQUIRY_STATUS = "new"

VISIT_STATUSES = ["requested", "confirmed", "rescheduled", "completed", "cancelled"]
DEFAULT_VISIT_STATUS = "requested"
