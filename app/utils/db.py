import logging
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from app.config.config import Config

logger = logging.getLogger(__name__)

def create_db_indexes(db):
    """
    Configure and create all required MongoDB collection indexes.
    
    1. users: email unique index
    2. properties: location, type, transaction_type, price, bedrooms, furnishing, approval_status, agent_id, created_at
    3. favorites: unique compound index on (customer_id, property_id)
    4. enquiries: customer_id, property_id, agent_id, status
    5. visits: customer_id, property_id, agent_id, status
    """
    if db is None:
        logger.warning("Skipping index creation: Database instance is None.")
        return False

    try:
        # 1. users collection indexes
        db.users.create_index([("email", ASCENDING)], unique=True, name="idx_users_email_unique")

        # 2. properties collection indexes
        db.properties.create_index([("location", ASCENDING)], name="idx_properties_location")
        db.properties.create_index([("type", ASCENDING)], name="idx_properties_type")
        db.properties.create_index([("transaction_type", ASCENDING)], name="idx_properties_transaction_type")
        db.properties.create_index([("price", ASCENDING)], name="idx_properties_price")
        db.properties.create_index([("bedrooms", ASCENDING)], name="idx_properties_bedrooms")
        db.properties.create_index([("furnishing", ASCENDING)], name="idx_properties_furnishing")
        db.properties.create_index([("approval_status", ASCENDING)], name="idx_properties_approval_status")
        db.properties.create_index([("agent_id", ASCENDING)], name="idx_properties_agent_id")
        db.properties.create_index([("created_at", DESCENDING)], name="idx_properties_created_at")

        # 3. favorites collection index (unique compound index customer_id + property_id)
        db.favorites.create_index(
            [("customer_id", ASCENDING), ("property_id", ASCENDING)],
            unique=True,
            name="idx_favorites_customer_property_unique"
        )

        # 4. enquiries collection indexes
        db.enquiries.create_index([("customer_id", ASCENDING)], name="idx_enquiries_customer_id")
        db.enquiries.create_index([("property_id", ASCENDING)], name="idx_enquiries_property_id")
        db.enquiries.create_index([("agent_id", ASCENDING)], name="idx_enquiries_agent_id")
        db.enquiries.create_index([("status", ASCENDING)], name="idx_enquiries_status")

        # 5. visits collection indexes
        db.visits.create_index([("customer_id", ASCENDING)], name="idx_visits_customer_id")
        db.visits.create_index([("property_id", ASCENDING)], name="idx_visits_property_id")
        db.visits.create_index([("agent_id", ASCENDING)], name="idx_visits_agent_id")
        db.visits.create_index([("status", ASCENDING)], name="idx_visits_status")

        # 6. chat_conversations collection indexes
        db.chat_conversations.create_index([("user_id", ASCENDING)], name="idx_chat_user_id")
        db.chat_conversations.create_index([("conversation_id", ASCENDING)], unique=True, name="idx_chat_conversation_id_unique")
        db.chat_conversations.create_index([("updated_at", DESCENDING)], name="idx_chat_updated_at")

        logger.info("Successfully configured all MongoDB collection indexes.")
        return True

    except Exception as e:
        logger.error(f"Error creating database indexes: {e}")
        return False

class MongoManager:
    _client = None
    _db = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            try:
                cls._client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=2000)
                cls._client.admin.command('ping')
                logger.info("Successfully connected to MongoDB database.")
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.warning(f"MongoDB connection warning: Could not ping database at {Config.MONGO_URI}. Details: {e}")
            except Exception as e:
                logger.error(f"Unexpected MongoDB connection error: {e}")
        return cls._client

    @classmethod
    def get_db(cls):
        if cls._db is None:
            client = cls.get_client()
            if client:
                db_name = Config.MONGO_URI.split('/')[-1].split('?')[0] or 'real_estate_db'
                cls._db = client[db_name]
        return cls._db

def get_db():
    return MongoManager.get_db()

def init_db(app):
    """
    Initialize database connection for the Flask application lifecycle.
    """
    app.config["MONGO_URI"] = Config.MONGO_URI
    with app.app_context():
        db = MongoManager.get_db()
        if db is not None:
            try:
                create_db_indexes(db)
            except Exception as e:
                logger.warning(f"Index initialization warning: {e}")
