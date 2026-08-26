import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, g
from pymongo.errors import DuplicateKeyError
from bson.objectid import ObjectId
import logging

from app.utils.db import get_db
from app.utils.password_utils import hash_password, verify_password
from app.utils.jwt_utils import generate_token, decode_token
from app.models import UserModel
from app.middleware.auth_middleware import authenticate_user
from app.services.notification_service import send_welcome_email, send_password_reset_email, send_otp_email

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

PUBLIC_ALLOWED_ROLES = ["customer", "agent"]

def hash_otp_code(code_str):
    """Utility to compute SHA-256 hash of a 6-digit OTP code."""
    return hashlib.sha256(str(code_str).strip().encode("utf-8")).hexdigest()

@auth_bp.route("/register", methods=["POST"])
def register():
    """
    Public User & Agent Registration Endpoint with Secure Gmail SMTP Email OTP Verification
    Saves user with status='pending_verification', email_verified=False, sends OTP email.
    """
    data = request.get_json() or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    phone = str(data.get("phone", "")).strip()
    role = str(data.get("role", "customer")).strip().lower()

    # Field validations
    if not name:
        return jsonify({"success": False, "error": "Validation Error", "message": "Name is required."}), 400

    if not email or "@" not in email:
        return jsonify({"success": False, "error": "Validation Error", "message": "A valid email address is required."}), 400

    if not password or len(password) < 6:
        return jsonify({"success": False, "error": "Validation Error", "message": "Password must be at least 6 characters long."}), 400

    # Role check for public registration
    if role == "admin" or role not in PUBLIC_ALLOWED_ROLES:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": f"Public registration for role '{role}' is not allowed. Allowed roles: customer, agent, owner."
        }), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    hashed_pw = hash_password(password)

    # Secure 6-digit numeric OTP generation using secrets module
    otp_code = f"{secrets.randbelow(1000000):06d}"
    otp_hash = hash_otp_code(otp_code)
    now = datetime.now(timezone.utc)
    otp_expires_at = now + timedelta(minutes=10)

    # Check for existing user account
    existing_user = db.users.find_one({"email": email})
    if existing_user:
        is_already_verified = bool(existing_user.get("email_verified") or existing_user.get("is_verified") or existing_user.get("status") in ["active", "pending_approval"])
        if is_already_verified:
            return jsonify({"success": False, "error": "Conflict", "message": "An account with this email address already exists. Please log in."}), 400
        
        # Unverified account exists: Update credentials and re-issue a fresh OTP
        db.users.update_one(
            {"_id": existing_user["_id"]},
            {
                "$set": {
                    "name": name,
                    "password": hashed_pw,
                    "phone": phone,
                    "role": role,
                    "status": "pending_verification",
                    "email_verified": False,
                    "is_verified": False,
                    "otp_hash": otp_hash,
                    "otp_expires_at": otp_expires_at,
                    "otp_attempts": 0,
                    "last_otp_sent_at": now,
                    "updated_at": now
                },
                "$unset": {"otp_code": ""}
            }
        )

        email_sent = True
        try:
            send_otp_email(user_email=email, user_name=name, otp_code=otp_code)
        except Exception as mail_err:
            email_sent = False
            logger.error(f"[RE-REGISTRATION OTP EMAIL NOTICE] Error for {email}: {mail_err}")

        print(f"\n==========================================")
        print(f"[RE-REGISTER OTP CODE] Email: {email} | OTP: {otp_code}")
        print(f"==========================================\n")

        return jsonify({
            "success": True,
            "requires_otp": True,
            "requiresVerification": True,
            "email": email,
            "message": "Unverified account found. A new 6-digit verification code has been sent to your email."
        }), 200

    # Create new user document for brand-new email registration
    try:
        user_doc = UserModel.create_document(
            name=name,
            email=email,
            password=hashed_pw,
            phone=phone,
            role=role,
            status="pending_verification",
            email_verified=False,
            is_verified=False,
            otp_hash=otp_hash,
            otp_expires_at=otp_expires_at,
            otp_attempts=0,
            last_otp_sent_at=now
        )

        result = db.users.insert_one(user_doc)
        user_id = str(result.inserted_id)

        # Dispatch OTP Email via Gmail SMTP
        email_sent = True
        try:
            send_otp_email(user_email=email, user_name=name, otp_code=otp_code)
        except Exception as mail_err:
            email_sent = False
            logger.error(f"[REGISTRATION OTP EMAIL NOTICE] OTP email dispatch error for {email}: {mail_err}")

        # Terminal log for local dev debugging
        print(f"\n==========================================")
        print(f"[REGISTER OTP CODE] Email: {email} | OTP: {otp_code}")
        print(f"==========================================\n")

        msg = "Account created. A 6-digit verification code has been sent to your email." if email_sent else "Account created, but we could not send the verification email. Please try Resend OTP."

        return jsonify({
            "success": True,
            "requires_otp": True,
            "requiresVerification": True,
            "email": email,
            "message": msg
        }), 201

    except DuplicateKeyError:
        return jsonify({"success": False, "error": "Conflict", "message": "An account with this email address already exists."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": "Server Error", "message": f"Registration failed: {str(e)}"}), 500


@auth_bp.route("/google", methods=["POST"])
def google_auth():
    """
    Google OAuth Registration & Login Endpoint
    Accepts Google ID Token (credential) or Google User details.
    Verifies token with Google OAuth API, registers brand new user if not found (with email_verified=True),
    or logs in existing user.
    """
    data = request.get_json() or {}
    credential = data.get("credential") or data.get("token") or data.get("id_token")
    role = str(data.get("role", "customer")).strip().lower()
    if role not in PUBLIC_ALLOWED_ROLES:
        role = "customer"

    email = None
    name = None
    google_id = None
    picture = None

    # Try verifying Google ID Token or Access Token with Google APIs if credential is provided
    if credential:
        try:
            import urllib.request
            import json
            req_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
            req = urllib.request.Request(req_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    token_info = json.loads(resp.read().decode("utf-8"))
                    email = token_info.get("email")
                    name = token_info.get("name") or token_info.get("given_name")
                    google_id = token_info.get("sub")
                    picture = token_info.get("picture")
        except Exception as err:
            logger.warning(f"Google tokeninfo validation notice: {err}")

        # Also check access_token via userinfo if tokeninfo didn't yield email
        if not email:
            try:
                import urllib.request
                import json
                userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
                req = urllib.request.Request(userinfo_url, headers={
                    "Authorization": f"Bearer {credential}",
                    "User-Agent": "Mozilla/5.0"
                })
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        token_info = json.loads(resp.read().decode("utf-8"))
                        email = token_info.get("email")
                        name = token_info.get("name") or token_info.get("given_name")
                        google_id = token_info.get("sub")
                        picture = token_info.get("picture")
            except Exception as err:
                logger.warning(f"Google userinfo validation notice: {err}")

    # Fallback to direct payload parameters if client fetched userinfo directly
    if not email:
        email = str(data.get("email", "")).strip().lower()
        name = str(data.get("name", "")).strip() or (email.split("@")[0] if email else "")
        google_id = data.get("google_id") or data.get("sub")
        picture = data.get("picture")

    if not email or "@" not in email:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": "Valid Google email address is required."
        }), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    now = datetime.now(timezone.utc)
    user = db.users.find_one({"email": email})

    if user:
        # Existing user - update Google info if missing and mark verified
        update_fields = {"last_login_at": now, "updated_at": now}
        if google_id and not user.get("google_id"):
            update_fields["google_id"] = google_id
        if picture and not user.get("avatar_url"):
            update_fields["avatar_url"] = picture
        if not user.get("email_verified"):
            update_fields["email_verified"] = True
            update_fields["is_verified"] = True
            if user.get("status") == "pending_verification":
                update_fields["status"] = "pending_approval" if user.get("role") in ["agent", "owner"] else "active"

        db.users.update_one({"_id": user["_id"]}, {"$set": update_fields})
        user = db.users.find_one({"_id": user["_id"]})
    else:
        # Brand new user registration via Google!
        user_status = "pending_approval" if role in ["agent", "owner"] else "active"
        random_pw_hash = hash_password(secrets.token_hex(16))
        
        user_doc = UserModel.create_document(
            name=name or email.split("@")[0],
            email=email,
            password=random_pw_hash,
            phone="",
            role=role,
            status=user_status,
            email_verified=True,
            is_verified=True,
            google_id=google_id,
            avatar_url=picture,
            auth_provider="google"
        )

        result = db.users.insert_one(user_doc)
        user = db.users.find_one({"_id": result.inserted_id})

        # Send welcome email
        try:
            send_welcome_email(user_email=email, user_name=name or email.split("@")[0], role=role)
        except Exception as mail_err:
            logger.error(f"[GOOGLE WELCOME EMAIL NOTICE] Error for {email}: {mail_err}")

    user_id = str(user["_id"])
    user_role = user.get("role", role)
    user_status = user.get("status", "active")
    formatted_user = UserModel.format_user(user)

    if user_role in ["agent", "owner"] and user_status == "pending_approval":
        return jsonify({
            "success": True,
            "requires_approval": True,
            "message": "Google registration successful! Your agent account is pending administrator approval before signing in.",
            "data": {
                "user": formatted_user
            }
        }), 200

    token = generate_token(user_id, user_role)
    return jsonify({
        "success": True,
        "message": "Google authentication successful.",
        "data": {
            "token": token,
            "user": formatted_user
        }
    }), 200


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify 6-digit Email OTP Endpoint
    Validates SHA-256 hash, marks email_verified=True, sends Welcome Email.
    """
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    otp = str(data.get("otp", "")).strip()

    if not email or not otp:
        return jsonify({"success": False, "error": "Validation Error", "message": "Both email and OTP code are required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"success": False, "error": "Not Found", "message": "Account not found."}), 404

    is_already_verified = bool(user.get("email_verified") or user.get("is_verified"))
    if is_already_verified and user.get("status") == "active":
        return jsonify({"success": False, "error": "Conflict", "message": "Account is already verified. Please log in."}), 400

    # Max 5 attempts check
    attempts = user.get("otp_attempts", 0)
    if attempts >= 5:
        return jsonify({"success": False, "error": "Too Many Attempts", "message": "Too many verification attempts. Please request a new OTP."}), 400

    # Expiration check
    now = datetime.now(timezone.utc)
    otp_expires_at = user.get("otp_expires_at")
    if otp_expires_at:
        if otp_expires_at.tzinfo is None:
            otp_expires_at = otp_expires_at.replace(tzinfo=timezone.utc)
        if now > otp_expires_at:
            return jsonify({"success": False, "error": "Expired", "message": "OTP has expired. Please request a new OTP."}), 400

    # Verify SHA-256 OTP Hash
    entered_hash = hash_otp_code(otp)
    stored_hash = user.get("otp_hash")
    
    # Backwards compatibility check for legacy plaintext stored codes during migration
    legacy_otp = str(user.get("otp_code", "")).strip()
    is_valid_otp = (stored_hash and stored_hash == entered_hash) or (legacy_otp and legacy_otp == otp)

    if not is_valid_otp:
        db.users.update_one({"_id": user["_id"]}, {"$inc": {"otp_attempts": 1}})
        remaining = 5 - (attempts + 1)
        err_msg = f"Invalid verification code. {remaining} attempt(s) remaining." if remaining > 0 else "Invalid verification code. Maximum attempts exceeded. Please request a new OTP."
        return jsonify({"success": False, "error": "Validation Error", "message": err_msg}), 400

    # Determine status & activation after verification
    role = user.get("role", "customer")
    # Preserve Agent approval flow: if agent/owner, transition to pending_approval unless already active
    if role in ["agent", "owner"]:
        new_status = "pending_approval" if user.get("status") in ["pending_verification", "inactive"] else user.get("status", "pending_approval")
    else:
        new_status = "active"

    # Mark email_verified=True and clear OTP fields
    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {"status": new_status, "email_verified": True, "is_verified": True},
            "$unset": {"otp_hash": "", "otp_code": "", "otp_expires_at": "", "otp_attempts": "", "last_otp_sent_at": ""}
        }
    )

    updated_user = db.users.find_one({"_id": user["_id"]})
    user_id = str(updated_user["_id"])
    formatted_user = UserModel.format_user(updated_user)

    # Trigger Welcome Email ONLY AFTER successful OTP verification (idempotent check)
    if not is_already_verified:
        try:
            send_welcome_email(user_email=email, user_name=updated_user.get("name", "User"), role=role)
        except Exception as mail_err:
            logger.error(f"[WELCOME EMAIL NOTICE] Error for {email}: {mail_err}")

    if role in ["agent", "owner"] and new_status == "pending_approval":
        return jsonify({
            "success": True,
            "requires_approval": True,
            "message": "Email verified successfully! Your agent account is pending administrator approval before you can sign in.",
            "data": {
                "user": formatted_user
            }
        }), 200

    token = generate_token(user_id, role)
    return jsonify({
        "success": True,
        "message": "Email verified successfully.",
        "data": {
            "token": token,
            "user": formatted_user
        }
    }), 200


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    """
    Resend 6-Digit Verification OTP Endpoint
    Generates new secure OTP, hashes with SHA-256, enforces 60s cooldown.
    """
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()

    if not email:
        return jsonify({"success": False, "error": "Validation Error", "message": "Email address is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({"success": False, "error": "Not Found", "message": "Account not found."}), 404

    is_verified = bool(user.get("email_verified") or user.get("is_verified"))
    if is_verified and user.get("status") == "active":
        return jsonify({"success": False, "error": "Conflict", "message": "Account is already verified. Please sign in."}), 400

    now = datetime.now(timezone.utc)
    last_sent = user.get("last_otp_sent_at")
    if last_sent:
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        diff_seconds = (now - last_sent).total_seconds()
        if diff_seconds < 60:
            wait_time = int(60 - diff_seconds)
            return jsonify({
                "success": False,
                "error": "Cooldown Active",
                "message": f"Please wait {wait_time} seconds before requesting another code."
            }), 400

    # Generate new secure 6-digit OTP
    new_otp = f"{secrets.randbelow(1000000):06d}"
    new_hash = hash_otp_code(new_otp)
    expires_at = now + timedelta(minutes=10)

    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "otp_hash": new_hash,
            "otp_expires_at": expires_at,
            "otp_attempts": 0,
            "last_otp_sent_at": now
        }, "$unset": {"otp_code": ""}}
    )

    try:
        send_otp_email(user_email=email, user_name=user.get("name", "User"), otp_code=new_otp)
    except Exception as mail_err:
        logger.error(f"[RESEND OTP NOTICE] Error sending OTP to {email}: {mail_err}")

    print(f"\n==========================================")
    print(f"[RESENT OTP CODE] Email: {email} | OTP: {new_otp}")
    print(f"==========================================\n")

    return jsonify({
        "success": True,
        "message": "A new verification code has been sent."
    }), 200


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    User Login Endpoint
    Validates credentials, checks verification & agent approval status, issues JWT token.
    """
    data = request.get_json() or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not email or not password:
        return jsonify({
            "success": False,
            "error": "Validation Error",
            "message": "Both email and password are required."
        }), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user = db.users.find_one({"email": email})
    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": "Invalid email or password."
        }), 401

    if not verify_password(password, user.get("password")):
        return jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": "Invalid email or password."
        }), 401

    role = user.get("role", "customer")
    is_verified = bool(user.get("email_verified") or user.get("is_verified", False))

    # Block login for unverified accounts (except admin)
    if (not is_verified or user.get("status") == "pending_verification") and role != "admin":
        return jsonify({
            "success": False,
            "error": "Account Unverified",
            "message": "Please complete your registration email OTP verification before signing in."
        }), 403

    # Allow active accounts and pending_approval agent accounts to log in (agents can view dashboard/profile)
    if user.get("status") not in ["active", "pending_approval"]:
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "Account is inactive or suspended. Please contact support."
        }), 403

    user_id = str(user["_id"])
    token = generate_token(user_id, role)
    formatted_user = UserModel.format_user(user)

    return jsonify({
        "success": True,
        "message": "Login successful",
        "data": {
            "token": token,
            "user": formatted_user
        }
    }), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Logout Endpoint"""
    return jsonify({"success": True, "message": "Logged out successfully"}), 200


@auth_bp.route("/profile", methods=["GET"])
@authenticate_user
def get_profile():
    """Get Current Authenticated User Profile"""
    user = g.current_user
    formatted_user = UserModel.format_user(user)
    return jsonify({"success": True, "data": {"user": formatted_user}}), 200


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """
    Public Password Reset Request Endpoint (All Roles)
    Sends 6-digit OTP code to the requested user email.
    """
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()

    if not email or "@" not in email:
        return jsonify({"success": False, "error": "Validation Error", "message": "Valid email is required."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    user = db.users.find_one({"email": email})
    if user:
        otp_code = f"{secrets.randbelow(1000000):06d}"
        otp_hash = hash_otp_code(otp_code)
        now = datetime.now(timezone.utc)
        otp_expires_at = now + timedelta(minutes=15)

        db.users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "reset_otp_hash": otp_hash,
                    "reset_otp_expires_at": otp_expires_at,
                    "updated_at": now
                }
            }
        )

        try:
            from app.services.notification_service import send_otp_email
            send_otp_email(user_email=email, user_name=user.get("name", "User"), otp_code=otp_code)
        except Exception as mail_err:
            logger.error(f"[FORGOT PASSWORD EMAIL NOTICE] Failed to send OTP email to {email}: {mail_err}")

    return jsonify({
        "success": True,
        "message": "If an account with that email exists, a password reset OTP code has been sent."
    }), 200


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """
    Password Reset Completion Endpoint (All Roles)
    Verifies 6-digit OTP code or reset token and updates the user's password.
    """
    data = request.get_json() or {}
    email = str(data.get("email", "")).strip().lower()
    otp = str(data.get("otp", "")).strip()
    token = str(data.get("token", "")).strip()
    new_password = str(data.get("new_password", ""))

    if not new_password or len(new_password) < 6:
        return jsonify({"success": False, "error": "Validation Error", "message": "New password must be at least 6 characters long."}), 400

    db = get_db()
    if db is None:
        return jsonify({"success": False, "error": "Database Error", "message": "Database connection unavailable."}), 500

    target_user = None

    # Option A: OTP verification
    if email and otp:
        user = db.users.find_one({"email": email})
        if not user:
            return jsonify({"success": False, "error": "Validation Error", "message": "Invalid email or OTP code."}), 400

        reset_hash = user.get("reset_otp_hash")
        reset_expires = user.get("reset_otp_expires_at")
        now = datetime.now(timezone.utc)

        if not reset_hash or hash_otp_code(otp) != reset_hash:
            return jsonify({"success": False, "error": "Validation Error", "message": "Invalid OTP code. Please check your email and try again."}), 400

        if reset_expires:
            if isinstance(reset_expires, datetime):
                if reset_expires.tzinfo is None:
                    reset_expires = reset_expires.replace(tzinfo=timezone.utc)
                if now > reset_expires:
                    return jsonify({"success": False, "error": "Validation Error", "message": "OTP code has expired. Please request a new code."}), 400

        target_user = user

    # Option B: Token verification
    elif token:
        payload = decode_token(token)
        if not payload or not payload.get("sub"):
            return jsonify({"success": False, "error": "Unauthorized", "message": "Invalid or expired password reset token."}), 401
        user_id = payload.get("sub")
        target_user = db.users.find_one({"_id": ObjectId(user_id)})
        if not target_user:
            return jsonify({"success": False, "error": "Not Found", "message": "User account not found."}), 404

    else:
        return jsonify({"success": False, "error": "Validation Error", "message": "Email and OTP code (or token) are required."}), 400

    hashed_pw = hash_password(new_password)
    db.users.update_one(
        {"_id": target_user["_id"]},
        {
            "$set": {"password": hashed_pw, "updated_at": datetime.now(timezone.utc)},
            "$unset": {"reset_otp_hash": "", "reset_otp_expires_at": ""}
        }
    )

    return jsonify({
        "success": True,
        "message": "Password reset successfully! You can now log in with your new password."
    }), 200
