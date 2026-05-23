"""
Lambda Function 3: send_diary
- SNS 토픽 구독 (recommend_music이 발행한 메시지 수신)
- Amazon SES로 사용자에게 감정 분석 결과 + 플레이리스트를 이메일 발송
- 발송 결과를 DynamoDB에 기록 (status: EMAIL_SENT)
"""

import json
import boto3
import os
from datetime import datetime

ses      = boto3.client("ses",      region_name=os.environ.get("SES_REGION",  "us-east-1"))
dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-northeast-2"))

TABLE_NAME      = os.environ.get("DYNAMODB_TABLE", "emotion-diary")
SES_FROM_EMAIL  = os.environ.get("SES_FROM_EMAIL", "noreply@emotion-diary.example.com")

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
        try:
            sns_message = json.loads(record["Sns"]["Message"])

            entry_id  = sns_message["entry_id"]
            user_id   = sns_message["user_id"]   # 이메일 주소로 사용
            emotion   = sns_message["emotion"]
            genre     = sns_message["genre"]
            timestamp = sns_message["timestamp"]
            tracks    = sns_message.get("tracks", [])

            # 이메일 HTML 본문 생성
            html_body = _build_email_html(emotion, genre, timestamp, tracks)
            text_body = _build_email_text(emotion, genre, timestamp, tracks)

            # SES 이메일 발송
            ses.send_email(
                Source=SES_FROM_EMAIL,
                Destination={"ToAddresses": [user_id]},
                Message={
                    "Subject": {
                        "Data":    f"[Emotion Diary] 오늘의 감정은 {EMOTION_KO.get(emotion, emotion)} — 플레이리스트가 준비됐어요 🎵",
                        "Charset": "UTF-8",
                    },
                    "Body": {
                        "Text": {"Data": text_body, "Charset": "UTF-8"},
                        "Html": {"Data": html_body, "Charset": "UTF-8"},
                    },
                },
            )

            # DynamoDB status 업데이트
            table = dynamodb.Table(TABLE_NAME)
            table.update_item(
                Key={"entry_id": entry_id},
                UpdateExpression="SET #st = :s, email_sent_at = :t",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":s": "EMAIL_SENT",
                    ":t": datetime.utcnow().isoformat(),
                },
            )

            sent += 1
            print(f"[OK] Email sent to {user_id} for entry {entry_id}")

        except Exception as e:
            print(f"[ERROR] {e}")

    return {"emails_sent": sent}


# ────────────────────────────────────────────────
# 이메일 본문 빌더
# ────────────────────────────────────────────────

def _build_email_html(emotion: str, genre: str, timestamp: str, tracks: list) -> str:
    emotion_ko = EMOTION_KO.get(emotion, emotion)
    date_str   = timestamp[:10]

    track_rows = ""
    for i, t in enumerate(tracks, 1):
        link = f'<a href="{t["spotify_url"]}" style="color:#1DB954;">Spotify에서 듣기</a>' if t.get("spotify_url") else ""
        track_rows += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px;color:#666;">{i}</td>
          <td style="padding:10px;font-weight:bold;">{t['name']}</td>
          <td style="padding:10px;color:#555;">{t['artist']}</td>
          <td style="padding:10px;">{link}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:20px;background:#f9f9f9;">
      <div style="background:white;border-radius:12px;padding:30px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <h1 style="color:#333;font-size:22px;">🎵 오늘의 감정 다이어리</h1>
        <p style="color:#666;">{date_str}</p>
        <div style="background:#f0f4ff;border-radius:8px;padding:16px;margin:20px 0;">
          <p style="margin:0;font-size:18px;">오늘의 감정: <strong>{emotion_ko}</strong></p>
          <p style="margin:4px 0 0;color:#888;">추천 장르: {genre}</p>
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


def _build_email_text(emotion: str, genre: str, timestamp: str, tracks: list) -> str:
    emotion_ko = EMOTION_KO.get(emotion, emotion)
    lines = [
        f"오늘의 감정 다이어리 ({timestamp[:10]})",
        f"감정: {emotion_ko}  |  추천 장르: {genre}",
        "",
        "🎧 추천 플레이리스트",
        "-" * 40,
    ]
    for i, t in enumerate(tracks, 1):
        lines.append(f"{i}. {t['name']} — {t['artist']}")
        if t.get("spotify_url"):
            lines.append(f"   {t['spotify_url']}")
    lines.append("\n이 메일은 Emotion Diary 서비스에서 자동 발송되었습니다.")
    return "\n".join(lines)