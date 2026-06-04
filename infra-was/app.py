import logging
from uuid import uuid4

from flask import Flask, jsonify, request, send_file, session
from flask_cors import CORS
from werkzeug.exceptions import RequestEntityTooLarge

from services.backend import BackendError, MockBackend, create_backend
from services.settings import Settings
from services.validation import (
    ValidationError,
    normalize_email,
    validate_date,
    validate_month,
    validate_nickname,
    validate_password,
    validate_upload,
)


def _error(code: str, message: str, status_code: int):
    return jsonify({"error": {"code": code, "message": message}}), status_code


def create_app(settings: Settings | None = None, backend=None) -> Flask:
    settings = settings or Settings()
    backend = backend or create_backend(settings)
    app = Flask(__name__)
    CORS(app, supports_credentials=True, origins=["http://localhost:5173"])
    app.config["MAX_CONTENT_LENGTH"] = settings.max_upload_size_bytes
    app.config["SECRET_KEY"] = settings.session_secret
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = settings.session_cookie_secure

    def current_user_id() -> str:
        if "anonymous_user_id" not in session:
            session["anonymous_user_id"] = f"anonymous:{uuid4()}"
        return session.get("authenticated_user_id", session["anonymous_user_id"])

    @app.errorhandler(ValidationError)
    def handle_validation_error(error):
        return _error("validation_error", str(error), 400)

    @app.errorhandler(BackendError)
    def handle_backend_error(error):
        return _error(error.code, error.message, error.status_code)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_error_value):
        return _error("upload_too_large", "uploaded file exceeds size limit", 413)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled request error: %s", error)
        return _error("internal_error", "internal server error", 500)

    @app.get("/")
    def home():
        return jsonify({"message": "Emotion Diary server", "status": "healthy"})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "mode": settings.app_mode, "region": settings.aws_region})

    @app.get("/v1/auth/session")
    def auth_session():
        user_id = session.get("authenticated_user_id")
        user = backend.get_user(user_id) if user_id else None
        if user_id and not user:
            session.pop("authenticated_user_id", None)
        current_user_id()
        return jsonify({"user": user})

    @app.post("/v1/auth/signup")
    def signup():
        data = request.get_json(silent=True) or {}
        user = backend.signup(
            normalize_email(data.get("email")),
            validate_password(data.get("password")),
            validate_nickname(data.get("nickname")),
        )
        session["authenticated_user_id"] = user["userId"]
        current_user_id()
        return jsonify({"user": user}), 201

    @app.post("/v1/auth/login")
    def login():
        data = request.get_json(silent=True) or {}
        user = backend.authenticate(
            normalize_email(data.get("email")),
            validate_password(data.get("password")),
        )
        session["authenticated_user_id"] = user["userId"]
        current_user_id()
        return jsonify({"user": user})

    @app.post("/v1/auth/logout")
    def logout():
        session.pop("authenticated_user_id", None)
        current_user_id()
        return "", 204

    @app.post("/v1/uploads/presign")
    def presign_upload():
        data = request.get_json(silent=True) or {}
        extension, content_type = validate_upload(data.get("filename"), data.get("contentType"))
        return jsonify(backend.issue_upload(current_user_id(), extension, content_type))

    @app.post("/v1/mock/uploads/<path:s3_key>")
    def mock_upload(s3_key):
        if not isinstance(backend, MockBackend):
            return _error("not_found", "route is available only in mock mode", 404)
        uploaded_file = request.files.get("file")
        if not uploaded_file:
            return _error("validation_error", "file is required", 400)
        backend.store_upload(s3_key, uploaded_file)
        return "", 204

    @app.get("/v1/mock/images/<path:s3_key>")
    def mock_image(s3_key):
        if not isinstance(backend, MockBackend):
            return _error("not_found", "route is available only in mock mode", 404)
        image_path = backend.get_image_path(s3_key)
        if not image_path.is_file():
            return _error("not_found", "image not found", 404)
        return send_file(image_path)

    @app.post("/v1/entries")
    def create_entry():
        data = request.get_json(silent=True) or {}
        entry_date = validate_date(data.get("date"))
        s3_key = data.get("s3Key")
        if not isinstance(s3_key, str):
            raise ValidationError("s3Key is required")
        return jsonify(backend.create_entry(current_user_id(), entry_date, s3_key)), 202

    @app.get("/v1/entries")
    def list_entries():
        month = validate_month(request.args.get("month"))
        return jsonify({"entries": backend.list_entries(current_user_id(), month)})

    @app.get("/v1/entries/<entry_id>")
    def get_entry(entry_id):
        entry = backend.get_entry(current_user_id(), entry_id)
        if not entry:
            return _error("not_found", "entry not found", 404)
        return jsonify(entry)

    return app


logging.basicConfig(level=logging.INFO)
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
