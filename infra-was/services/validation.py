import hashlib
import re
from datetime import date


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
}


class ValidationError(ValueError):
    pass


def normalize_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise ValidationError("email must be a valid email address")
    return email


def validate_password(value: str) -> str:
    if not isinstance(value, str) or len(value) < 8:
        raise ValidationError("password must be at least 8 characters")
    return value


def validate_nickname(value: str) -> str:
    nickname = (value or "").strip()
    if not 1 <= len(nickname) <= 40:
        raise ValidationError("nickname must be between 1 and 40 characters")
    return nickname


def validate_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value or "")
    except ValueError as exc:
        raise ValidationError("date must use YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise ValidationError("date must use YYYY-MM-DD format")
    return value


def validate_month(value: str) -> str:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value or ""):
        raise ValidationError("month must use YYYY-MM format")
    return value


def validate_upload(filename: str, content_type: str) -> tuple[str, str]:
    if not filename or "." not in filename:
        raise ValidationError("filename must include an extension")
    extension = filename.rsplit(".", 1)[1].lower()
    expected_extension = ALLOWED_CONTENT_TYPES.get(content_type)
    if expected_extension is None:
        raise ValidationError("contentType must be image/jpeg or image/png")
    if extension not in {"jpg", "jpeg", "png"}:
        raise ValidationError("filename extension must be jpg, jpeg, or png")
    if expected_extension == "png" and extension != "png":
        raise ValidationError("filename extension does not match contentType")
    if expected_extension == "jpg" and extension not in {"jpg", "jpeg"}:
        raise ValidationError("filename extension does not match contentType")
    return extension, content_type


def user_upload_prefix(user_id: str) -> str:
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return f"uploads/{digest}/"


def validate_owned_s3_key(user_id: str, s3_key: str) -> str:
    if not s3_key or not s3_key.startswith(user_upload_prefix(user_id)):
        raise ValidationError("s3Key does not belong to userId")
    return s3_key


def daily_entry_id(user_id: str, entry_date: str) -> str:
    return hashlib.sha256(f"{user_id}:{entry_date}".encode("utf-8")).hexdigest()
