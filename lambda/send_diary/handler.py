"""
Lambda Function 3: send_diary
- SNS 토픽 구독 (recommend_music이 발행한 메시지 수신)
- Amazon SES로 사용자에게 감정 분석 결과 + 플레이리스트를 이메일 발송
- 발송 결과를 DynamoDB에 기록 (status: EMAIL_SENT)
"""

import html
import json
import boto3
import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError

ses      = boto3.client("ses",      region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))

TABLE_NAME     = os.environ.get("DYNAMODB_TABLE", "emotion-diary")
SES_FROM_EMAIL = os.environ["SES_FROM_EMAIL"]   # 필수값: 기본값이 잘못된 도메인이면 SES 발송 실패

# 감정 한국어 매핑
EMOTION_KO = {
    "HAPPY":     "😊 행복",
    "SAD":       "😢 슬픔",
    "ANGRY":     "😠 분노",
    "SURPRISED": "😲 놀람",
    "DISGUSTED": "😒 혐오",
    "CONFUSED":  "😕 혼란",
    "CALM":      "😌 평온",
    "FEAR":      "😨 두려움",
}


def lambda_handler(event, context):
    """
    SNS 이벤트 구조:
    event["Records"][i]["Sns"]["Message"] = JSON string
    """
    sent = 0

    for record in event.get("Records", []):
        message = json.loads(record["Sns"]["Message"])
        table   = dynamodb.Table(TABLE_NAME)

        # 중복 발송 방지: request_id와 status 확인
        current = table.get_item(Key={"entry_id": message["entry_id"]}).get("Item", {})
        if current.get("request_id") != message["request_id"] or current.get("status") != "PLAYLIST_READY":
            continue

        # 비로그인(anonymous) 사용자는 이메일 발송 대상 아님
        user_id = message.get("user_id", "")
        if user_id.startswith("anonymous:"):
            continue

        # account 레코드에서 실제 이메일 주소 조회
        # (user_id는 "user:UUID" 형태이므로 이메일 주소가 아님)
        account = table.get_item(Key={"entry_id": f"account:{user_id}"}).get("Item", {})
        email   = account.get("email")
        if not email:
            continue

        try:
            # EMAIL_SENDING 중간 상태로 전환 (멱등성 확보: SNS 재전송 시 중복 발송 방지)
            try:
                table.update_item(
                    Key={"entry_id": message["entry_id"]},
                    UpdateExpression="SET #st = :sending, updated_at = :updated",
                    ConditionExpression="request_id = :request AND #st = :ready",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":request": message["request_id"],
                        ":ready":   "PLAYLIST_READY",
                        ":sending": "EMAIL_SENDING",
                        ":updated": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    continue
                raise

            # 이메일 HTML 본문 생성
            html_body = _build_email_html(message)
            text_body = _build_email_text(message)

            # SES 이메일 발송
            try:
                ses.send_email(
                    Source=SES_FROM_EMAIL,
                    Destination={"ToAddresses": [email]},
                    Message={
                        "Subject": {
                            "Data":    f"[Emotion Diary] 오늘의 감정은 {EMOTION_KO.get(message['emotion'], message['emotion'])} — 플레이리스트가 준비됐어요 🎵",
                            "Charset": "UTF-8",
                        },
                        "Body": {
                            "Text": {"Data": text_body, "Charset": "UTF-8"},
                            "Html": {"Data": html_body, "Charset": "UTF-8"},
                        },
                    },
                )
            except Exception:
                # 발송 실패 시 PLAYLIST_READY로 롤백
                table.update_item(
                    Key={"entry_id": message["entry_id"]},
                    UpdateExpression="SET #st = :ready, updated_at = :updated",
                    ConditionExpression="request_id = :request AND #st = :sending",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={
                        ":request": message["request_id"],
                        ":sending": "EMAIL_SENDING",
                        ":ready":   "PLAYLIST_READY",
                        ":updated": datetime.now(timezone.utc).isoformat(),
                    },
                )
                raise

            # DynamoDB status 업데이트
            table.update_item(
                Key={"entry_id": message["entry_id"]},
                UpdateExpression="SET #st = :sent, email_sent_at = :sent_at, updated_at = :updated",
                ConditionExpression="request_id = :request AND #st = :sending",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":request":  message["request_id"],
                    ":sending":  "EMAIL_SENDING",
                    ":sent":     "EMAIL_SENT",
                    ":sent_at":  datetime.now(timezone.utc).isoformat(),
                    ":updated":  datetime.now(timezone.utc).isoformat(),
                },
            )

            sent += 1
            print(f"[OK] Email sent to {email} for entry {message['entry_id']}")

        except Exception as e:
            print(f"[ERROR] {e}")

    return {"emails_sent": sent}


# ────────────────────────────────────────────────
# 이메일 본문 빌더
# ────────────────────────────────────────────────

def _build_email_html(message: dict) -> str:
    emotion_ko = EMOTION_KO.get(message["emotion"], message["emotion"])
    entry_date = message.get("date", "")

    track_rows = ""
    for i, t in enumerate(message.get("tracks", []), 1):
        # html.escape()로 XSS 방지 (트랙명·아티스트명에 특수문자 포함 가능)
        spotify_url = html.escape(t.get("spotifyUrl", ""), quote=True)
        link = f'<a href="{spotify_url}" style="color:#1DB954;">Spotify에서 듣기</a>' if spotify_url else ""
        track_rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px;color:#666;">{i}</td>
          <td style="padding:10px;font-weight:bold;">{html.escape(t["name"])}</td>
          <td style="padding:10px;color:#555;">{html.escape(t["artist"])}</td>
          <td style="padding:10px;">{link}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:20px;background:#f9f9f9;">
      <div style="background:white;border-radius:12px;padding:30px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <h1 style="color:#333;font-size:22px;">🎵 오늘의 감정 다이어리</h1>
        <p style="color:#666;">{html.escape(entry_date)}</p>
        <div style="background:#f0f4ff;border-radius:8px;padding:16px;margin:20px 0;">
          <p style="margin:0;font-size:18px;">오늘의 감정: <strong>{html.escape(emotion_ko)}</strong></p>
          <p style="margin:4px 0 0;color:#888;">추천 장르: {html.escape(message.get("genre", ""))}</p>
        </div>
        <h2 style="color:#333;font-size:16px;">🎧 추천 플레이리스트</h2>
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:#f5f5f5;">
              <th style="padding:10px;text-align:left;">#</th>
              <th style="padding:10px;text-align:left;">곡명</th>
              <th style="padding:10px;text-align:left;">아티스트</th>
              <th style="padding:10px;text-align:left;"></th>
            </tr>
          </thead>
          <tbody>{track_rows}</tbody>
        </table>
        <p style="color:#aaa;font-size:12px;margin-top:30px;">
          이 메일은 Emotion Diary 서비스에서 자동 발송되었습니다.
        </p>
      </div>
    </body></html>
    """


def _build_email_text(message: dict) -> str:
    emotion_ko = EMOTION_KO.get(message["emotion"], message["emotion"])
    lines = [
        f"오늘의 감정 다이어리 ({message.get('date', '')})",
        f"감정: {emotion_ko}  |  추천 장르: {message.get('genre', '')}",
        "",
        "🎧 추천 플레이리스트",
        "-" * 40,
    ]
    for i, t in enumerate(message.get("tracks", []), 1):
        lines.append(f"{i}. {t['name']} — {t['artist']}")
        if t.get("spotifyUrl"):
            lines.append(f"   {t['spotifyUrl']}")
    lines.append("\n이 메일은 Emotion Diary 서비스에서 자동 발송되었습니다.")
    return "\n".join(lines)