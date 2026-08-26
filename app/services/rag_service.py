import re
import json
import math
import logging
from datetime import datetime, timezone
from bson import ObjectId

from app.utils.db import get_db
from app.models.property import PropertyModel
from app.services.gemini_service import get_gemini_service
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)

GROUNDED_SYSTEM_PROMPT = """
You are HavenSpace AI, an intelligent, professional real-estate assistant.

STRICT RAG GROUNDING RULES:
1. Use the retrieved HavenSpace context below as the primary source of truth.
2. Do not invent properties, prices, locations, amenities, availability, agent information, or platform policies.
3. If the answer cannot be found in the provided HavenSpace context, clearly state: "I couldn't find reliable HavenSpace information for that question. Please try asking about a specific property or location."
4. Never make up unlisted properties or fake database records.
5. When recommending properties, only recommend properties present in the retrieved database context.
6. When discussing price, availability, amenities, BHK, area, location, or property details, use the retrieved database information.
7. Format prices cleanly in Indian Currency notation (e.g. ₹92 Lakhs, ₹1.5 Crores, ₹35,000/month).
8. Answer naturally, concisely, and accurately.
"""

def cosine_similarity(vec_a: list, vec_b: list) -> float:
    """
    Computes cosine similarity between two vector float lists.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)

def build_searchable_property_text(doc: dict) -> str:
    """
    Constructs a rich text representation of a property for embedding generation.
    """
    title = doc.get("title", "")
    type_ = doc.get("type", "Property")
    bhk = doc.get("bedrooms", 0)
    price = doc.get("price", 0)
    location = doc.get("location", "")
    address = doc.get("address", "")
    area = doc.get("area", 0)
    bedrooms = doc.get("bedrooms", 0)
    bathrooms = doc.get("bathrooms", 0)
    parking = "available" if doc.get("parking") else "not available"
    furnishing = doc.get("furnishing", "Unfurnished")
    description = doc.get("description", "")
    tx_type = doc.get("transaction_type", "Sale")

    price_str = f"₹{price:,.0f}" if price else "Price on Request"

    text = (
        f"{title} is a {bedrooms} BHK {type_} for {tx_type} located in {location}. "
        f"Address: {address}. Price: {price_str}. Area: {area} sq.ft. "
        f"It has {bedrooms} bedrooms, {bathrooms} bathrooms, {furnishing} status, and parking is {parking}. "
        f"Description: {description}."
    )
    return text.strip()

class RAGService:
    """
    Core HavenSpace RAG Pipeline Manager.
    """
    def __init__(self):
        self.gemini_service = get_gemini_service()
        self.embedding_service = get_embedding_service()

    def index_property(self, property_id: str) -> dict:
        """
        Generates embedding and searchable text for a single property and updates MongoDB.
        """
        db = get_db()
        if db is None or not ObjectId.is_valid(property_id):
            return {"success": False, "error": "INVALID_ID"}

        p_doc = db.properties.find_one({"_id": ObjectId(property_id)})
        if not p_doc:
            return {"success": False, "error": "NOT_FOUND"}

        searchable_text = build_searchable_property_text(p_doc)
        embedding_vec = self.embedding_service.generate_embedding(searchable_text)

        update_payload = {
            "searchable_text": searchable_text,
            "updated_at": datetime.now(timezone.utc)
        }
        if embedding_vec:
            update_payload["embedding"] = embedding_vec

        db.properties.update_one({"_id": ObjectId(property_id)}, {"$set": update_payload})
        return {"success": True, "property_id": property_id, "has_embedding": bool(embedding_vec)}

    def reindex_all_properties(self) -> dict:

        """
        Admin functionality: Re-generates searchable text and vector embeddings for all properties in database.
        """
        db = get_db()
        if db is None:
            return {"success": False, "error": "DB_UNAVAILABLE"}

        cursor = db.properties.find({})
        properties = list(cursor)
        indexed_count = 0

        for p_doc in properties:
            p_id = str(p_doc["_id"])
            res = self.index_property(p_id)
            if res.get("success"):
                indexed_count += 1

        return {
            "success": True,
            "total_properties": len(properties),
            "indexed_count": indexed_count
        }

    def retrieve_hybrid_properties(self, query_text: str, intent_filters: dict, top_k: int = 5) -> list:
        """
        Retrieves top properties using Hybrid Search (Hard MongoDB Metadata Filters + Vector Search).
        """
        db = get_db()
        if db is None:
            return []

        query_embedding = self.embedding_service.generate_embedding(query_text)

        # Build Hard Metadata Filter query
        mongo_filter = {"approval_status": "Approved"}
        status_val = intent_filters.get("status")
        mongo_filter["status"] = status_val if status_val else "Available"

        city = intent_filters.get("city")
        locality = intent_filters.get("locality")
        loc_terms = [t for t in [city, locality] if t]
        if loc_terms:
            pattern = "|".join([re.escape(str(t).strip()) for t in loc_terms])
            mongo_filter["$or"] = [
                {"location": {"$regex": pattern, "$options": "i"}},
                {"address": {"$regex": pattern, "$options": "i"}}
            ]

        prop_type = intent_filters.get("property_type")
        if prop_type:
            mongo_filter["type"] = {"$regex": f"^{re.escape(str(prop_type))}$", "$options": "i"}

        tx_type = intent_filters.get("transaction_type")
        if tx_type:
            mongo_filter["transaction_type"] = {"$regex": f"^{re.escape(str(tx_type))}$", "$options": "i"}

        min_price = intent_filters.get("min_price")
        max_price = intent_filters.get("max_price")
        if min_price is not None or max_price is not None:
            price_q = {}
            if min_price is not None:
                try: price_q["$gte"] = float(min_price)
                except (ValueError, TypeError): pass
            if max_price is not None:
                try: price_q["$lte"] = float(max_price)
                except (ValueError, TypeError): pass
            if price_q:
                mongo_filter["price"] = price_q

        bedrooms = intent_filters.get("bedrooms")
        if bedrooms is not None:
            try: mongo_filter["bedrooms"] = int(bedrooms)
            except (ValueError, TypeError): pass

        # 1. Attempt MongoDB Atlas Vector Search Aggregation ($vectorSearch) if query embedding exists
        atlas_results = []
        if query_embedding:
            try:
                pipeline = [
                    {
                        "$vectorSearch": {
                            "index": "vector_index",
                            "path": "embedding",
                            "queryVector": query_embedding,
                            "numCandidates": 50,
                            "limit": top_k,
                            "filter": mongo_filter
                        }
                    }
                ]
                atlas_cursor = db.properties.aggregate(pipeline)
                atlas_results = list(atlas_cursor)
            except Exception as atlas_err:
                logger.debug(f"MongoDB Atlas $vectorSearch notice: {atlas_err}")

        if atlas_results:
            return [PropertyModel.format_property(doc) for doc in atlas_results]

        # 2. Fallback: Query MongoDB with hard filters, then compute vector cosine similarity in memory
        cursor = db.properties.find(mongo_filter).limit(50)
        candidates = list(cursor)

        if not candidates:
            # If hard filters produced zero candidates, relax location filter for vector matching
            relaxed_filter = {"approval_status": "Approved", "status": mongo_filter.get("status", "Available")}
            candidates = list(db.properties.find(relaxed_filter).limit(50))

        scored_props = []
        for doc in candidates:
            doc_embedding = doc.get("embedding")
            similarity = 0.0
            if query_embedding and doc_embedding:
                similarity = cosine_similarity(query_embedding, doc_embedding)

            formatted = PropertyModel.format_property(doc)
            formatted["similarity_score"] = round(similarity, 4)
            scored_props.append((similarity, formatted))

        # Sort by similarity descending (or created_at if no vector match)
        scored_props.sort(key=lambda x: x[0], reverse=True)
        top_matches = [item[1] for item in scored_props[:top_k]]
        return top_matches

    def retrieve_knowledge_chunks(self, query_text: str, top_k: int = 3) -> list:
        """
        Retrieves top relevant documentation / FAQ chunks from `db.knowledge_base`.
        """
        db = get_db()
        if db is None:
            return []

        query_vec = self.embedding_service.generate_embedding(query_text)
        cursor = db.knowledge_base.find({}).limit(100)
        chunks = list(cursor)

        scored = []
        for c in chunks:
            sim = 0.0
            if query_vec and c.get("embedding"):
                sim = cosine_similarity(query_vec, c.get("embedding"))
            scored.append((sim, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k] if item[0] > 0.3 or not query_vec]

    def answer_rag_query(self, user_message: str, intent_filters: dict = None, current_property_id: str = None, history: list = None) -> dict:
        """
        Complete RAG Pipeline: Retrieval -> Context Building -> Grounded Gemini Generation.
        """
        db = get_db()
        intent_filters = intent_filters or {}
        sources = []

        # 1. Check if specific property details requested
        current_property = None
        if current_property_id and ObjectId.is_valid(current_property_id):
            p_doc = db.properties.find_one({"_id": ObjectId(current_property_id)}) if db is not None else None
            if p_doc:
                current_property = PropertyModel.format_property(p_doc)


        # 2. Retrieve Property Data & Knowledge Base Chunks
        matching_properties = self.retrieve_hybrid_properties(user_message, intent_filters, top_k=5)
        knowledge_chunks = self.retrieve_knowledge_chunks(user_message, top_k=3)

        # 3. Assemble Grounded Database Context
        context_parts = []

        if current_property:
            context_parts.append(
                f"CURRENTLY VIEWED PROPERTY:\n"
                f"Title: {current_property.get('title')}\n"
                f"ID: {current_property.get('id')}\n"
                f"Price: ₹{current_property.get('price', 0):,.0f}\n"
                f"Location: {current_property.get('location')} (Address: {current_property.get('address')})\n"
                f"Specs: {current_property.get('bedrooms')} Beds, {current_property.get('bathrooms')} Baths, {current_property.get('area')} sq.ft\n"
                f"Furnishing: {current_property.get('furnishing')}, Parking: {'Yes' if current_property.get('parking') else 'No'}\n"
                f"Status: {current_property.get('status')}\n"
                f"Description: {current_property.get('description')}\n"
            )
            sources.append({
                "type": "property",
                "property_id": current_property.get("id"),
                "title": current_property.get("title")
            })

        if matching_properties:
            prop_lines = []
            for idx, p in enumerate(matching_properties, 1):
                prop_lines.append(
                    f"{idx}. Title: {p.get('title')} (ID: {p.get('id')})\n"
                    f"   Price: ₹{p.get('price', 0):,.0f} | Location: {p.get('location')}\n"
                    f"   Specs: {p.get('bedrooms')} BHK, {p.get('bathrooms')} Baths, {p.get('area')} sq.ft\n"
                    f"   Furnishing: {p.get('furnishing')}, Parking: {'Yes' if p.get('parking') else 'No'}\n"
                    f"   Description: {p.get('description')}"
                )
                if not any(s.get("property_id") == p.get("id") for s in sources):
                    sources.append({
                        "type": "property",
                        "property_id": p.get("id"),
                        "title": p.get("title")
                    })

            context_parts.append("RETRIEVED PROPERTY LISTINGS:\n" + "\n\n".join(prop_lines))

        if knowledge_chunks:
            k_lines = []
            for kc in knowledge_chunks:
                k_lines.append(f"[{kc.get('document_name')}]: {kc.get('text')}")
                sources.append({
                    "type": "document",
                    "document_id": kc.get("document_id"),
                    "document_name": kc.get("document_name"),
                    "chunk_id": kc.get("chunk_id")
                })
            context_parts.append("RETRIEVED HAVENSPACE POLICY & FAQ DATA:\n" + "\n".join(k_lines))

        context_str = "\n\n=========================================\n\n".join(context_parts) if context_parts else "No matching property or policy data found in database."

        # 4. Construct LLM Content Payload
        contents = []
        if history:
            for h in history[-6:]:
                role = "user" if h.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": h.get("content", "")}]})

        user_prompt = f"RETRIEVED HAVENSPACE DATABASE CONTEXT:\n{context_str}\n\nUSER QUESTION: {user_message}"
        contents.append({"role": "user", "parts": [{"text": user_prompt}]})

        # 5. Invoke Gemini Grounded Generation
        llm_reply = self.gemini_service.generate_content(contents, system_instruction=GROUNDED_SYSTEM_PROMPT, temperature=0.2)

        if not llm_reply or len(llm_reply.strip()) == 0:
            if matching_properties:
                llm_reply = f"I found {len(matching_properties)} matching properties in HavenSpace database."
            else:
                llm_reply = "I couldn't find reliable HavenSpace information for that question. Please try asking about a specific property, budget, or location."

        return {
            "success": True,
            "answer": llm_reply,
            "properties": matching_properties,
            "sources": sources
        }

_rag_service_instance = None

def get_rag_service() -> RAGService:
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    return _rag_service_instance
