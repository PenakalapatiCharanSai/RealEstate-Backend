from datetime import datetime, timedelta, timezone
import jwt
from app.config.config import Config

def generate_token(user_id, role, expires_in_hours=None):
    """
    Generate JWT token containing user_id, role, iat, and exp.
    """
    if expires_in_hours is None:
        expires_in_hours = Config.JWT_EXPIRATION_HOURS

    now = datetime.now(timezone.utc)
    expiration = now + timedelta(hours=expires_in_hours)

    payload = {
        "sub": str(user_id),
        "role": str(role),
        "iat": now,
        "exp": expiration,
    }

    token = jwt.encode(payload, Config.JWT_SECRET, algorithm="HS256")
    return token

def decode_token(token):
    """
    Decode and validate JWT token.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise ValueError("Invalid authentication token")
