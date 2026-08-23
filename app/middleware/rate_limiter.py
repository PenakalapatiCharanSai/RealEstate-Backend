import time
from collections import defaultdict
from flask import request, jsonify

class RateLimiter:
    """
    In-Memory Sliding Window Rate Limiter Guard to protect sensitive auth endpoints
    from automated brute-force, password guessing, and DDoS attacks.
    """
    def __init__(self):
        # Maps (ip, endpoint_group) -> list of timestamp floats
        self.request_records = defaultdict(list)

    def is_rate_limited(self, ip_address, group, limit, window_seconds=60):
        now = time.time()
        key = f"{ip_address}:{group}"
        timestamps = self.request_records[key]

        # Filter out timestamps outside the sliding window
        valid_timestamps = [ts for ts in timestamps if now - ts < window_seconds]
        self.request_records[key] = valid_timestamps

        if len(valid_timestamps) >= limit:
            return True, int(window_seconds - (now - valid_timestamps[0]))

        valid_timestamps.append(now)
        return False, 0

# Global Rate Limiter Instance
limiter = RateLimiter()

def rate_limit_guard():
    """
    Before-request rate limiter middleware.
    """
    # Exclude static file uploads and health checks from aggressive rate limiting
    path = request.path
    if path.startswith("/uploads") or path == "/api/health":
        return None

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    # Sensitive Auth Endpoints: Max 15 requests per minute per IP
    if path in ["/api/auth/login", "/api/auth/register", "/api/auth/verify-otp", "/api/auth/resend-otp", "/api/auth/forgot-password"]:
        limited, retry_after = limiter.is_rate_limited(client_ip, group="auth_sensitive", limit=15, window_seconds=60)
        if limited:
            return jsonify({
                "success": False,
                "error": "Too Many Requests",
                "message": f"Rate limit exceeded for authentication requests. Please try again in {retry_after} seconds."
            }), 429

    # General API Endpoints: Max 300 requests per minute per IP
    else:
        limited, retry_after = limiter.is_rate_limited(client_ip, group="api_general", limit=300, window_seconds=60)
        if limited:
            return jsonify({
                "success": False,
                "error": "Too Many Requests",
                "message": f"Rate limit exceeded. Please wait {retry_after} seconds before sending more requests."
            }), 429

    return None
