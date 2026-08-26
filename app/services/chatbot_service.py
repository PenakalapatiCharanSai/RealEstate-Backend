import re
import logging
from datetime import datetime, timezone
from bson import ObjectId
from app.utils.db import get_db
from app.models.property import PropertyModel
from app.models.chat import ChatConversationModel
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)

# Allowed whitelist fields for MongoDB search filter
ALLOWED_SEARCH_FIELDS = {
    "city", "locality", "property_type", "transaction_type",
    "min_price", "max_price", "bedrooms", "bathrooms",
    "min_area", "max_area", "furnishing", "amenities", "facing", "status"
}


def build_mongo_property_query(intent: dict, raw_user_message: str) -> dict:
    """
    Constructs a hardened, controlled MongoDB query dict with whitelisted fields.
    Prevents NoSQL injection and enforces approval_status='Approved'.
    """
    query = {
        "approval_status": "Approved"
    }

    # Status filter (default to 'Available')
    status_val = intent.get("status")
    if status_val:
        query["status"] = {"$regex": f"^{re.escape(str(status_val))}$", "$options": "i"}
    else:
        query["status"] = "Available"

    # Location / City / Locality search
    city = intent.get("city")
    locality = intent.get("locality")
    location_terms = []
    if city:
        location_terms.append(re.escape(str(city).strip()))
    if locality:
        location_terms.append(re.escape(str(locality).strip()))

    if location_terms:
        # Regex matching location or address
        loc_pattern = "|".join(location_terms)
        query["$or"] = [
            {"location": {"$regex": loc_pattern, "$options": "i"}},
            {"address": {"$regex": loc_pattern, "$options": "i"}}
        ]

    # Property Type (Apartment, Villa, Independent House, Commercial Property, Plot, Office)
    prop_type = intent.get("property_type")
    if prop_type:
        query["type"] = {"$regex": f"^{re.escape(str(prop_type))}$", "$options": "i"}

    # Transaction Type (Sale or Rent)
    tx_type = intent.get("transaction_type")
    if tx_type:
        query["transaction_type"] = {"$regex": f"^{re.escape(str(tx_type))}$", "$options": "i"}

    # Price range
    min_price = intent.get("min_price")
    max_price = intent.get("max_price")
    if min_price is not None or max_price is not None:
        price_query = {}
        if min_price is not None:
            try:
                price_query["$gte"] = float(min_price)
            except (ValueError, TypeError):
                pass
        if max_price is not None:
            try:
                price_query["$lte"] = float(max_price)
            except (ValueError, TypeError):
                pass
        if price_query:
            query["price"] = price_query

    # Bedrooms
    bedrooms = intent.get("bedrooms")
    if bedrooms is not None:
        try:
            query["bedrooms"] = int(bedrooms)
        except (ValueError, TypeError):
            pass

    # Bathrooms
    bathrooms = intent.get("bathrooms")
    if bathrooms is not None:
        try:
            query["bathrooms"] = int(bathrooms)
        except (ValueError, TypeError):
            pass

    # Area
    min_area = intent.get("min_area")
    max_area = intent.get("max_area")
    if min_area is not None or max_area is not None:
        area_query = {}
        if min_area is not None:
            try:
                area_query["$gte"] = float(min_area)
            except (ValueError, TypeError):
                pass
        if max_area is not None:
            try:
                area_query["$lte"] = float(max_area)
            except (ValueError, TypeError):
                pass
        if area_query:
            query["area"] = area_query

    # Furnishing
    furnishing = intent.get("furnishing")
    if furnishing:
        query["furnishing"] = {"$regex": re.escape(str(furnishing)), "$options": "i"}

    # Amenities search (e.g. swimming pool, parking, garden)
    amenities = intent.get("amenities")
    if amenities and isinstance(amenities, list):
        for am in amenities:
            am_clean = str(am).strip()
            if am_clean:
                # Search description or address for amenity keyword
                amenity_regex = {"$regex": re.escape(am_clean), "$options": "i"}
                if "$and" not in query:
                    query["$and"] = []
                query["$and"].append({
                    "$or": [
                        {"description": amenity_regex},
                        {"title": amenity_regex}
                    ]
                })

    # Direct query string text check if no location was captured but user mentioned a place in raw text
    msg_lower = raw_user_message.lower()
    if not location_terms:
        # Fallback check for prominent cities in text
        for known_city in ["hyderabad", "bangalore", "mumbai", "pune", "delhi", "chennai", "gachibowli", "kukatpally", "jubilee hills", "indiranagar", "whitefield", "worli", "koregaon park", "hitech city"]:
            if known_city in msg_lower:
                if "$or" not in query:
                    query["$or"] = [
                        {"location": {"$regex": known_city, "$options": "i"}},
                        {"address": {"$regex": known_city, "$options": "i"}}
                    ]
                break

    return query


def execute_property_search(query: dict, limit: int = 5) -> list:
    """
    Executes controlled query on `db.properties` and formats results.
    """
    db = get_db()
    if db is None:
        return []

    try:
        cursor = db.properties.find(query).sort("created_at", -1).limit(limit)
        raw_docs = list(cursor)
        return [PropertyModel.format_property(doc) for doc in raw_docs]
    except Exception as e:
        logger.error(f"Error querying properties database: {e}")
        return []


def handle_enquiry_action(user: dict, property_info: dict, message: str) -> dict:
    """
    Creates property enquiry using existing enquiry database logic.
    """
    if not user:
        return {
            "success": False,
            "error": "AUTH_REQUIRED",
            "message": "Please log in to submit an enquiry to the property agent."
        }

    if not property_info or not property_info.get("id"):
        return {
            "success": False,
            "error": "PROPERTY_REQUIRED",
            "message": "Please select a property first to submit an enquiry."
        }

    db = get_db()
    if db is None:
        return {"success": False, "error": "DB_ERROR", "message": "Database connection unavailable."}

    try:
        prop_obj_id = ObjectId(property_info["id"])
        prop_doc = db.properties.find_one({"_id": prop_obj_id})
        if not prop_doc:
            return {"success": False, "error": "NOT_FOUND", "message": "Property not found."}

        customer_id = ObjectId(user["_id"])
        agent_id = prop_doc.get("agent_id") or prop_doc.get("owner_id")

        enquiry_doc = {
            "customer_id": customer_id,
            "customer_name": user.get("name", "Customer"),
            "customer_email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "property_id": prop_obj_id,
            "agent_id": agent_id,
            "message": message or f"Hi, I am interested in '{prop_doc.get('title')}'. Please share more details.",
            "response_message": "",
            "status": "new",
            "created_at": datetime.now(timezone.utc)
        }

        res = db.enquiries.insert_one(enquiry_doc)
        db.properties.update_one({"_id": prop_obj_id}, {"$inc": {"enquiry_count": 1, "enquiries_count": 1}})

        # Trigger notification if agent exists
        if agent_id:
            try:
                from app.utils.notification_utils import create_notification
                create_notification(
                    db=db,
                    user_id=agent_id,
                    type_str="new_enquiry",
                    title="New Property Enquiry",
                    message=f"New enquiry received for '{prop_doc.get('title')}' from {user.get('name', 'Customer')}.",
                    related_id=res.inserted_id
                )
            except Exception as notif_err:
                logger.warning(f"Notification error: {notif_err}")

        return {
            "success": True,
            "enquiry_id": str(res.inserted_id),
            "property_id": str(prop_obj_id),
            "property_title": prop_doc.get("title"),
            "message": f"Your enquiry for '{prop_doc.get('title')}' has been submitted successfully. The assigned agent will contact you soon."
        }
    except Exception as e:
        logger.error(f"Error creating enquiry via chatbot: {e}")
        return {"success": False, "error": "SERVER_ERROR", "message": "Failed to submit enquiry."}


def handle_visit_action(user: dict, property_info: dict, visit_date: str, visit_time: str, message: str) -> dict:
    """
    Creates property visit request using existing visit database logic.
    """
    if not user:
        return {
            "success": False,
            "error": "AUTH_REQUIRED",
            "message": "Please log in to schedule a property visit."
        }

    if not property_info or not property_info.get("id"):
        return {
            "success": False,
            "error": "PROPERTY_REQUIRED",
            "message": "Please select or specify a property to schedule a visit."
        }

    if not visit_date or not str(visit_date).strip():
        return {
            "success": False,
            "error": "MISSING_DATE",
            "message": "Please provide your preferred visit date."
        }

    if not visit_time or not str(visit_time).strip():
        return {
            "success": False,
            "error": "MISSING_TIME",
            "message": "Please provide your preferred visit time (e.g. 5:00 PM)."
        }

    db = get_db()
    if db is None:
        return {"success": False, "error": "DB_ERROR", "message": "Database connection unavailable."}

    try:
        prop_obj_id = ObjectId(property_info["id"])
        prop_doc = db.properties.find_one({"_id": prop_obj_id})
        if not prop_doc:
            return {"success": False, "error": "NOT_FOUND", "message": "Property not found."}

        customer_id = ObjectId(user["_id"])
        agent_id = prop_doc.get("agent_id") or prop_doc.get("owner_id")

        visit_doc = {
            "customer_id": customer_id,
            "customer_name": user.get("name", "Customer"),
            "customer_email": user.get("email", ""),
            "phone": user.get("phone", ""),
            "property_id": prop_obj_id,
            "agent_id": agent_id,
            "visit_date": str(visit_date).strip(),
            "visit_time": str(visit_time).strip(),
            "message": message or f"Visit request for '{prop_doc.get('title')}' on {visit_date} at {visit_time}.",
            "status": "requested",
            "created_at": datetime.now(timezone.utc)
        }

        res = db.visits.insert_one(visit_doc)

        if agent_id:
            try:
                from app.utils.notification_utils import create_notification
                create_notification(
                    db=db,
                    user_id=agent_id,
                    type_str="visit_request",
                    title="New Visit Request",
                    message=f"Visit request for '{prop_doc.get('title')}' on {visit_date} at {visit_time}.",
                    related_id=res.inserted_id
                )
            except Exception as notif_err:
                logger.warning(f"Notification error: {notif_err}")

        return {
            "success": True,
            "visit_id": str(res.inserted_id),
            "property_id": str(prop_obj_id),
            "property_title": prop_doc.get("title"),
            "visit_date": str(visit_date).strip(),
            "visit_time": str(visit_time).strip(),
            "message": f"Your visit for '{prop_doc.get('title')}' on {visit_date} at {visit_time} has been scheduled successfully."
        }
    except Exception as e:
        logger.error(f"Error creating visit request via chatbot: {e}")
        return {"success": False, "error": "SERVER_ERROR", "message": "Failed to schedule visit."}


def generate_fallback_natural_response(user_message: str, properties: list, action_result: dict, intent: dict) -> str:
    """
    Intelligent rule-based natural language generator fallback when AI API key is unconfigured or offline.
    """
    action = intent.get("action")

    if action_result and action_result.get("success"):
        return action_result.get("message", "Your request has been processed successfully.")

    if action_result and not action_result.get("success"):
        return action_result.get("message", "Unable to complete request.")

    if properties and len(properties) > 0:
        count = len(properties)
        lines = [f"I found {count} matching {'property' if count == 1 else 'properties'} from our database:\n"]
        for i, p in enumerate(properties, 1):
            price_fmt = f"₹{p.get('price'):,.0f}" if p.get('price') else "Price on Request"
            lines.append(f"{i}. **{p.get('title')}**\n   📍 {p.get('location')} | 💰 {price_fmt}\n   🛏️ {p.get('bedrooms')} Beds • 🛁 {p.get('bathrooms')} Baths • 📐 {p.get('area')} sq.ft\n")
        lines.append("Would you like to view details, compare, schedule a visit, or contact the agent for any of these?")
        return "\n".join(lines)

    if action == "SEARCH" or intent.get("city") or intent.get("bedrooms") or intent.get("max_price"):
        return "I couldn't find any properties matching those requirements in our database. Would you like to try a different location or increase your budget range?"

    msg_lower = user_message.lower()
    if "hi" in msg_lower or "hello" in msg_lower or "hey" in msg_lower:
        return "Hello! I'm your HavenSpace AI Property Assistant. I can help you search properties, check specifications, schedule visits, or contact property representatives. How can I assist you today?"

    if "best" in msg_lower or "recommend" in msg_lower:
        return "To recommend the best properties for you, could you please share your preferred location, property type (e.g., Apartment, Villa), and budget range?"

    return "I'm your HavenSpace Property Assistant. How can I help you find your dream property today? You can search by location, budget, bedrooms, or ask to schedule a property visit!"


def process_chat_message(user: dict, user_message: str, conversation_id: str = None, current_property_id: str = None) -> dict:
    """
    Main entry point for processing chat messages.
    """
    user_message = (user_message or "").strip()
    if not user_message:
        return {
            "success": False,
            "error": "VALIDATION_ERROR",
            "message": "Message content cannot be empty."
        }

    # Max message length safety check
    if len(user_message) > 1000:
        return {
            "success": False,
            "error": "MESSAGE_TOO_LONG",
            "message": "Message exceeds maximum allowed length of 1000 characters."
        }

    db = get_db()
    if db is None:
        return {
            "success": False,
            "error": "DATABASE_ERROR",
            "message": "Database connection unavailable."
        }

    user_id_obj = ObjectId(user["_id"]) if user and "_id" in user and ObjectId.is_valid(user["_id"]) else None

    # Retrieve or initialize chat conversation document
    conv_doc = None
    if conversation_id:
        conv_doc = db.chat_conversations.find_one({"conversation_id": conversation_id})
        if conv_doc and user_id_obj and conv_doc.get("user_id") and str(conv_doc.get("user_id")) != str(user_id_obj):
            # Enforce user authorization isolation
            return {
                "success": False,
                "error": "FORBIDDEN",
                "message": "You are not authorized to access this conversation."
            }

    if not conv_doc:
        title = user_message[:40] + ("..." if len(user_message) > 40 else "")
        conv_doc = ChatConversationModel.create_document(
            user_id=user_id_obj,
            conversation_id=conversation_id,
            title=title
        )
        # For authenticated users or valid conversation_id, insert doc into DB
        if user_id_obj or conversation_id:
            try:
                db.chat_conversations.insert_one(conv_doc)
            except Exception as ins_err:
                logger.warning(f"Conversation insert notice: {ins_err}")

    current_conv_id = conv_doc.get("conversation_id")
    history = conv_doc.get("messages", [])

    # Fetch currently viewed property doc if provided
    current_property = None
    if current_property_id and ObjectId.is_valid(current_property_id):
        p_doc = db.properties.find_one({"_id": ObjectId(current_property_id)})
        if p_doc:
            current_property = PropertyModel.format_property(p_doc)

    # 1. Invoke AI service for Intent & Filter extraction
    ai_service = get_ai_service()
    intent = {}
    try:
        intent = ai_service.extract_intent(user_message, history=history, current_property=current_property)
    except Exception as e:
        logger.error(f"AI Intent extraction error: {e}")

    # 2. Build controlled MongoDB query & fetch matching properties
    query = build_mongo_property_query(intent, user_message)
    matching_properties = execute_property_search(query, limit=5)

    # If specific property details requested by ID
    target_prop = None
    if intent.get("property_id") and ObjectId.is_valid(intent.get("property_id")):
        p_doc = db.properties.find_one({"_id": ObjectId(intent.get("property_id"))})
        if p_doc:
            target_prop = PropertyModel.format_property(p_doc)
            matching_properties = [target_prop]

    active_property = target_prop or (matching_properties[0] if matching_properties else current_property)

    # 3. Action Execution (Enquiry or Visit)
    action_type = intent.get("action")
    action_result = None

    if action_type == "ENQUIRY" or "contact agent" in user_message.lower() or "enquire" in user_message.lower():
        enquiry_msg = intent.get("enquiry_message") or user_message
        action_result = handle_enquiry_action(user, active_property, enquiry_msg)

    elif action_type == "VISIT" or "visit" in user_message.lower() or "schedule" in user_message.lower() or "book" in user_message.lower():
        v_date = intent.get("visit_date")
        v_time = intent.get("visit_time")
        
        # Simple regex extract date/time if AI intent missed them
        if not v_date:
            date_match = re.search(r"(\d{4}-\d{2}-\d{2}|tomorrow|next week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)", user_message, re.I)
            if date_match:
                v_date = date_match.group(1)
        if not v_time:
            time_match = re.search(r"(\d{1,2}(?::\d{2})?\s*(?:am|pm))", user_message, re.I)
            if time_match:
                v_time = time_match.group(1)

        action_result = handle_visit_action(user, active_property, v_date, v_time, user_message)

    # 4. Generate Natural Language Grounded AI Response
    assistant_reply = None
    try:
        assistant_reply = ai_service.generate_response(
            message=user_message,
            properties=matching_properties,
            action_result=action_result,
            history=history,
            current_property=current_property
        )
    except Exception as gen_err:
        logger.error(f"AI Response generation error: {gen_err}")

    if not assistant_reply or len(assistant_reply.strip()) == 0:
        assistant_reply = generate_fallback_natural_response(user_message, matching_properties, action_result, intent)

    # 5. Persist Chat History in MongoDB
    now_iso = datetime.now(timezone.utc).isoformat()
    user_msg_entry = {
        "role": "user",
        "content": user_message,
        "timestamp": now_iso
    }
    assistant_msg_entry = {
        "role": "assistant",
        "content": assistant_reply,
        "properties": matching_properties,
        "action": action_result,
        "timestamp": now_iso
    }

    if user_id_obj or conversation_id:
        try:
            db.chat_conversations.update_one(
                {"conversation_id": current_conv_id},
                {
                    "$push": {"messages": {"$each": [user_msg_entry, assistant_msg_entry]}},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
        except Exception as upd_err:
            logger.warning(f"Chat history update notice: {upd_err}")

    return {
        "success": True,
        "conversation_id": current_conv_id,
        "title": conv_doc.get("title", "Property Conversation"),
        "message": assistant_reply,
        "properties": matching_properties,
        "action": action_result
    }
