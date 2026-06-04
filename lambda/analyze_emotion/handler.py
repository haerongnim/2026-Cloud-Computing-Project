"""
Lambda Function 1: analyze_emotion
- S3에 업로드된 셀카 이미지를 받아 AWS Rekognition으로 감정 분석
- 분석 결과를 DynamoDB에 저장
- DynamoDB Streams → recommend_music Lambda를 트리거
"""

import json
import boto3
import os
from datetime import datetime, timezone
from decimal import Decimal

from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-2")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "emotion-diary")

rekognition = boto3.client("rekognition", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

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
    이벤트 구조 (Backend → Lambda 직접 호출):
    {
        "entry_id":   "sha256-hash",
        "request_id": "uuid",
        "user_id":    "user:uuid",
        "s3_bucket":  "emotion-diary-images",
        "s3_key":     "uploads/hash/uuid.jpg",
        "date":       "2026-05-30"
    }
    """
    body = json.loads(event.get("body", "{}")) if isinstance(event.get("body"), str) else event

    # 필수 파라미터 검증 (entry_id, request_id 포함)
    required = ("entry_id", "request_id", "user_id", "date", "s3_bucket", "s3_key")
    if not all(body.get(field) for field in required):
        return _response(400, {"error": f"{', '.join(required)} are required"})

    table = dynamodb.Table(TABLE_NAME)

    # 중복 실행 방지: 현재 DynamoDB 레코드의 request_id와 status를 확인
    current = table.get_item(Key={"entry_id": body["entry_id"]}).get("Item", {})
    if current.get("request_id") != body["request_id"] or current.get("status") != "PROCESSING":
        return _response(200, {"entry_id": body["entry_id"], "message": "stale or duplicate request ignored"})

    try:
        # 1. Rekognition 감정 분석
        emotion_label, confidence, raw_emotions = _detect_emotion(body["s3_bucket"], body["s3_key"])

        # 2. DynamoDB 업데이트 (이 이벤트가 recommend_music Lambda를 트리거)
        timestamp = datetime.now(timezone.utc).isoformat()
        genre = EMOTION_TO_GENRE.get(emotion_label, "pop")

        table.update_item(
            Key={"entry_id": body["entry_id"]},
            UpdateExpression=(
                "SET #st = :analyzed, emotion = :emotion, confidence = :confidence, "
                "raw_emotions = :raw, genre = :genre, updated_at = :updated"
            ),
            ConditionExpression="request_id = :request AND #st = :processing",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":request":    body["request_id"],
                ":processing": "PROCESSING",
                ":analyzed":   "EMOTION_ANALYZED",
                ":emotion":    emotion_label,
                ":confidence": Decimal(str(round(confidence, 2))),
                ":raw":        {key: Decimal(str(value)) for key, value in raw_emotions.items()},
                ":genre":      genre,
                ":updated":    timestamp,
            },
        )

        return _response(200, {
            "entry_id":    body["entry_id"],
            "emotion":     emotion_label,
            "confidence":  round(confidence, 2),
            "genre":       genre,
            "all_emotions": raw_emotions,
            "message":     "Emotion analyzed. Playlist recommendation triggered."
        })

    except rekognition.exceptions.InvalidS3ObjectException as e:
        _save_failed_entry(table, body, "S3 object not found or invalid image")
        return _response(400, {"error": "S3 object not found or invalid image"})

    except ValueError as e:
        _save_failed_entry(table, body, str(e))
        return _response(400, {"error": str(e)})

    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return _response(200, {"entry_id": body["entry_id"], "message": "duplicate request ignored"})
        raise

    except Exception as e:
        print(f"[ERROR] {e}")
        _save_failed_entry(table, body, str(e))
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


def _save_failed_entry(table, body: dict, error_message: str):
    """실패 상태 업데이트 — ConditionExpression으로 중복 방지"""
    try:
        table.update_item(
            Key={"entry_id": body["entry_id"]},
            UpdateExpression="SET #st = :failed, error_message = :message, updated_at = :updated",
            ConditionExpression="request_id = :request AND #st = :processing",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":request":    body["request_id"],
                ":processing": "PROCESSING",
                ":failed":     "FAILED",
                ":message":    error_message,
                ":updated":    datetime.now(timezone.utc).isoformat(),
            },
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise