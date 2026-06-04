import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_mode: str = os.environ.get("APP_MODE", "mock").lower()
    aws_region: str = os.environ.get("AWS_REGION", "ap-northeast-2")
    s3_bucket: str = os.environ.get("S3_BUCKET", "emotion-diary-images")
    dynamodb_table: str = os.environ.get("DYNAMODB_TABLE", "emotion-diary")
    analyze_lambda_name: str = os.environ.get("ANALYZE_LAMBDA_NAME", "analyze_emotion")
    local_data_dir: str = os.environ.get("LOCAL_DATA_DIR", ".local")
    presign_expiry_seconds: int = int(os.environ.get("PRESIGN_EXPIRY_SECONDS", "300"))
    max_upload_size_bytes: int = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", str(5 * 1024 * 1024)))
    session_secret: str = os.environ.get("SESSION_SECRET", "change-me-for-production")
    session_cookie_secure: bool = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() == "true"
