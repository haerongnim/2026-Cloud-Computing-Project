# 2026 Cloud Computing Term Project

## AI 표정 분석 기반 맞춤형 음악 추천 서비스

### 중간 개발 보고 — 인프라, WAS

---

## 프로젝트 개요

사용자가 웹페이지에서 사진을 업로드하면,
Flask 기반 API 서버가 요청을 수신하고 감정 분석 파이프라인으로 전달하는 구조 구축

현재 단계에서는:

* 실제 AWS Rekognition/Spotify 연동 대신
* Mock 기반 감정 분석 및 음악 추천 로직을 구현하여
* 전체 서비스 흐름과 서버 아키텍처 검증

---

# 현재 백엔드 아키텍처

```text
[Client Browser]
        │
        ▼
┌─────────────────────┐
│      nginx          │
│  Docker Container   │
│  Reverse Proxy      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│      Flask API      │
│  Docker Container   │
│  Upload Gateway     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Upload Validation  │
│  multipart/form     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Mock Emotion AI    │
│  Random Emotion     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Mock Music Service  │
│ Playlist Generator  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Mock DynamoDB Save  │
│ Repository Layer    │
└─────────────────────┘
```

---

# 현재 구현 범위

## 1. AWS EC2 인프라 구축

### 구현 내용

* Ubuntu 기반 EC2 생성
* Security Group 최소 공개 정책 적용
* SSH 특정 IP 제한
* HTTP 80 포트 공개

### 적용 사항

| 항목             | 상태 |
| -------------- | -- |
| EC2            | 완료 |
| Security Group | 완료 |
| IMDSv2 활성화     | 완료 |
| Docker 설치      | 완료 |

---

# 2. Docker 기반 컨테이너 환경 구축

## 구성

| 컨테이너      | 역할            |
| --------- | ------------- |
| nginx     | Reverse Proxy |
| flask-app | API Gateway   |

---

## Docker Compose 구성

### 적용 기능

* 컨테이너 네트워크 분리
* restart policy 적용
* volume mount 적용
* 환경변수(.env) 연결

---

# 3. nginx Reverse Proxy 구성

## 역할

* 외부 HTTP 요청 수신
* Flask 컨테이너로 요청 전달
* Flask 서버 외부 직접 노출 차단

---

## 네트워크 구조

```text
Client
   ↓ :80
nginx container
   ↓ internal network
flask container :5000
```

---

# 4. Flask API Gateway 구현

## 구현 API

### Health Check

```http
GET /health
```

---

### 이미지 분석 요청

```http
POST /analyze
```

---

## Request 형식

```multipart/form-data
email=<user email>
image=<image file>
```

---

## 구현 기능

| 기능                     | 상태 |
| ---------------------- | -- |
| multipart/form-data 처리 | 완료 |
| 이미지 업로드                | 완료 |
| 파일 확장자 검증              | 완료 |
| secure_filename 적용     | 완료 |
| UUID 기반 파일명 생성         | 완료 |
| uploads 디렉토리 저장        | 완료 |

---

# 5. 환경변수(.env) 구성

## 적용 목적

* AWS Key 관리
* Spotify Secret 관리
* 환경 설정 분리

---

## 추후 사용예정 환경변수

| 변수                    | 설명                |
| --------------------- | ----------------- |
| FLASK_ENV             | Flask 실행 환경       |
| AWS_REGION            | AWS 리전            |
| AWS_ACCESS_KEY_ID     | AWS Access Key    |
| AWS_SECRET_ACCESS_KEY | AWS Secret        |
| SPOTIFY_CLIENT_ID     | Spotify Client ID |
| SPOTIFY_CLIENT_SECRET | Spotify Secret    |
```(실제 .env 파일은 git으로 추적하지 않음)```

---

# 6. Mock 감정 분석 서비스 구현

## emotion_service.py

실제 Rekognition 대신:

* 랜덤 감정 반환
* 신뢰도(confidence) 생성

---

## 지원 감정 목록

| 감정    |
| ----- |
| HAPPY |
| SAD   |
| CALM  |
| ANGRY |

---

# 7. Mock 음악 추천 서비스 구현

## music_service.py

감정 기반 샘플 플레이리스트 반환 구현

---

## 예시 매핑

| 감정    | 추천 장르  |
| ----- | ------ |
| HAPPY | pop    |
| SAD   | ballad |
| CALM  | chill  |
| ANGRY | rock   |

---

# 8. Repository Layer 구현

## 구조

```text
services/
repositories/
```

---

## 구현 목적

* 비즈니스 로직 분리
* DB 접근 계층 분리
* 향후 DynamoDB 연동 대비

---

## 현재 상태

### Mock DynamoDB Save 구현

* diary_repository.py
* 저장 데이터 구조 검증 완료
* 로그 출력 기반 테스트 완료

---

# 현재 프로젝트 구조

```text
cc-term-project/
├── app.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
├── .gitignore
│
├── services/
│   ├── __init__.py
│   ├── emotion_service.py
│   ├── music_service.py
│   └── diary_service.py
│
├── repositories/
│   ├── __init__.py
│   └── diary_repository.py
│
├── uploads/
│
└── nginx/
    └── default.conf
```

---

# Docker 보안 및 운영 구성

## 적용 사항

| 항목                      | 상태 |
| ----------------------- | -- |
| non-root container user | 적용 |
| Flask 외부 미공개            | 적용 |
| nginx만 외부 공개            | 적용 |
| Docker restart policy   | 적용 |
| 내부 Docker network       | 적용 |

---

# 테스트 완료 항목

| 테스트                 | 결과   |
| ------------------- | ---- |
| nginx Reverse Proxy | PASS |
| Flask Health Check  | PASS |
| multipart 이미지 업로드   | PASS |
| Mock 감정 분석          | PASS |
| Mock 플레이리스트 생성      | PASS |
| Mock DB 저장          | PASS |
| Docker 재시작          | PASS |

---

# 현재 API 응답 예시

```json
{
  "message": "analysis completed",
  "email": "test@example.com",
  "emotion": {
    "emotion": "HAPPY",
    "confidence": 94.3
  },
  "playlist": [
    "Pharrell Williams - Happy",
    "Justin Timberlake - Can't Stop The Feeling"
  ],
  "filename": "uuid_test.jpg"
}
```

---

# 현재까지 달성한 목표

* AWS 기반 컨테이너 인프라 구축
* Docker Compose 기반 서비스 운영
* Reverse Proxy 기반 API Gateway 구현
* 이미지 업로드 API 구현
* Mock 기반 AI/추천 흐름 구현
* 서비스 계층 분리 구조 구현
* 서버리스 백엔드 연동 준비 완료

---

# 이후 개발 계획

* [ ] AWS Rekognition 실제 연동
* [ ] DynamoDB 실제 저장 연동
* [ ] Spotify Web API 연동
* [ ] S3 업로드 연동
* [ ] Lambda Trigger 연결
* [ ] 프론트엔드 업로드 화면 연동
* [ ] SES 이메일 다이어리 발송 연동
