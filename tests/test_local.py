"""
로컬 테스트 - lambda/ 폴더에서 직접 로드 (lambda_/ 복사 불필요)
실행 위치: 프로젝트 루트 (2026-Cloud-Computing-Project/)
명령어:    python3 tests/test_local.py
"""
import json, sys, os, unittest, importlib.util
from unittest.mock import MagicMock, patch

sys.modules["boto3"] = MagicMock()
import boto3

# tests/test_local.py 기준으로 한 단계 위 = 프로젝트 루트
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_handler(subdir):
    """lambda/<subdir>/handler.py 를 직접 로드 (lambda 예약어 우회)"""
    path = os.path.join(ROOT, "lambda", subdir, "handler.py")
    key  = f"_handler_{subdir}"
    if key in sys.modules:
        del sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 공통 픽스처 ───────────────────────────────────────────────

def _rek_resp(emotion="HAPPY", conf=97.5):
    return {"FaceDetails": [{"Emotions": [
        {"Type": emotion, "Confidence": conf},
        {"Type": "CALM",  "Confidence": 1.5},
    ]}]}

def _stream_event(entry_id, user_id, emotion, genre, status="EMOTION_ANALYZED"):
    return {"Records": [{"eventName": "INSERT", "dynamodb": {"NewImage": {
        "entry_id":  {"S": entry_id},  "user_id":   {"S": user_id},
        "genre":     {"S": genre},     "emotion":   {"S": emotion},
        "timestamp": {"S": "2026-05-08T10:00:00+00:00"},
        "status":    {"S": status},
    }}}]}

FAKE_TRACKS = [{"name": "Happy", "artist": "Pharrell Williams",
                "album": "Despicable Me 2",
                "spotify_url": "https://spotify.com/x", "preview_url": ""}]


# ══ 테스트 1: analyze_emotion/handler.py ══════════════════════

class TestAnalyzeEmotion(unittest.TestCase):

    def _setup(self, rek_resp):
        mock_rek   = MagicMock()
        mock_table = MagicMock()
        mock_rek.detect_faces.return_value = rek_resp
        mock_rek.exceptions.InvalidS3ObjectException = Exception
        boto3.client.return_value   = mock_rek
        boto3.resource.return_value = MagicMock()
        boto3.resource.return_value.Table.return_value = mock_table
        return mock_rek, mock_table

    def _call(self, rek_resp, event):
        self._setup(rek_resp)
        m = load_handler("analyze_emotion")
        return m.lambda_handler(event, {}), m

    def test_happy_mapped_to_pop(self):
        result, _ = self._call(_rek_resp("HAPPY", 97.5),
            {"user_id": "u@t.com", "s3_bucket": "b", "s3_key": "k"})
        body = json.loads(result["body"])
        self.assertEqual(result["statusCode"], 200)
        self.assertEqual(body["emotion"], "HAPPY")
        self.assertEqual(body["genre"],   "pop")
        print("  [PASS] test_happy_mapped_to_pop")

    def test_sad_mapped_to_sad(self):
        result, _ = self._call(_rek_resp("SAD", 88.0),
            {"user_id": "u@t.com", "s3_bucket": "b", "s3_key": "k"})
        self.assertEqual(json.loads(result["body"])["genre"], "sad")
        print("  [PASS] test_sad_mapped_to_sad")

    def test_no_face_returns_400(self):
        result, _ = self._call({"FaceDetails": []},
            {"user_id": "u", "s3_bucket": "b", "s3_key": "k"})
        self.assertEqual(result["statusCode"], 400)
        print("  [PASS] test_no_face_returns_400")

    def test_missing_params_returns_400(self):
        self._setup(_rek_resp())
        m = load_handler("analyze_emotion")
        result = m.lambda_handler({"user_id": "only_this"}, {})
        self.assertEqual(result["statusCode"], 400)
        print("  [PASS] test_missing_params_returns_400")

    def test_all_emotion_genre_mappings(self):
        expected = {"HAPPY":"pop","SAD":"sad","ANGRY":"metal",
                    "SURPRISED":"electronic","DISGUSTED":"blues",
                    "CONFUSED":"ambient","CALM":"chill","FEAR":"classical"}
        for emotion, genre in expected.items():
            result, _ = self._call(_rek_resp(emotion, 90.0),
                {"user_id":"u","s3_bucket":"b","s3_key":"k"})
            self.assertEqual(json.loads(result["body"])["genre"], genre)
        print("  [PASS] test_all_emotion_genre_mappings (8 emotions)")

    def test_dynamodb_saved_correctly(self):
        _, mock_table = self._setup(_rek_resp("HAPPY"))
        m = load_handler("analyze_emotion")
        m.lambda_handler({"user_id":"u@t.com","s3_bucket":"b","s3_key":"k"},{})
        saved = mock_table.put_item.call_args[1]["Item"]
        self.assertEqual(saved["status"],  "EMOTION_ANALYZED")
        self.assertEqual(saved["emotion"], "HAPPY")
        print("  [PASS] test_dynamodb_saved_correctly")


# ══ 테스트 2: recommend_music/handler.py ══════════════════════

class TestRecommendMusic(unittest.TestCase):

    def _setup(self):
        mock_table = MagicMock()
        mock_sns   = MagicMock()
        boto3.resource.return_value.Table.return_value = mock_table
        boto3.client.return_value = mock_sns
        return mock_table, mock_sns

    def test_insert_processed(self):
        mock_table, _ = self._setup()
        m = load_handler("recommend_music")
        with patch.object(m, "_search_spotify_tracks", return_value=FAKE_TRACKS):
            result = m.lambda_handler(
                _stream_event("e1","u@t.com","HAPPY","pop"), {})
        self.assertEqual(result["processed"], 1)
        vals = mock_table.update_item.call_args[1]["ExpressionAttributeValues"]
        self.assertEqual(vals[":s"], "PLAYLIST_READY")
        print("  [PASS] test_insert_processed")

    def test_modify_skipped(self):
        m = load_handler("recommend_music")
        result = m.lambda_handler(
            {"Records":[{"eventName":"MODIFY","dynamodb":{"NewImage":{}}}]},{})
        self.assertEqual(result["processed"], 0)
        print("  [PASS] test_modify_skipped")

    def test_wrong_status_skipped(self):
        m = load_handler("recommend_music")
        result = m.lambda_handler(
            _stream_event("e2","u@t.com","HAPPY","pop",status="PLAYLIST_READY"),{})
        self.assertEqual(result["processed"], 0)
        print("  [PASS] test_wrong_status_skipped")

    def test_sns_published(self):
        _, mock_sns = self._setup()
        m = load_handler("recommend_music")
        m.SNS_TOPIC_ARN = "arn:aws:sns:ap-northeast-2:123:emotion-diary"
        with patch.object(m, "_search_spotify_tracks", return_value=FAKE_TRACKS):
            m.lambda_handler(_stream_event("e3","u@t.com","SAD","sad"),{})
        mock_sns.publish.assert_called_once()
        print("  [PASS] test_sns_published")


# ══ 테스트 3: send_diary/handler.py ══════════════════════════

class TestSendDiary(unittest.TestCase):

    def _setup(self):
        mock_ses   = MagicMock()
        mock_table = MagicMock()
        boto3.client.return_value   = mock_ses
        boto3.resource.return_value.Table.return_value = mock_table
        return mock_ses, mock_table

    def _sns_event(self, emotion="HAPPY", tracks=None):
        return {"Records":[{"Sns":{"Message":json.dumps({
            "entry_id":"e1","user_id":"u@t.com",
            "emotion":emotion,"genre":"pop",
            "timestamp":"2026-05-08T10:00:00+00:00",
            "tracks": tracks or FAKE_TRACKS,
        })}}]}

    def test_email_sent(self):
        mock_ses, _ = self._setup()
        m = load_handler("send_diary")
        result = m.lambda_handler(self._sns_event("HAPPY"), {})
        self.assertEqual(result["emails_sent"], 1)
        mock_ses.send_email.assert_called_once()
        print("  [PASS] test_email_sent")

    def test_subject_korean_emotion(self):
        mock_ses, _ = self._setup()
        m = load_handler("send_diary")
        m.lambda_handler(self._sns_event("SAD"), {})
        subj = mock_ses.send_email.call_args[1]["Message"]["Subject"]["Data"]
        self.assertIn("슬픔", subj)
        print("  [PASS] test_subject_korean_emotion")

    def test_dynamodb_status_email_sent(self):
        _, mock_table = self._setup()
        m = load_handler("send_diary")
        m.lambda_handler(self._sns_event("CALM"), {})
        vals = mock_table.update_item.call_args[1]["ExpressionAttributeValues"]
        self.assertEqual(vals[":s"], "EMAIL_SENT")
        print("  [PASS] test_dynamodb_status_email_sent")

    def test_html_contains_track(self):
        m = load_handler("send_diary")
        tracks = [{"name":"Bohemian Rhapsody","artist":"Queen",
                   "album":"A Night at the Opera",
                   "spotify_url":"https://spotify.com/bq","preview_url":""}]
        html = m._build_email_html("HAPPY","pop","2026-05-08T10:00:00",tracks)
        self.assertIn("Bohemian Rhapsody", html)
        self.assertIn("행복", html)
        print("  [PASS] test_html_contains_track")

    def test_text_contains_track(self):
        m = load_handler("send_diary")
        tracks = [{"name":"Song A","artist":"Artist B",
                   "album":"C","spotify_url":"","preview_url":""}]
        text = m._build_email_text("CALM","chill","2026-05-08T10:00:00",tracks)
        self.assertIn("Song A", text)
        self.assertIn("평온", text)
        print("  [PASS] test_text_contains_track")


# ── 실행 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [TestAnalyzeEmotion, TestRecommendMusic, TestSendDiary]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    print("\n" + "="*60)
    print("  Emotion Diary — Lambda 로컬 테스트")
    print("="*60)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    total  = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    print("="*60)
    print(f"  결과: {passed}/{total} 통과")
    print("="*60 + "\n")
    sys.exit(0 if result.wasSuccessful() else 1)