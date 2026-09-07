// 검증용 FO가 호출하는 API 서버 주소.
// 로컬 개발: uv run uvicorn 내작업폴더.api_art_admission:app --reload --port 8000
// 배포 후에는 실제 API 호스팅 주소(Render/Railway 등)로 이 한 줄만 바꾸면 된다.
window.API_BASE_URL = "https://api.unsuzone.com/art-admission";
