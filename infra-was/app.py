import os
from uuid import uuid4

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from services.emotion_service import analyze_emotion
from services.music_service import recommend_music
from services.diary_service import create_diary

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE_BYTES


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_mimetype(mimetype):
    return isinstance(mimetype, str) and mimetype.startswith("image/")


@app.route("/")
def home():
    return jsonify({"message": "Server Running", "status": "healthy"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/analyze", methods=["POST"])
def analyze():

    if "image" not in request.files:
        return jsonify({"error": "image file is required"}), 400

    file = request.files["image"]

    email = request.form.get("email")

    if file.filename == "":
        return jsonify({"error": "empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "invalid file type"}), 400

    if not allowed_mimetype(file.mimetype):
        return jsonify({"error": "invalid mimetype"}), 400

    filename = secure_filename(file.filename)

    unique_filename = f"{uuid4()}_{filename}"

    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)

    try:
        file.save(filepath)

        emotion_result = analyze_emotion(filepath)

        playlist = recommend_music(emotion_result["emotion"])

        diary_item = create_diary(
            email=email,
            emotion_result=emotion_result,
            playlist=playlist,
            image_filename=unique_filename,
        )
    except Exception:
        return jsonify({"error": "internal error"}), 500

    return jsonify(
        {
            "message": "analysis completed",
            "email": email,
            "emotion": emotion_result,
            "playlist": playlist,
            "saved_diary": diary_item,
            "filename": unique_filename,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
