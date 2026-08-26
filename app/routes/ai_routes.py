import logging
from flask import Blueprint, request, jsonify
from app.utils.db import get_db
from app.utils.rate_limiter import get_rate_limiter
from app.middleware.auth_middleware import authenticate_user
from app.middleware.role_middleware import role_required

from app.services.gemini_service import get_gemini_service
from app.services.embedding_service import get_embedding_service
from app.services.rag_service import get_rag_service
from app.services.knowledge_service import get_knowledge_service
from app.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)

ai_routes_bp = Blueprint("ai_routes", __name__)

@ai_routes_bp.route("/health", methods=["GET"])
def ai_health_check():
    """
    GET /api/ai/health
    Returns configuration and connectivity status of Gemini API, MongoDB, and Vector Search.
    Does not expose sensitive keys.
    """
    db = get_db()
    gemini_svc = get_gemini_service()
    embedding_svc = get_embedding_service()

    mongo_status = "connected" if db is not None else "disconnected"
    gemini_status = "configured" if gemini_svc.is_configured() else "unconfigured"
    embedding_status = "configured" if embedding_svc.is_configured() else "unconfigured"

    return jsonify({
        "success": True,
        "gemini": gemini_status,
        "embedding": embedding_status,
        "mongodb": mongo_status,
        "vector_search": "configured" if (gemini_status == "configured" and mongo_status == "connected") else "fallback"
    }), 200

@ai_routes_bp.route("/chat", methods=["POST"])
def ai_chat():
    """
    POST /api/ai/chat
    Request: { "message": "...", "conversation_id": "...", "current_property_id": "..." }
    """
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "Message is required."}), 400

    # Rate limiting
    ip_addr = request.remote_addr or "anonymous"
    limiter = get_rate_limiter()
    is_limited, remaining = limiter.is_rate_limited(ip_addr)
    if is_limited:
        return jsonify({
            "success": False,
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "You have reached the daily limit of 100 AI requests. Please try again tomorrow."
        }), 429

    try:
        # Extract intent & filters
        ai_svc = get_ai_service()
        intent = ai_svc.extract_intent(message)

        # RAG Grounded Answer
        rag_svc = get_rag_service()
        res = rag_svc.answer_rag_query(
            user_message=message,
            intent_filters=intent,
            current_property_id=data.get("current_property_id"),
            history=data.get("history", [])
        )
        res["remaining_daily_requests"] = remaining
        res["conversation_id"] = data.get("conversation_id")
        return jsonify(res), 200

    except Exception as e:
        logger.error(f"Error in /api/ai/chat: {e}")
        return jsonify({
            "success": False,
            "error": "SERVER_ERROR",
            "message": "Sorry, unable to process your request at the moment."
        }), 500

@ai_routes_bp.route("/property-search", methods=["POST"])
def ai_property_search():
    """
    POST /api/ai/property-search
    Request: { "query": "Find 2 BHK in Hyderabad under 70 lakhs" }
    Returns structured matching properties and grounded summary.
    """
    data = request.get_json() or {}
    query_text = (data.get("query") or data.get("message") or "").strip()

    if not query_text:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "Query string is required."}), 400

    ai_svc = get_ai_service()
    intent = ai_svc.extract_intent(query_text)

    rag_svc = get_rag_service()
    properties = rag_svc.retrieve_hybrid_properties(query_text, intent, top_k=6)

    res = rag_svc.answer_rag_query(user_message=query_text, intent_filters=intent)
    res["properties"] = properties
    return jsonify(res), 200

@ai_routes_bp.route("/property/<property_id>/chat", methods=["POST"])
def ai_property_specific_chat(property_id):
    """
    POST /api/ai/property/<property_id>/chat
    Property details page chatbot endpoint. Answers questions grounded exclusively on the specified property.
    """
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "Message is required."}), 400

    rag_svc = get_rag_service()
    res = rag_svc.answer_rag_query(
        user_message=message,
        current_property_id=property_id,
        history=data.get("history", [])
    )
    res["property_id"] = property_id
    return jsonify(res), 200

@ai_routes_bp.route("/knowledge-search", methods=["POST"])
def ai_knowledge_search():
    """
    POST /api/ai/knowledge-search
    Request: { "query": "What are the site visit rules?" }
    """
    data = request.get_json() or {}
    query_text = (data.get("query") or "").strip()

    if not query_text:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "Query is required."}), 400

    rag_svc = get_rag_service()
    chunks = rag_svc.retrieve_knowledge_chunks(query_text, top_k=3)

    formatted_chunks = [
        {
            "document_id": c.get("document_id"),
            "document_name": c.get("document_name"),
            "chunk_id": c.get("chunk_id"),
            "text": c.get("text"),
            "category": c.get("category")
        } for c in chunks
    ]
    return jsonify({"success": True, "query": query_text, "results": formatted_chunks}), 200

@ai_routes_bp.route("/index-property/<property_id>", methods=["POST"])
def ai_index_single_property(property_id):
    """
    POST /api/ai/index-property/<property_id>
    Generates text & embeddings for a single property document.
    """
    rag_svc = get_rag_service()
    res = rag_svc.index_property(property_id)
    status_code = 200 if res.get("success") else 400
    return jsonify(res), status_code

@ai_routes_bp.route("/reindex-properties", methods=["POST"])
@authenticate_user
@role_required(["admin"])
def ai_reindex_all_properties_admin(current_user):
    """
    POST /api/ai/reindex-properties (Admin Protected)
    Triggers complete property database vector re-indexing.
    """
    rag_svc = get_rag_service()
    res = rag_svc.reindex_all_properties()
    return jsonify(res), 200

@ai_routes_bp.route("/index-document", methods=["POST"])
@authenticate_user
@role_required(["admin"])
def ai_index_document_admin(current_user):
    """
    POST /api/ai/index-document (Admin Protected)
    Ingests, chunks, and embeds a knowledge base document.
    Request: { "document_name": "...", "text": "...", "category": "faq" }
    """
    data = request.get_json() or {}
    doc_name = (data.get("document_name") or "").strip()
    text = (data.get("text") or "").strip()
    category = data.get("category", "general")

    if not doc_name or not text:
        return jsonify({"success": False, "error": "VALIDATION_ERROR", "message": "document_name and text required."}), 400

    ks = get_knowledge_service()
    res = ks.ingest_document(document_name=doc_name, text=text, category=category)
    return jsonify(res), 200

