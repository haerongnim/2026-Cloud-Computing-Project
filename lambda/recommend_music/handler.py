"""
Lambda Function 2: recommend_music
- DynamoDB Streams 이벤트로 트리거됨 (analyze_emotion이 INSERT한 레코드 감지)
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

dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
sns      = boto3.client("sns",      region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))

TABLE_NAME    = os.environ.get("DYNAMODB_TABLE", "emotion-diary")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")

# Spotify API 자격증명 (Lambda 환경변수로 주입)
SPOTIFY_CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")


def lambda_handler(event, context):
    """
    DynamoDB Streams 이벤트를 받아 INSERT된 레코드만 처리
    """
    processed = 0

    for record in event.get("Records", []):
        if record.get("eventName") != "INSERT":
            continue

        new_image = record["dynamodb"].get("NewImage", {})
        status = new_image.get("status", {}).get("S", "")

        # analyze_emotion이 저장한 레코드만 처리
        if status != "EMOTION_ANALYZED":
            continue

        entry_id = new_image["entry_id"]["S"]
        user_id  = new_image["user_id"]["S"]
        genre    = new_image["genre"]["S"]
        emotion  = new_image["emotion"]["S"]
        timestamp = new_image["timestamp"]["S"]

        try:
            # 1. Spotify 플레이리스트 검색
            tracks = _search_spotify_tracks(genre, emotion)

            # 2. DynamoDB 업데이트
            table = dynamodb.Table(TABLE_NAME)
            table.update_item(
                Key={"entry_id": entry_id},
                UpdateExpression="SET #st = :s, playlist = :p",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":s": "PLAYLIST_READY",
                    ":p": json.dumps(tracks, ensure_ascii=False),
                },
            )

            # 3. SNS 발행 → send_diary Lambda가 구독해서 이메일 발송
            if SNS_TOPIC_ARN:
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=json.dumps({
                        "entry_id":  entry_id,
                        "user_id":   user_id,
                        "emotion":   emotion,
                        "genre":     genre,
                        "timestamp": timestamp,
                        "tracks":    tracks,
                    }, ensure_ascii=False),
                    Subject=f"[Emotion Diary] 감정 플레이리스트 준비 완료 - {emotion}",
                )

            processed += 1
            print(f"[OK] entry_id={entry_id}, user={user_id}, emotion={emotion}, tracks={len(tracks)}")

        except Exception as e:
            print(f"[ERROR] entry_id={entry_id}: {e}")

    return {"processed": processed}


# ────────────────────────────────────────────────
# Spotify Helper (urllib 사용, requests 미설치 환경 대비)
# ────────────────────────────────────────────────

def _get_spotify_token() -> str:
    """Client Credentials Flow로 액세스 토큰 발급"""
    credentials = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()

    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req  = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=data,
        headers={
            "Authorization": f"Basic {credentials}",
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
            "spotify_url": item["external_urls"].get("spotify", ""),
            "preview_url": item.get("preview_url", ""),
        })

    return tracks