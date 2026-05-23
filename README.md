# 2026 Cloud Computing Term Project
## AI 표정 분석 기반 맞춤형 음악 추천 및 서버리스 다이어리 전송 서비스

> 중간보고 — 서버리스 백엔드 (Lambda 3종 + 테스트)

---

## 아키텍처 (이벤트 흐름)

```
[사용자 셀카 업로드]
        │  S3 이벤트 (또는 API Gateway)
        ▼
┌─────────────────────┐
│  Lambda 1           │  ← analyze_emotion/handler.py
│  (감정 분석)         │
│  AWS Rekognition    │
│  → DynamoDB INSERT  │  status: EMOTION_ANALYZED
└────────┬────────────┘
         │  DynamoDB Streams (INSERT 감지)
         ▼
┌─────────────────────┐
│  Lambda 2           │  ← recommend_music/handler.py
│  (플레이리스트 추천) │
│  Spotify Web API    │
│  → DynamoDB UPDATE  │  status: PLAYLIST_READY
│  → SNS Publish      │
└────────┬────────────┘
         │  SNS 구독
         ▼
┌─────────────────────┐
│  Lambda 3           │  ← send_diary/handler.py
│  (이메일 발송)       │
│  Amazon SES         │
│  → DynamoDB UPDATE  │  status: EMAIL_SENT
└─────────────────────┘
```

---

## 파일 구조

```
lambda/
├── analyze_emotion/
│   └── handler.py      # Lambda 1: Rekognition 감정 분석 + DynamoDB 저장
├── recommend_music/
│   └── handler.py      # Lambda 2: DynamoDB Streams 트리거 + Spotify API
└── send_diary/
    └── handler.py      # Lambda 3: SNS 구독 + SES 이메일 발송

tests/
└── test_local.py       # 14개 단위 테스트 (boto3 완전 mock)
```

---

## Lambda 환경변수 목록

### Lambda 1 — analyze_emotion
| 변수 | 설명 | 예시 |
|------|------|------|
| `AWS_REGION` | 리전 | `ap-northeast-2` |
| `DYNAMODB_TABLE` | DynamoDB 테이블명 | `emotion-diary` |

### Lambda 2 — recommend_music
| 변수 | 설명 | 예시 |
|------|------|------|
| `AWS_REGION` | 리전 | `ap-northeast-2` |
| `DYNAMODB_TABLE` | DynamoDB 테이블명 | `emotion-diary` |
| `SNS_TOPIC_ARN` | SNS 토픽 ARN | `arn:aws:sns:ap-northeast-2:123456789012:emotion-diary` |
| `SPOTIFY_CLIENT_ID` | Spotify 앱 Client ID | Spotify Developer Dashboard에서 발급 |
| `SPOTIFY_CLIENT_SECRET` | Spotify 앱 Secret | Spotify Developer Dashboard에서 발급 |

### Lambda 3 — send_diary
| 변수 | 설명 | 예시 |
|------|------|------|
| `AWS_REGION` | 리전 | `ap-northeast-2` |
| `SES_REGION` | SES 리전 (샌드박스는 us-east-1 권장) | `us-east-1` |
| `DYNAMODB_TABLE` | DynamoDB 테이블명 | `emotion-diary` |
| `SES_FROM_EMAIL` | 발신 이메일 (SES 인증 필요) | `noreply@your-domain.com` |

---

## DynamoDB 테이블 스키마

| 속성 | 타입 | 설명 |
|------|------|------|
| `entry_id` | String (PK) | UUID |
| `user_id` | String | 사용자 이메일 |
| `timestamp` | String | ISO 8601 |
| `emotion` | String | HAPPY / SAD / ANGRY 등 |
| `confidence` | String | Rekognition 신뢰도 (%) |
| `raw_emotions` | String (JSON) | 전체 감정 분포 |
| `genre` | String | Spotify 검색 장르 |
| `s3_key` | String | 원본 이미지 S3 경로 |
| `status` | String | EMOTION_ANALYZED → PLAYLIST_READY → EMAIL_SENT |
| `playlist` | String (JSON) | 추천 트랙 목록 |
| `email_sent_at` | String | 이메일 발송 시각 |

> **DynamoDB Streams 설정**: `NEW_IMAGE` 모드로 활성화 필요

---

## 감정 → 장르 매핑

| Rekognition 감정 | Spotify 장르 |
|-----------------|-------------|
| HAPPY | pop |
| SAD | sad |
| ANGRY | metal |
| SURPRISED | electronic |
| DISGUSTED | blues |
| CONFUSED | ambient |
| CALM | chill |
| FEAR | classical |

---

## 로컬 테스트 실행

```bash
# Python 3.8+ 필요, boto3 설치 불필요 (완전 mock)
python tests/test_local.py
```

**테스트 결과 (14/14 통과)**
```
============================================================
  Emotion Diary — Lambda 로컬 테스트
============================================================
  [PASS] test_all_emotion_genre_mappings (8 emotions)
  [PASS] test_happy_emotion_mapped_to_pop
  [PASS] test_missing_params_returns_400
  [PASS] test_no_face_returns_400
  [PASS] test_sad_emotion_mapped_to_sad_genre
  [PASS] test_insert_event_processed
  [PASS] test_modify_event_skipped
  [PASS] test_non_emotion_analyzed_skipped
  [PASS] test_sns_published_when_topic_set
  [PASS] test_dynamodb_updated_to_email_sent
  [PASS] test_email_sent_on_valid_sns
  [PASS] test_html_email_contains_track_info
  [PASS] test_subject_contains_korean_emotion
  [PASS] test_text_email_contains_track_info
결과: 14/14 통과
============================================================
```

---

## 중간보고 이후 계획

- [ ] Spotify `search` → `recommendations` 엔드포인트로 고도화 (seed_genres 활용)
- [ ] Lambda 2 실패 시 DLQ(Dead Letter Queue) 연결
- [ ] SES 샌드박스 해제 후 실제 이메일 발송 테스트
- [ ] 프론트엔드 팀의 S3 presigned URL 업로드와 analyze_emotion Lambda 연결
