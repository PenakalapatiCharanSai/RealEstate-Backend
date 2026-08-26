import json
import time
import logging
import requests
from app.config.config import Config

logger = logging.getLogger(__name__)

DEFAULT_MODELS = [
    getattr(Config, "GEMINI_GENERATION_MODEL", "gemini-2.0-flash"),
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash-latest",
    "gemini-1.5-flash",
    "gemini-1.5-pro"
]


class GeminiService:
    """
    Production-ready Gemini LLM Service.
    Handles text generation, grounded RAG prompts, exponential backoff for HTTP 429, and configurable timeouts.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        self.models = [m for m in DEFAULT_MODELS if m]
        self.max_retries = getattr(Config, "AI_MAX_RETRIES", 3)
        self.timeout = getattr(Config, "AI_REQUEST_TIMEOUT", 30)

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("your_") and len(self.api_key) >= 10)

    def generate_content(self, contents: list, system_instruction: str = None, temperature: float = 0.2) -> str:
        """
        Executes generateContent call with exponential backoff on HTTP 429 quota limits.
        """
        if not self.is_configured():
            logger.warning("Gemini API key is missing or unconfigured.")
            return None

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 1024,
            }
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        headers = {"Content-Type": "application/json"}
        last_error = None

        for model in self.models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
            
            backoff_delay = 1.0
            for attempt in range(1, self.max_retries + 1):
                try:
                    resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)

                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates and len(candidates) > 0:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "")
                        return ""

                    elif resp.status_code == 429:
                        logger.warning(f"Gemini API rate limit 429 on model {model} (Attempt {attempt}/{self.max_retries}). Backing off {backoff_delay}s...")
                        time.sleep(backoff_delay)
                        backoff_delay *= 2.0
                        last_error = f"HTTP 429: Resource Exhausted on {model}"

                    else:
                        logger.warning(f"Gemini API model {model} returned HTTP status {resp.status_code}")
                        last_error = f"HTTP {resp.status_code}: {resp.text}"
                        break # Try next model if non-429 error

                except requests.exceptions.Timeout:
                    logger.error(f"Gemini API request timed out after {self.timeout}s on model {model} (Attempt {attempt}/{self.max_retries})")
                    last_error = f"Timeout ({self.timeout}s) on model {model}"
                    time.sleep(backoff_delay)
                    backoff_delay *= 1.5

                except Exception as err:
                    logger.error(f"Unexpected error invoking Gemini API model {model}: {err}")
                    last_error = str(err)
                    break

        logger.error(f"All Gemini model attempts failed. Last error: {last_error}")
        return None

_gemini_service_instance = None

def get_gemini_service() -> GeminiService:
    global _gemini_service_instance
    if _gemini_service_instance is None:
        _gemini_service_instance = GeminiService()
    return _gemini_service_instance
