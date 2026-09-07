# ART:READY - 검증용 FO

실제 `api_art_admission.py`(FastAPI)와 연결한 정적 사이트입니다.
빌드 도구 없음 - Tailwind CDN + 순수 JS.

**중요**: 화면에 나오는 학교/전형/일정/재료 등은 전부 실제 API 응답 그대로이며,
FO 코드에서 임의로 만들어내는 값은 없습니다.

## 로컬 실행

```powershell
# 1. API 서버 (다른 터미널)
uv run uvicorn 내작업폴더.api_art_admission:app --reload --port 8000

# 2. 정적 파일 서버 (이 폴더 안에서)
cd 내작업폴더/fo
python -m http.server 5500
```

브라우저에서 http://localhost:5500/index.html 접속.
로컬 API로 붙이려면 `config.js`의 `API_BASE_URL`을 `http://localhost:8000`으로
바꾸고, 커밋 전에 반드시 배포 주소(`https://api.unsuzone.com/art-admission`)로
되돌려야 합니다.

## 배포 시

- FO(`fo/` 폴더)는 정적 사이트로 별도 배포됩니다.
- API는 AWS Lightsail(`art-admission-api` systemd 서비스, 포트 8001, nginx가
  `/art-admission/`으로 경로 라우팅)에서 서비스되며, `main` 브랜치에서
  `api_art_admission.py`/`services/art_admission_service.py`/
  `services/art_admission_llm.py`가 바뀌면 GitHub Actions
  (`.github/workflows/deploy-art-admission-api.yml`)가 자동 배포합니다.
- `api_art_admission.py`의 `FO_ALLOWED_ORIGINS` 환경변수는 실제 FO 도메인으로
  제한되어 있어야 합니다.

## 화면 구성

FO의 메뉴는 홈 / 대학 찾기 / 입시 질문 / 서류 첨삭 4개로 고정입니다. 기존
Streamlit의 내부 메뉴를 그대로 복제하지 않고, 원장·학생·학부모 상담에 필요한
흐름만 담습니다.

| 파일 | 화면 | 연결된 API |
|---|---|---|
| `index.html` | 홈/랜딩 | `GET /stats`, `GET /universities` |
| `profile.html` | 준비 실기 종목/재료 입력 | - |
| `results.html` | 매칭 결과 + 전형 비교/일정 충돌 확인 + 공식 근거 패널 | `POST /prep-search`, `POST /compare-tracks`, `POST /simulate-multi-apply`, `GET /calendar-events`, `GET /universities/{university}` |
| `qa.html` | 입시 질문(AI) | `POST /qa` |
| `review.html` | 서류 첨삭(AI) + 후속 대화 | `GET /universities`, `POST /review-document`, `POST /review-chat` |

고교유형/내신/수능 입력 필드는 실제 매칭 로직에 반영되지 않아 profile.html에서
완전히 제거했습니다(지어내지 않기 위함).

## 전형 식별 규칙 (중요)

`track_name`(전형명, 예: "실기우수자전형")은 한 대학의 여러 학과가 그대로
공유하는 카테고리 이름이라 **절대 전형 식별자로 쓰면 안 됩니다**. 반드시
`university + campus + department` 조합으로 찾아야 합니다(현재 데이터셋
전체에서 이 조합만 유일함이 검증됨) - Evidence 패널/비교표/일정 API가 전부
이 규칙을 따릅니다.
