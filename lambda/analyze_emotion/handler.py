"""
Lambda Function 1: analyze_emotion
- S3에 업로드된 셀카 이미지를 받아 AWS Rekognition으로 감정 분석
- 분석 결과를 DynamoDB에 저장
- DynamoDB Streams → recommend_music Lambda를 트리거
"""

import json
import boto3
import os
import uuid
from datetime import datetime, timezone

rekognition = boto3.client("rekognition", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))

TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "emotion-diary")

# Rekognition 감정 → Spotify seed genre 매핑
EMOTION_TO_GENRE = {
    "HAPPY":     "pop",
    "SAD":       "sad",
    "ANGRY":     "metal",
    "SURPRISED": "electronic",
    "DISGUSTED": "blues",
    "CONFUSED":  "ambient",
    "CALM":      "chill",
    "FEAR":      "classical",
}


def lambda_handler(event, context):
    """
    이벤트 구조 (API Gateway → Lambda):
    {
        "user_id": "user@example.com",
        "s3_bucket": "emotion-diary-images",
        "s3_key": "uploads/user123/photo.jpg"
    }
    """
    try:
        body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event

        user_id  = body.get("user_id")
        s3_bucket = body.get("s3_bucket")
        s3_key    = body.get("s3_key")

        if not all([user_id, s3_bucket, s3_key]):
            return _response(400, {"error": "user_id, s3_bucket, s3_key are required"})

        # 1. Rekognition 감정 분석
        emotion_label, confidence, raw_emotions = _detect_emotion(s3_bucket, s3_key)

        # 2. DynamoDB 저장 (이 이벤트가 recommend_music Lambda를 트리거)
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        genre = EMOTION_TO_GENRE.get(emotion_label, "pop")

        table = dynamodb.Table(TABLE_NAME)
        table.put_item(Item={
            "entry_id":      entry_id,
            "user_id":       user_id,
            "timestamp":     timestamp,
            "emotion":       emotion_label,
            "confidence":    str(round(confidence, 2)),
            "raw_emotions":  json.dumps(raw_emotions),
            "genre":         genre,
            "s3_key":        s3_key,
            "status":        "EMOTION_ANALYZED",   # recommend_music이 PLAYLIST_READY로 업데이트
        })

        return _response(200, {
            "entry_id":   entry_id,
            "emotion":    emotion_label,
            "confidence": round(confidence, 2),
            "genre":      genre,
            "all_emotions": raw_emotions,
            "message":    "Emotion analyzed. Playlist recommendation triggered."
        })

    except rekognition.exceptions.InvalidS3ObjectException:
        return _response(400, {"error": "S3 object not found or invalid image"})
    except ValueError as e:
        # 얼굴 미감지 등 클라이언트 입력 문제
        return _response(400, {"error": str(e)})
    except Exception as e:
        print(f"[ERROR] {e}")
        return _response(500, {"error": str(e)})


def _detect_emotion(bucket: str, key: str):
    """Rekognition DetectFaces 호출 → 가장 신뢰도 높은 감정 반환"""
    response = rekognition.detect_faces(
        Image={"S3Object": {"Bucket": bucket, "Name": key}},
        Attributes=["ALL"],
    )

    if not response["FaceDetails"]:
        raise ValueError("No face detected in the image")

    # 첫 번째 얼굴의 감정 목록
    emotions = response["FaceDetails"][0]["Emotions"]
    emotions_sorted = sorted(emotions, key=lambda e: e["Confidence"], reverse=True)

    top_emotion = emotions_sorted[0]
    raw = {e["Type"]: round(e["Confidence"], 2) for e in emotions_sorted}

    return top_emotion["Type"], top_emotion["Confidence"], raw


def _response(status_code: int, body: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }