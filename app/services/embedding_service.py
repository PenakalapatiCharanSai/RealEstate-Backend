import time
import logging
import requests
from app.config.config import Config

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Service to generate vector embeddings using Gemini API (text-embedding-004).
    """
    def __init__(self, api_key: str = None, model_name: str = None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.model_name = model_name or getattr(Config, "GEMINI_EMBEDDING_MODEL", "text-embedding-004")
        self.timeout = getattr(Config, "AI_REQUEST_TIMEOUT", 30)

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_") and len(self.api_key) >= 10)

    def generate_embedding(self, text: str) -> list:
        """
        Generates embedding vector array for a given text string.
        Returns list of floats or empty list on failure.
        """
        text = (text or "").strip()
        if not text:
            return []

        if not self.is_configured():
            logger.warning("Gemini API key is unconfigured for embeddings.")
            return []

        models_to_try = [
            self.model_name.replace("models/", ""),
            "text-embedding-004",
            "embedding-001"
        ]

        # Remove duplicates preserving order
        unique_models = []
        for m in models_to_try:
            if m and m not in unique_models:
                unique_models.append(m)

        for model in unique_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={self.api_key}"
            payload = {
                "model": f"models/{model}",
                "content": {
                    "parts": [{"text": text}]
                }
            }
            headers = {"Content-Type": "application/json"}

            backoff = 1.0
            for attempt in range(2):
                try:
                    resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)

                    if resp.status_code == 200:
                        data = resp.json()
                        embedding_obj = data.get("embedding", {})
                        values = embedding_obj.get("values", [])
                        if values:
                            # Cache working model name
                            self.model_name = model
                            return values

                    elif resp.status_code == 429:
                        logger.warning(f"Embedding API 429 rate limit on {model}. Retrying in {backoff}s...")
                        time.sleep(backoff)
                        backoff *= 2.0

                    else:
                        logger.debug(f"Embedding model {model} returned status {resp.status_code}")
                        break

                except Exception as e:
                    logger.error(f"Error generating embedding on model {model}: {e}")
                    time.sleep(backoff)
                    backoff *= 1.5

        return []


_embedding_service_instance = None

def get_embedding_service() -> EmbeddingService:
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
