import importlib.util
import json
import os
import re
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class FakeTable:
    def __init__(self, items):
        if isinstance(items, dict) and "entry_id" in items:
            self.items = {items["entry_id"]: items}
        else:
            self.items = items
        self.updates = []

    def get_item(self, **kwargs):
        key = kwargs.get("Key", {}).get("entry_id")
        return {"Item": dict(self.items.get(key, {}))}

    def update_item(self, **kwargs):
        self.updates.append(kwargs)
        values = kwargs.get("ExpressionAttributeValues", {})
        match = re.search(r"#st = (:\w+)", kwargs.get("UpdateExpression", ""))
        if match:
            key = kwargs.get("Key", {}).get("entry_id")
            if key in self.items:
                self.items[key]["status"] = values[match.group(1)]
        return {}


class FakeResource:
    def __init__(self, table):
        self.table = table

    def Table(self, name):
        return self.table


class FakeClient:
    class exceptions:
        class InvalidS3ObjectException(Exception):
            pass

    def __init__(self):
        self.calls = []

    def detect_faces(self, **kwargs):
        return {"FaceDetails": [{"Emotions": [{"Type": "HAPPY", "Confidence": 98.5}, {"Type": "CALM", "Confidence": 1.5}]}]}

    def publish(self, **kwargs):
        self.calls.append(kwargs)

    def send_email(self, **kwargs):
        self.calls.append(kwargs)

    def get_secret_value(self, **kwargs):
        return {"SecretString": '{"client_id":"id","client_secret":"secret"}'}


def load_handler(name, table, clients, env=None):
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = lambda service, region_name=None: clients.setdefault(service, FakeClient())
    fake_boto3.resource = lambda service, region_name=None: FakeResource(table)
    fake_botocore = types.ModuleType("botocore")
    fake_exceptions = types.ModuleType("botocore.exceptions")
    fake_exceptions.ClientError = ClientError
    fake_botocore.exceptions = fake_exceptions
    sys.modules["boto3"] = fake_boto3
    sys.modules["botocore"] = fake_botocore
    sys.modules["botocore.exceptions"] = fake_exceptions
    for key, value in (env or {}).items():
        os.environ[key] = value
    path = ROOT / "lambda" / name / "handler.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AnalyzeHandlerTests(unittest.TestCase):
    def test_advances_matching_request(self):
        table = FakeTable({"entry_id": "entry", "request_id": "request", "status": "PROCESSING"})
        module = load_handler("analyze_emotion", table, {})
        event = {"entry_id": "entry", "request_id": "request", "user_id": "demo@example.com", "date": "2026-06-01", "s3_bucket": "bucket", "s3_key": "key"}
        response = module.lambda_handler(event, None)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(table.items["entry"]["status"], "EMOTION_ANALYZED")
        self.assertEqual(module.AWS_REGION, "ap-northeast-2")

    def test_ignores_stale_request(self):
        table = FakeTable({"entry_id": "entry", "request_id": "new", "status": "PROCESSING"})
        module = load_handler("analyze_emotion", table, {})
        event = {"entry_id": "entry", "request_id": "old", "user_id": "demo@example.com", "date": "2026-06-01", "s3_bucket": "bucket", "s3_key": "key"}
        module.lambda_handler(event, None)
        self.assertFalse(table.updates)


class RecommendHandlerTests(unittest.TestCase):
    def test_processes_transition_and_publishes_sns(self):
        table = FakeTable({"entry_id": "entry", "request_id": "request", "status": "EMOTION_ANALYZED"})
        clients = {}
        module = load_handler("recommend_music", table, clients, {"SNS_TOPIC_ARN": "topic", "SPOTIFY_SECRET_ARN": "secret"})
        module._search_spotify_tracks = lambda genre, emotion: [{"name": "Happy", "artist": "Artist"}]
        event = {"Records": [{"eventName": "MODIFY", "dynamodb": {"OldImage": {"status": {"S": "PROCESSING"}}, "NewImage": {"entry_id": {"S": "entry"}, "request_id": {"S": "request"}, "user_id": {"S": "demo@example.com"}, "date": {"S": "2026-06-01"}, "emotion": {"S": "HAPPY"}, "genre": {"S": "pop"}, "status": {"S": "EMOTION_ANALYZED"}}}}]}
        self.assertEqual(module.lambda_handler(event, None), {"processed": 1})
        self.assertEqual(table.items["entry"]["status"], "PLAYLIST_READY")
        self.assertEqual(len(clients["sns"].calls), 1)


class SendDiaryHandlerTests(unittest.TestCase):
    def test_sends_email_and_marks_entry_sent(self):
        table = FakeTable({
            "entry": {"entry_id": "entry", "request_id": "request", "status": "PLAYLIST_READY", "user_id": "user:123"},
            "account:user:123": {"entry_id": "account:user:123", "email": "demo@example.com"}
        })
        clients = {}
        module = load_handler("send_diary", table, clients, {"SES_FROM_EMAIL": "sender@example.com"})
        message = {"entry_id": "entry", "request_id": "request", "user_id": "user:123", "date": "2026-06-01", "emotion": "HAPPY", "genre": "pop", "tracks": [{"name": "Happy", "artist": "Artist", "spotifyUrl": "https://example.com"}]}
        event = {"Records": [{"Sns": {"Message": json.dumps(message)}}]}
        self.assertEqual(module.lambda_handler(event, None), {"emails_sent": 1})
        self.assertEqual(table.items["entry"]["status"], "EMAIL_SENT")
        self.assertEqual(len(clients["ses"].calls), 1)
        email = clients["ses"].calls[0]["Message"]
        self.assertIn("😊 행복", email["Subject"]["Data"])
        self.assertIn("🎵 오늘의 감정 다이어리", email["Body"]["Html"]["Data"])
        self.assertIn("🎧 추천 플레이리스트", email["Body"]["Text"]["Data"])

    def test_escapes_track_fields_in_html_email(self):
        table = FakeTable({
            "entry": {"entry_id": "entry", "request_id": "request", "status": "PLAYLIST_READY", "user_id": "user:123"},
            "account:user:123": {"entry_id": "account:user:123", "email": "demo@example.com"}
        })
        module = load_handler("send_diary", table, {}, {"SES_FROM_EMAIL": "sender@example.com"})
        message = {"date": "2026-06-01", "emotion": "HAPPY", "genre": "pop", "tracks": [{"name": "<script>", "artist": "A&B", "spotifyUrl": "https://example.com/?a=1&b=2"}]}
        html_body = module._build_email_html(message)
        self.assertNotIn("<script>", html_body)
        self.assertIn("&lt;script&gt;", html_body)
        self.assertIn("A&amp;B", html_body)
        self.assertIn("a=1&amp;b=2", html_body)

    def test_ignores_duplicate_message(self):
        table = FakeTable({
            "entry": {"entry_id": "entry", "request_id": "request", "status": "EMAIL_SENT", "user_id": "user:123"},
            "account:user:123": {"entry_id": "account:user:123", "email": "demo@example.com"}
        })
        clients = {}
        module = load_handler("send_diary", table, clients, {"SES_FROM_EMAIL": "sender@example.com"})
        message = {"entry_id": "entry", "request_id": "request", "user_id": "user:123", "date": "2026-06-01", "emotion": "HAPPY", "tracks": []}
        event = {"Records": [{"Sns": {"Message": json.dumps(message)}}]}
        self.assertEqual(module.lambda_handler(event, None), {"emails_sent": 0})
        self.assertFalse(clients["ses"].calls)


if __name__ == "__main__":
    unittest.main()
