"""
Lambda Function 2: recommend_music
- DynamoDB Streams 이벤트로 트리거됨 (analyze_emotion이 UPDATE한 레코드 감지)
- Spotify Web API로 감정 기반 플레이리스트 검색
- 결과를 DynamoDB에 업데이트 (status: PLAYLIST_READY)
- SNS 토픽에 메시지 발행 → send_diary Lambda 트리거
"""

import json
import boto3
import os
import urllib.request
import urllib.parse
import base64
from datetime import datetime, timezone

from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
sns      = boto3.client("sns",      region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
secretsmanager = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))

TABLE_NAME    = os.environ.get("DYNAMODB_TABLE", "emotion-diary")
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

# Spotify 자격증명은 Secrets Manager에서 로드 (환경변수 직접 노출 방지)
SPOTIFY_SECRET_ARN = os.environ["SPOTIFY_SECRET_ARN"]
_spotify_credentials = None


def lambda_handler(event, context):
    """
    DynamoDB Streams 이벤트를 받아 MODIFY된 레코드 중 EMOTION_ANALYZED 상태만 처리
    (analyze_emotion이 update_item으로 상태를 변경하면 MODIFY 이벤트 발생)
    """
    processed = 0

    for record in event.get("Records", []):
        # MODIFY 이벤트만 처리 (analyze_emotion은 update_item 사용 → INSERT 아님)
        if record.get("eventName") != "MODIFY":
            continue

        old_image = record["dynamodb"].get("OldImage", {})
        new_image = record["dynamodb"].get("NewImage", {})

        # 이전 상태가 이미 EMOTION_ANALYZED였거나, 새 상태가 EMOTION_ANALYZED가 아니면 건너뜀
        if _string(old_image, "status") == "EMOTION_ANALYZED" or _string(new_image, "status") != "EMOTION_ANALYZED":
            continue

        entry_id   = _string(new_image, "entry_id")
        request_id = _string(new_image, "request_id")
        user_id    = _string(new_image, "user_id")
        genre      = _string(new_image, "genre")
        emotion    = _string(new_image, "emotion")
        entry_date = _string(new_image, "date")

        table = dynamodb.Table(TABLE_NAME)

        # 중복 실행 방지: 현재 DynamoDB 레코드 상태 재확인
        current = table.get_item(Key={"entry_id": entry_id}).get("Item", {})
        if current.get("request_id") != request_id or current.get("status") != "EMOTION_ANALYZED":
            continue

        try:
            # 1. Spotify 플레이리스트 검색
            tracks = _search_spotify_tracks(genre, emotion)

            # 2. DynamoDB 업데이트 (ConditionExpression으로 중복 방지)
            try:
                table.update_item(
                    Key={"entry_id": entry_id},
                    UpdateExpression="SET #st = :ready, playlist = :playlist, updated_at = :updated",
                    ConditionExpression="request_id = :request AND #st = :analyzed",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":request":  request_id,
                        ":analyzed": "EMOTION_ANALYZED",
                        ":ready":    "PLAYLIST_READY",
                        ":playlist": tracks,
                        ":updated":  datetime.now(timezone.utc).isoformat(),
                    },
                )
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    continue
                raise

            # 3. SNS 발행 → send_diary Lambda가 구독해서 이메일 발송
            try:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=json.dumps({
                        "entry_id":   entry_id,
                        "request_id": request_id,
                        "user_id":    user_id,
                        "emotion":    emotion,
                        "genre":      genre,
                        "date":       entry_date,
                        "tracks":     tracks,
                    }, ensure_ascii=False),
                    Subject=f"[Emotion Diary] 감정 플레이리스트 준비 완료 - {emotion}",
                )
            except Exception:
                # SNS 실패 시 PLAYLIST_READY → EMOTION_ANALYZED 롤백
                table.update_item(
                    Key={"entry_id": entry_id},
                    UpdateExpression="SET #st = :analyzed, updated_at = :updated",
                    ConditionExpression="request_id = :request AND #st = :ready",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":request":  request_id,
                        ":ready":    "PLAYLIST_READY",
                        ":analyzed": "EMOTION_ANALYZED",
                        ":updated":  datetime.now(timezone.utc).isoformat(),
                    },
                )
                raise

            processed += 1
            print(f"[OK] entry_id={entry_id}, user={user_id}, emotion={emotion}, tracks={len(tracks)}")

        except Exception as e:
            print(f"[ERROR] entry_id={entry_id}: {e}")

    return {"processed": processed}


# ────────────────────────────────────────────────
# DynamoDB Streams 헬퍼
# ────────────────────────────────────────────────

def _string(image: dict, key: str) -> str:
    return image.get(key, {}).get("S", "")


# ────────────────────────────────────────────────
# Spotify Helper (urllib 사용, requests 미설치 환경 대비)
# ────────────────────────────────────────────────

def _get_spotify_credentials() -> dict:
    """Secrets Manager에서 Spotify 자격증명 로드 (캐싱)"""
    global _spotify_credentials
    if _spotify_credentials is None:
        response = secretsmanager.get_secret_value(SecretId=SPOTIFY_SECRET_ARN)
        _spotify_credentials = json.loads(response["SecretString"])
    return _spotify_credentials


def _get_spotify_token() -> str:
    """Client Credentials Flow로 액세스 토큰 발급"""
    credentials = _get_spotify_credentials()
    encoded = base64.b64encode(
        f"{credentials['client_id']}:{credentials['client_secret']}".encode()
    ).decode()

    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req  = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())["access_token"]


def _search_spotify_tracks(genre: str, emotion: str, limit: int = 5) -> list:
    """감정 + 장르 키워드로 트랙 검색, 최대 limit개 반환"""
    token = _get_spotify_token()

    # 검색 쿼리: 감정 키워드 + 장르
    query = urllib.parse.quote(f"{emotion.lower()} {genre} mood")
    url   = f"https://api.spotify.com/v1/search?q={query}&type=track&limit={limit}&market=KR"

    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    tracks = []
    for item in data.get("tracks", {}).get("items", []):
        tracks.append({
            "name":        item["name"],
            "artist":      ", ".join(a["name"] for a in item["artists"]),
            "album":       item["album"]["name"],
            "spotifyUrl":  item["external_urls"].get("spotify", ""),
            "previewUrl":  item.get("preview_url", ""),
            "albumCover":  item["album"]["images"][-1]["url"] if item["album"].get("images") else "",
        })

    return tracks