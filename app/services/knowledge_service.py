import uuid
import logging
from datetime import datetime, timezone
from app.utils.db import get_db
from app.config.config import Config
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)

def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> list[str]:
    """
    Splits text into chunks of specified size with overlap.
    """
    chunk_size = chunk_size or getattr(Config, "CHUNK_SIZE", 500)
    chunk_overlap = chunk_overlap or getattr(Config, "CHUNK_OVERLAP", 50)

    text = (text or "").strip()
    if not text:
        return []

    words = text.split()
    if len(words) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunks.append(" ".join(chunk_words))
        start += (chunk_size - chunk_overlap)

    return chunks

class KnowledgeService:
    """
    Manages document ingestion, chunking, embedding generation, and vector retrieval for HavenSpace Knowledge Base.
    """
    def __init__(self):
        self.embedding_service = get_embedding_service()

    def ingest_document(self, document_name: str, text: str, category: str = "general", metadata: dict = None) -> dict:
        """
        Chunks text, generates embeddings for each chunk, and inserts into `db.knowledge_base`.
        """
        db = get_db()
        if db is None:
            return {"success": False, "error": "DB_UNAVAILABLE", "message": "Database connection unavailable."}

        document_id = str(uuid.uuid4())
        chunks = chunk_text(text)

        inserted_chunks = 0
        now = datetime.now(timezone.utc)

        for idx, chunk_str in enumerate(chunks):
            embedding_vector = self.embedding_service.generate_embedding(chunk_str)

            chunk_doc = {
                "document_id": document_id,
                "document_name": document_name,
                "chunk_id": f"{document_id}_chunk_{idx}",
                "chunk_index": idx,
                "text": chunk_str,
                "embedding": embedding_vector,
                "category": category,
                "metadata": metadata or {},
                "created_at": now
            }

            try:
                db.knowledge_base.insert_one(chunk_doc)
                inserted_chunks += 1
            except Exception as e:
                logger.error(f"Failed to insert knowledge base chunk {idx} for doc '{document_name}': {e}")

        return {
            "success": True,
            "document_id": document_id,
            "document_name": document_name,
            "total_chunks": len(chunks),
            "inserted_chunks": inserted_chunks
        }

_knowledge_service_instance = None

def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service_instance
    if _knowledge_service_instance is None:
        _knowledge_service_instance = KnowledgeService()
    return _knowledge_service_instance
