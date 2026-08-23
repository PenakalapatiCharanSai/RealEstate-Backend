import bcrypt

def hash_password(plain_password):
    """
    Hash a plain-text password securely using bcrypt.
    """
    if not plain_password:
        raise ValueError("Password cannot be empty")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(str(plain_password).encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password, hashed_password):
    """
    Verify a plain-text password against a stored bcrypt hash.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            str(plain_password).encode("utf-8"),
            str(hashed_password).encode("utf-8")
        )
    except Exception:
        return False
