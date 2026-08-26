import time
import logging
from collections import defaultdict
from app.config.config import Config

logger = logging.getLogger(__name__)

class AIRateLimiter:
    """
    In-memory Rate Limiter to track daily requests per user/IP.
    """
    def __init__(self):
        self.daily_limit = getattr(Config, "AI_DAILY_LIMIT", 100)
        self.request_records = defaultdict(list)

    def is_rate_limited(self, identifier: str) -> tuple[bool, int]:
        """
        Check if identifier (user_id or ip_address) exceeded daily_limit within last 24 hours (86400 seconds).
        Returns tuple: (is_limited: bool, remaining_requests: int)
        """
        if not identifier:
            identifier = "anonymous_guest"

        now = time.time()
        cutoff = now - 86400

        # Filter out timestamps older than 24h
        valid_timestamps = [ts for ts in self.request_records[identifier] if ts > cutoff]
        self.request_records[identifier] = valid_timestamps

        count = len(valid_timestamps)
        remaining = max(0, self.daily_limit - count)

        if count >= self.daily_limit:
            logger.warning(f"Rate limit exceeded for AI request identifier: '{identifier}'. Count: {count}/{self.daily_limit}")
            return True, 0

        # Record this request
        self.request_records[identifier].append(now)
        return False, remaining - 1

_rate_limiter_instance = None

def get_rate_limiter() -> AIRateLimiter:
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = AIRateLimiter()
    return _rate_limiter_instance
