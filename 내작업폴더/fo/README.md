# ART BAUHAUS - 검증용 FO

Google Stitch로 디자인한 화면(`../stitch_art_admissions_intelligence_fo/`)의 코드를
가져와 실제 `api_art_admission.py`(FastAPI)와 연결한 정적 사이트입니다.
빌드 도구 없음 - Tailwind CDN + 순수 JS.

**중요**: Stitch가 만든 원본 목업에는 국민대/건국대/서울대/이화여대 등 우리
실제 데이터에 없는 학교명과 가상의 수치가 들어있었습니다. 이 폴더의 파일들은
그 가상 데이터를 전부 제거하고 실제 API 응답으로 대체한 버전입니다.

## 로컬 실행

```powershell
# 1. API 서버 (다른 터미널)
uv run uvicorn 내작업폴더.api_art_admission:app --reload --port 8000

# 2. 정적 파일 서버 (이 폴더 안에서)
cd 내작업폴더/fo
python -m http.server 5500
```

브라우저에서 http://localhost:5500/index.html 접속.

## 배포 시

1. API를 Render/Railway 등에 배포 (Streamlit Cloud는 FastAPI 못 띄움)
2. `config.js`의 `API_BASE_URL`을 배포된 API 주소로 변경
3. 이 `fo/` 폴더를 Vercel/Netlify/GitHub Pages 등에 정적 배포
4. 자체 도메인(예: artready.kr) 연결
5. `api_art_admission.py`의 `FO_ALLOWED_ORIGINS` 환경변수를 실제 FO 도메인으로 제한

## 화면 구성

| 파일 | 화면 | 연결된 API |
|---|---|---|
| `index.html` | 홈/랜딩 | `GET /universities` (통계 숫자만) |
| `profile.html` | 학생 조건 입력 | - |
| `results.html` | 매칭 결과 | `POST /prep-search` |
| `qa.html` | RAG 질의응답 | `POST /qa` |
| `review.html` | 서류 첨삭 | `GET /universities`, `POST /review-document` |

고교유형/내신/수능 입력 필드는 화면에 남아있지만 **아직 매칭 로직에 반영되지
않습니다** (백엔드 엔진이 지원하지 않음) - 지어내지 않기 위해 지금은 참고
표시로만 남겨뒀습니다.
