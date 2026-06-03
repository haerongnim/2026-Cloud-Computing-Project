import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from werkzeug.security import check_password_hash, generate_password_hash

from services.settings import Settings
from services.validation import daily_entry_id, user_upload_prefix, validate_owned_s3_key


logger = logging.getLogger(__name__)


class BackendError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 500):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Unsupported JSON value: {type(value)!r}")


def serialize_entry(entry: dict, image_url: str | None = None) -> dict:
    result = {
        "entryId": entry["entry_id"],
        "requestId": entry["request_id"],
        "userId": entry["user_id"],
        "date": entry["date"],
        "status": entry["status"],
        "emotion": entry.get("emotion"),
        "confidence": entry.get("confidence"),
        "genre": entry.get("genre"),
        "playlist": entry.get("playlist", []),
        "createdAt": entry["created_at"],
        "updatedAt": entry["updated_at"],
    }
    if image_url:
        result["imageUrl"] = image_url
    return result


def serialize_user(user: dict) -> dict:
    return {
        "userId": user["user_id"],
        "email": user["email"],
        "nickname": user["nickname"],
    }


def _account_key(user_id: str) -> str:
    return f"account:{user_id}"


def _email_key(email: str) -> str:
    return f"account-email:{hashlib.sha256(email.encode('utf-8')).hexdigest()}"


class AwsBackend:
    def __init__(self, settings: Settings):
        import boto3
        from botocore.config import Config

        self.settings = settings
        self.s3 = boto3.client(
            "s3",
            region_name=settings.aws_region,
            endpoint_url=f"https://s3.{settings.aws_region}.amazonaws.com",
            config=Config(signature_version="s3v4"),
        )
        self.lambda_client = boto3.client("lambda", region_name=settings.aws_region)
        self.table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(
            settings.dynamodb_table
        )

    def signup(self, email: str, password: str, nickname: str) -> dict:
        from botocore.exceptions import ClientError

        user_id = f"user:{uuid4()}"
        account = {
            "entry_id": _account_key(user_id),
            "record_type": "account",
            "user_id": user_id,
            "email": email,
            "nickname": nickname,
            "password_hash": generate_password_hash(password),
            "created_at": _now(),
        }
        email_lookup = {
            "entry_id": _email_key(email),
            "record_type": "account_email",
            "user_id": user_id,
        }
        try:
            self.table.put_item(Item=email_lookup, ConditionExpression="attribute_not_exists(entry_id)")
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                raise BackendError("email_in_use", "email is already registered", 409) from error
            raise
        try:
            self.table.put_item(Item=account)
        except Exception:
            self.table.delete_item(Key={"entry_id": email_lookup["entry_id"]})
            raise
        return serialize_user(account)

    def authenticate(self, email: str, password: str) -> dict:
        lookup = self.table.get_item(Key={"entry_id": _email_key(email)}).get("Item")
        account = self._get_account(lookup.get("user_id")) if lookup else None
        if not account or not check_password_hash(account["password_hash"], password):
            raise BackendError("invalid_credentials", "invalid email or password", 401)
        return serialize_user(account)

    def get_user(self, user_id: str) -> dict | None:
        account = self._get_account(user_id)
        return serialize_user(account) if account else None

    def _get_account(self, user_id: str | None) -> dict | None:
        if not user_id:
            return None
        account = self.table.get_item(Key={"entry_id": _account_key(user_id)}).get("Item")
        return account if account and account.get("record_type") == "account" else None

    def issue_upload(self, user_id: str, extension: str, content_type: str) -> dict:
        s3_key = f"{user_upload_prefix(user_id)}{uuid4()}.{extension}"
        result = self.s3.generate_presigned_post(
            Bucket=self.settings.s3_bucket,
            Key=s3_key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, self.settings.max_upload_size_bytes],
            ],
            ExpiresIn=self.settings.presign_expiry_seconds,
        )
        return {
            "uploadUrl": result["url"],
            "fields": result["fields"],
            "s3Key": s3_key,
            "expiresIn": self.settings.presign_expiry_seconds,
            "maxSizeBytes": self.settings.max_upload_size_bytes,
        }

    def create_entry(self, user_id: str, entry_date: str, s3_key: str) -> dict:
        validate_owned_s3_key(user_id, s3_key)
        self._verify_object(s3_key)

        entry_id = daily_entry_id(user_id, entry_date)
        previous = self.table.get_item(Key={"entry_id": entry_id}).get("Item")
        timestamp = _now()
        entry = {
            "entry_id": entry_id,
            "request_id": str(uuid4()),
            "user_id": user_id,
            "date": entry_date,
            "s3_key": s3_key,
            "status": "PROCESSING",
            "playlist": [],
            "created_at": previous.get("created_at", timestamp) if previous else timestamp,
            "updated_at": timestamp,
        }
        self.table.put_item(Item=entry)

        try:
            response = self.lambda_client.invoke(
                FunctionName=self.settings.analyze_lambda_name,
                InvocationType="Event",
                Payload=json.dumps(
                    {
                        "entry_id": entry_id,
                        "request_id": entry["request_id"],
                        "user_id": user_id,
                        "date": entry_date,
                        "s3_bucket": self.settings.s3_bucket,
                        "s3_key": s3_key,
                    }
                ).encode("utf-8"),
            )
            if response.get("StatusCode") != 202:
                raise BackendError("lambda_rejected", "analysis Lambda did not accept the request")
        except Exception:
            if previous:
                self.table.put_item(Item=previous)
            else:
                self.table.delete_item(Key={"entry_id": entry_id})
            self._delete_object(s3_key)
            raise

        old_s3_key = previous.get("s3_key") if previous else None
        if old_s3_key and old_s3_key != s3_key:
            self._delete_object(old_s3_key)
        return serialize_entry(entry)

    def list_entries(self, user_id: str, month: str) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        response = self.table.query(
            IndexName="user-date-index",
            KeyConditionExpression=Key("user_id").eq(user_id)
            & Key("date").between(f"{month}-01", f"{month}-31"),
        )
        return [
            serialize_entry(item, image_url=self._image_url(item["s3_key"]))
            for item in response.get("Items", [])
        ]

    def get_entry(self, user_id: str, entry_id: str) -> dict | None:
        entry = self.table.get_item(Key={"entry_id": entry_id}).get("Item")
        if not entry or entry.get("user_id") != user_id:
            return None
        return serialize_entry(entry, image_url=self._image_url(entry["s3_key"]))

    def _image_url(self, s3_key: str) -> str:
        return self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.settings.s3_bucket, "Key": s3_key},
            ExpiresIn=self.settings.presign_expiry_seconds,
        )

    def _verify_object(self, s3_key: str) -> None:
        try:
            metadata = self.s3.head_object(Bucket=self.settings.s3_bucket, Key=s3_key)
        except Exception as exc:
            raise BackendError("upload_not_found", "uploaded S3 object was not found", 400) from exc
        if metadata.get("ContentLength", 0) > self.settings.max_upload_size_bytes:
            raise BackendError("upload_too_large", "uploaded file exceeds size limit", 400)
        if metadata.get("ContentType") not in {"image/jpeg", "image/png"}:
            raise BackendError("invalid_content_type", "uploaded file must be JPEG or PNG", 400)

    def _delete_object(self, s3_key: str) -> None:
        try:
            self.s3.delete_object(Bucket=self.settings.s3_bucket, Key=s3_key)
        except Exception:
            logger.warning("Failed to delete S3 object %s", s3_key, exc_info=True)


class MockBackend:
    EMOTIONS = ("HAPPY", "SAD", "CALM", "ANGRY")
    PLAYLISTS = {
        "HAPPY": [{"name": "Happy", "artist": "Pharrell Williams", "spotifyUrl": ""}],
        "SAD": [{"name": "Someone Like You", "artist": "Adele", "spotifyUrl": ""}],
        "CALM": [{"name": "Paris in the Rain", "artist": "Lauv", "spotifyUrl": ""}],
        "ANGRY": [{"name": "Numb", "artist": "Linkin Park", "spotifyUrl": ""}],
    }

    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = Path(settings.local_data_dir)
        self.upload_root = self.root / "uploads"
        self.database_path = self.root / "emotion-diary.sqlite3"
        self.email_log_path = self.root / "emails.log"
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def signup(self, email: str, password: str, nickname: str) -> dict:
        user_id = f"user:{uuid4()}"
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO users (user_id, email, password_hash, nickname) VALUES (?, ?, ?, ?)",
                    (user_id, email, generate_password_hash(password), nickname),
                )
        except sqlite3.IntegrityError as error:
            raise BackendError("email_in_use", "email is already registered", 409) from error
        return {"userId": user_id, "email": email, "nickname": nickname}

    def authenticate(self, email: str, password: str) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id, email, password_hash, nickname FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            raise BackendError("invalid_credentials", "invalid email or password", 401)
        return {"userId": row["user_id"], "email": row["email"], "nickname": row["nickname"]}

    def get_user(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id, email, nickname FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
        return dict(row) if row else None

    def issue_upload(self, user_id: str, extension: str, content_type: str) -> dict:
        s3_key = f"{user_upload_prefix(user_id)}{uuid4()}.{extension}"
        return {
            "uploadUrl": f"/api/v1/mock/uploads/{quote(s3_key, safe='/')}",
            "fields": {},
            "s3Key": s3_key,
            "expiresIn": self.settings.presign_expiry_seconds,
            "maxSizeBytes": self.settings.max_upload_size_bytes,
        }

    def store_upload(self, s3_key: str, uploaded_file) -> None:
        target = self._upload_path(s3_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        uploaded_file.save(target)
        if target.stat().st_size > self.settings.max_upload_size_bytes:
            target.unlink(missing_ok=True)
            raise BackendError("upload_too_large", "uploaded file exceeds size limit", 413)

    def create_entry(self, user_id: str, entry_date: str, s3_key: str) -> dict:
        validate_owned_s3_key(user_id, s3_key)
        image_path = self.upload_root / s3_key
        if not image_path.is_file():
            raise BackendError("upload_not_found", "uploaded mock object was not found", 400)

        entry_id = daily_entry_id(user_id, entry_date)
        request_id = str(uuid4())
        timestamp = _now()
        previous = self._get_row(entry_id)
        emotion = self.EMOTIONS[int(hashlib.sha256(s3_key.encode()).hexdigest(), 16) % len(self.EMOTIONS)]
        entry = {
            "entry_id": entry_id,
            "request_id": request_id,
            "user_id": user_id,
            "date": entry_date,
            "s3_key": s3_key,
            "status": "EMAIL_SENT",
            "emotion": emotion,
            "confidence": 95.0,
            "genre": emotion.lower(),
            "playlist": self.PLAYLISTS[emotion],
            "created_at": previous.get("created_at", timestamp) if previous else timestamp,
            "updated_at": timestamp,
        }
        self._put_row(entry)
        with self.email_log_path.open("a", encoding="utf-8") as log:
            log.write(json.dumps({"entryId": entry_id, "userId": user_id, "emotion": emotion}) + "\n")

        old_s3_key = previous.get("s3_key") if previous else None
        if old_s3_key and old_s3_key != s3_key:
            (self.upload_root / old_s3_key).unlink(missing_ok=True)

        accepted = dict(entry)
        accepted["status"] = "PROCESSING"
        return serialize_entry(accepted)

    def list_entries(self, user_id: str, month: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM entries WHERE user_id = ? AND date LIKE ? ORDER BY date",
                (user_id, f"{month}-%"),
            ).fetchall()
        entries = [json.loads(row["payload"]) for row in rows]
        return [
            serialize_entry(entry, image_url=self._image_url(entry["s3_key"]))
            for entry in entries
        ]

    def get_entry(self, user_id: str, entry_id: str) -> dict | None:
        entry = self._get_row(entry_id)
        if not entry or entry.get("user_id") != user_id:
            return None
        return serialize_entry(entry, image_url=self._image_url(entry["s3_key"]))

    def _image_url(self, s3_key: str) -> str:
        return f"/api/v1/mock/images/{quote(s3_key, safe='/')}"

    def get_image_path(self, s3_key: str) -> Path:
        return self._upload_path(s3_key)

    def _upload_path(self, s3_key: str) -> Path:
        target = (self.upload_root / s3_key).resolve()
        try:
            target.relative_to(self.upload_root.resolve())
        except ValueError as exc:
            raise BackendError("invalid_upload_key", "invalid mock upload key", 400) from exc
        return target

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS entries (
                    entry_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS entries_user_date ON entries (user_id, date)")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    nickname TEXT NOT NULL
                )
                """
            )

    def _get_row(self, entry_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM entries WHERE entry_id = ?", (entry_id,)
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    def _put_row(self, entry: dict) -> None:
        payload = json.dumps(entry, default=_json_default)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO entries (entry_id, user_id, date, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(entry_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    date = excluded.date,
                    payload = excluded.payload
                """,
                (entry["entry_id"], entry["user_id"], entry["date"], payload),
            )


def create_backend(settings: Settings | None = None):
    settings = settings or Settings()
    if settings.app_mode == "aws":
        return AwsBackend(settings)
    if settings.app_mode == "mock":
        return MockBackend(settings)
    raise RuntimeError("APP_MODE must be 'mock' or 'aws'")
