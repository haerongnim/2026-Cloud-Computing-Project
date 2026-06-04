import io
import tempfile
import unittest
from pathlib import Path

from services.backend import MockBackend
from services.settings import Settings
from services.validation import ValidationError, daily_entry_id, normalize_email, validate_month, validate_upload

class FakeUpload:
    def __init__(self, content: bytes):
        self.content = content

    def save(self, target):
        Path(target).write_bytes(self.content)


class ValidationTests(unittest.TestCase):
    def test_normalizes_demo_identity(self):
        self.assertEqual(normalize_email(" Demo@Example.COM "), "demo@example.com")

    def test_rejects_invalid_identity(self):
        with self.assertRaises(ValidationError):
            normalize_email("not-an-email")

    def test_validates_month_and_upload_type(self):
        self.assertEqual(validate_month("2026-06"), "2026-06")
        self.assertEqual(validate_upload("selfie.jpeg", "image/jpeg"), ("jpeg", "image/jpeg"))
        with self.assertRaises(ValidationError):
            validate_upload("selfie.png", "image/jpeg")


class MockBackendTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = Settings(local_data_dir=self.tempdir.name)
        self.backend = MockBackend(self.settings)
        self.user_id = "demo@example.com"

    def tearDown(self):
        self.tempdir.cleanup()

    def _upload(self, content=b"image"):
        presign = self.backend.issue_upload(self.user_id, "jpg", "image/jpeg")
        self.backend.store_upload(presign["s3Key"], FakeUpload(content))
        return presign["s3Key"]

    def test_mock_pipeline_populates_diary_and_email_log(self):
        s3_key = self._upload()
        accepted = self.backend.create_entry(self.user_id, "2026-06-01", s3_key)
        self.assertEqual(accepted["status"], "PROCESSING")

        detail = self.backend.get_entry(self.user_id, accepted["entryId"])
        self.assertEqual(detail["status"], "EMAIL_SENT")
        self.assertTrue(detail["playlist"])
        listed = self.backend.list_entries(self.user_id, "2026-06")[0]
        self.assertEqual(listed["entryId"], accepted["entryId"])
        self.assertEqual(listed["imageUrl"], detail["imageUrl"])
        self.assertTrue(self.backend.email_log_path.read_text())

    def test_replacement_reuses_daily_id_and_deletes_previous_image(self):
        first_key = self._upload(b"first")
        first = self.backend.create_entry(self.user_id, "2026-06-01", first_key)
        second_key = self._upload(b"second")
        second = self.backend.create_entry(self.user_id, "2026-06-01", second_key)
        self.assertEqual(first["entryId"], second["entryId"])
        self.assertNotEqual(first["requestId"], second["requestId"])
        self.assertFalse((self.backend.upload_root / first_key).exists())
        self.assertTrue((self.backend.upload_root / second_key).exists())

    def test_rejects_foreign_upload_key(self):
        s3_key = self._upload()
        with self.assertRaises(ValidationError):
            self.backend.create_entry("other@example.com", "2026-06-01", s3_key)

    def test_rejects_mock_upload_path_traversal(self):
        with self.assertRaisesRegex(Exception, "invalid mock upload key"):
            self.backend.store_upload("../../outside.jpg", FakeUpload(b"image"))

    def test_daily_id_is_stable(self):
        self.assertEqual(daily_entry_id(self.user_id, "2026-06-01"), daily_entry_id(self.user_id, "2026-06-01"))


try:
    from app import create_app
except ModuleNotFoundError:
    create_app = None


@unittest.skipIf(create_app is None, "Flask is not installed")
class FlaskApiTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.settings = Settings(local_data_dir=self.tempdir.name)
        self.backend = MockBackend(self.settings)
        self.client = create_app(self.settings, self.backend).test_client()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_full_http_mock_flow(self):
        presign = self.client.post(
            "/v1/uploads/presign",
            json={"filename": "selfie.jpg", "contentType": "image/jpeg"},
        ).get_json()
        response = self.client.post(
            presign["uploadUrl"].removeprefix("/api"),
            data={"file": (io.BytesIO(b"image"), "selfie.jpg")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 204)

        accepted = self.client.post(
            "/v1/entries",
            json={"date": "2026-06-01", "s3Key": presign["s3Key"]},
        )
        self.assertEqual(accepted.status_code, 202)
        entry_id = accepted.get_json()["entryId"]
        detail = self.client.get(f"/v1/entries/{entry_id}")
        self.assertEqual(detail.get_json()["status"], "EMAIL_SENT")
        entries = self.client.get("/v1/entries?month=2026-06").get_json()["entries"]
        self.assertEqual(len(entries), 1)
        self.assertIn("imageUrl", entries[0])
        image = self.client.get(entries[0]["imageUrl"].removeprefix("/api"))
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.data, b"image")

    def test_anonymous_cookie_isolates_diaries(self):
        first = self.client.get("/v1/auth/session")
        second_client = create_app(self.settings, self.backend).test_client()
        second = second_client.get("/v1/auth/session")
        self.assertIsNone(first.get_json()["user"])
        self.assertIsNone(second.get_json()["user"])

        presign = self.client.post(
            "/v1/uploads/presign",
            json={"filename": "selfie.jpg", "contentType": "image/jpeg"},
        ).get_json()
        self.client.post(
            presign["uploadUrl"].removeprefix("/api"),
            data={"file": (io.BytesIO(b"image"), "selfie.jpg")},
            content_type="multipart/form-data",
        )
        self.client.post("/v1/entries", json={"date": "2026-06-01", "s3Key": presign["s3Key"]})

        self.assertEqual(len(self.client.get("/v1/entries?month=2026-06").get_json()["entries"]), 1)
        self.client.post(
            "/v1/auth/signup",
            json={"email": "account.com", "password": "password123", "nickname": "Account"},
        )
        self.assertEqual(self.client.get("/v1/entries?month=2026-06").get_json()["entries"], [])
        self.client.post("/v1/auth/logout")
        self.assertEqual(len(self.client.get("/v1/entries?month=2026-06").get_json()["entries"]), 1)
        self.assertEqual(second_client.get("/v1/entries?month=2026-06").get_json()["entries"], [])

    def test_signup_login_and_logout_switch_identity(self):
        anonymous_session = self.client.get("/v1/auth/session")
        self.assertIn("session=", anonymous_session.headers["Set-Cookie"])

        signup = self.client.post(
            "/v1/auth/signup",
            json={"email": "Person@Example.COM", "password": "password123", "nickname": "Person"},
        )
        self.assertEqual(signup.status_code, 201)
        user = signup.get_json()["user"]
        self.assertTrue(user["userId"].startswith("user:"))
        self.assertEqual(user["email"], "person@example.com")

        with self.backend._connect() as connection:
            stored = connection.execute("SELECT password_hash FROM users WHERE email = ?", (user["email"],)).fetchone()
        self.assertNotEqual(stored["password_hash"], "password123")

        self.assertEqual(self.client.post("/v1/auth/logout").status_code, 204)
        self.assertIsNone(self.client.get("/v1/auth/session").get_json()["user"])
        login = self.client.post(
            "/v1/auth/login",
            json={"email": "person@example.com", "password": "password123"},
        )
        self.assertEqual(login.get_json()["user"]["userId"], user["userId"])

    def test_rejects_invalid_request(self):
        response = self.client.post("/v1/uploads/presign", json={"userId": "bad"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "validation_error")


if __name__ == "__main__":
    unittest.main()
