import os
import uuid
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB per file

def is_allowed_file(filename):
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def validate_image_file(file_storage):
    """
    Validates uploaded FileStorage object.
    Returns (is_valid: bool, error_message: str | None)
    """
    if not file_storage or not file_storage.filename:
        return False, "No file provided or file is empty."

    if not is_allowed_file(file_storage.filename):
        allowed_str = ", ".join(ALLOWED_EXTENSIONS).upper()
        return False, f"Invalid image format. Allowed formats: {allowed_str}"

    # Check file size by reading content or seeking
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)

    if size > MAX_FILE_SIZE_BYTES:
        return False, f"File size exceeds the 5MB limit ({round(size / (1024 * 1024), 2)}MB uploaded)."

    return True, None


def save_image_file(file_storage, upload_folder="properties"):
    """
    Saves image using Cloudinary if credentials are configured,
    or falls back to local disk storage in backend/uploads/properties/.

    Returns dict:
    {
      "url": str,
      "public_id": str,
      "provider": "cloudinary" | "local"
    }
    """
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
    api_key = os.environ.get("CLOUDINARY_API_KEY")
    api_secret = os.environ.get("CLOUDINARY_API_SECRET")

    # 1. Cloudinary Provider
    if cloud_name and api_key and api_secret:
        try:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True
            )

            res = cloudinary.uploader.upload(
                file_storage,
                folder=f"real_estate_marketplace/{upload_folder}",
                resource_type="image"
            )

            return {
                "url": res.get("secure_url"),
                "public_id": res.get("public_id"),
                "provider": "cloudinary"
            }
        except Exception as e:
            print(f"[STORAGE WARNING] Cloudinary upload failed ({str(e)}). Falling back to local storage.")

    # 2. Local Disk Fallback
    original_filename = secure_filename(file_storage.filename)
    ext = original_filename.rsplit(".", 1)[1].lower() if "." in original_filename else "jpg"
    unique_filename = f"{uuid.uuid4().hex}.{ext}"

    # Ensure backend/uploads/properties directory exists
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    target_dir = os.path.join(backend_dir, "uploads", upload_folder)
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, unique_filename)
    file_storage.save(file_path)

    relative_url = f"/uploads/{upload_folder}/{unique_filename}"

    return {
        "url": relative_url,
        "public_id": unique_filename,
        "provider": "local"
    }


def delete_storage_image(public_id, provider="local", upload_folder="properties"):
    """
    Deletes stored image file from Cloudinary or local disk.
    """
    if not public_id:
        return False

    if provider == "cloudinary":
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
        api_key = os.environ.get("CLOUDINARY_API_KEY")
        api_secret = os.environ.get("CLOUDINARY_API_SECRET")
        if cloud_name and api_key and api_secret:
            try:
                import cloudinary
                import cloudinary.uploader
                cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret)
                cloudinary.uploader.destroy(public_id)
                return True
            except Exception as e:
                print(f"[STORAGE ERROR] Failed to delete Cloudinary resource {public_id}: {str(e)}")
                return False

    # Local file deletion
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    filename = os.path.basename(public_id)
    file_path = os.path.join(backend_dir, "uploads", upload_folder, filename)

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            print(f"[STORAGE ERROR] Failed to remove local file {file_path}: {str(e)}")
            return False

    return True
