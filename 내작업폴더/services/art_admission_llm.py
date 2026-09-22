# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] LLM 연동 계층
================================================================================
- LLM은 절대 "새로운 사실"을 만들지 않는다. 답변 생성 시 항상 Neo4j에서 조회한
  official_facts/estimates JSON만 컨텍스트로 주고, 그 밖의 값은 지어내지 말라고
  시스템 프롬프트에 못박는다 (DART-Trace의 Zero-Mixing/정직한 추출 원칙과 동일).
- 서류/자소서 첨삭(review_document)은 사실 조회가 아니라 글쓰기 의견이므로
  "AI 추정 의견, 공식 평가 아님"을 항상 명시한다.
- 현재 이 프로젝트에 설정된 키는 OPENAI_API_KEY뿐이다. 다른 공급자는 키가 없으면
  자동으로 '사용 불가'로 표시되고 호출되지 않는다 - 없는 키로 조용히 실패하거나
  거짓 응답을 만들지 않기 위함.
================================================================================
"""

import os
import json
import time
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")

_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_GEMINI_KEY = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))

# 최신/고급 모델을 쓰려면 비밀번호(년월일 8자리)를 입력해야 한다 - 비용이 더 큰
# 모델을 아무나 실수로/장난으로 고르지 못하게 막는 용도일 뿐, 보안 목적이 아니다.
MODEL_PASSWORD = "20260907"

# 모델 레지스트리 - provider별 키 존재 여부로 available을 결정한다.
# gated=True인 모델은 화면에서 비밀번호를 맞춰야 선택/사용할 수 있다.
MODEL_REGISTRY: List[Dict[str, Any]] = [
    {"id": "gpt-4o-mini", "label": "GPT-4o mini (OpenAI)", "provider": "openai", "available": bool(_OPENAI_KEY), "gated": False},
    {"id": "gpt-4o", "label": "GPT-4o (OpenAI)", "provider": "openai", "available": bool(_OPENAI_KEY), "gated": False},
    {"id": "gpt-5.5", "label": "GPT-5.5 (OpenAI, 최신·고급)", "provider": "openai", "available": bool(_OPENAI_KEY), "gated": True},
    {"id": "o4-mini", "label": "o4-mini (OpenAI, 추론 특화·고급)", "provider": "openai", "available": bool(_OPENAI_KEY), "gated": True},
    # 2026-09-16: 엔티티 추출 모델 비교 실측용으로 추가. gpt-5.6-luna는 이전엔 여기
    # 등록 안 된 채로도 "우연히" 정상 동작했다(_model_info 폴백이 registry[0]로
    # 떨어져도 provider가 마침 openai로 같았기 때문) - 아래 _model_info 수정으로
    # 그런 우연에 기대는 구조 자체를 없앴으므로, 실제 쓰는 모델은 전부 명시 등록한다.
    {"id": "gpt-5.6-luna", "label": "GPT-5.6 Luna (OpenAI, 추론 모델)", "provider": "openai", "available": bool(_OPENAI_KEY), "gated": True},
    {"id": "claude-sonnet-5", "label": "Claude Sonnet 5 (Anthropic, 최신·고급)", "provider": "anthropic", "available": bool(_ANTHROPIC_KEY), "gated": True},
    {"id": "claude-opus-5", "label": "Claude Opus 5 (Anthropic, 최상급)", "provider": "anthropic", "available": bool(_ANTHROPIC_KEY), "gated": True},
    # 2026-09-16: gemini-1.5-pro, gemini-2.5-pro 둘 다 단종/신규사용자 차단 확인됨
    # (직접 호출해서 확인 - 2.5-pro는 "no longer available to new users" 에러,
    # 3.1-pro-preview로 옮기라고 API가 직접 안내함). 안내받은 대로 사용한다.
    {"id": "gemini-3.1-pro-preview", "label": "Gemini 3.1 Pro Preview (Google, 최신·고급)", "provider": "gemini", "available": bool(_GEMINI_KEY), "gated": True},
]


def get_available_models() -> List[Dict[str, Any]]:
    return MODEL_REGISTRY


# 2026-09-16: LLM 호출 예외(레이트리밋/지출한도/네트워크 오류 등)의 원문 메시지를
# 그대로 사용자에게 보여주면 "project_spend_limit_exceeded"처럼 내부 결제 상태나
# OpenAI 대시보드 URL까지 그대로 노출된다(실측 발견). 이 모듈의 모든 LLM 호출
# 실패 경로가 이 문구 하나로 통일해서 답하고, 실제 원인은 print로 서버 로그에만
# 남긴다 - api_art_admission.py에도 같은 문구의 사본이 있다(엔드포인트 레벨의
# 마지막 방어선용, 이 모듈이 예외를 안 삼키고 그냥 raise하는 경로를 위함).
_LLM_FRIENDLY_ERROR = "현재 AI 서비스 고도화 작업이 진행 중이라 일시적으로 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요."


def _model_info(model_id: str) -> Dict[str, Any]:
    for m in MODEL_REGISTRY:
        if m["id"] == model_id:
            return m
    # 2026-09-16: 예전엔 등록 안 된 모델명이 오면 조용히 MODEL_REGISTRY[0](gpt-4o-mini)
    # 정보로 대체했다 - provider까지 gpt-4o-mini 걸로 가져다 쓰다 보니, "claude-sonnet-5"
    # 처럼 다른 provider용 모델명을 실수로 넣으면 그 이름 그대로 OpenAI 엔드포인트로
    # 보내버려 엉뚱한 404 에러가 났다(실측 발견 - 원인 파악에 시간이 걸림). 모르는
    # 모델은 추측하지 말고 바로 에러를 내서, 등록을 빠뜨렸다는 걸 즉시 알 수 있게 한다.
    raise ValueError(f"'{model_id}'는 MODEL_REGISTRY에 등록되지 않은 모델입니다. 등록 후 다시 시도하세요.")


# gpt-5 계열/추론 특화 모델(o1/o3/o4)은 temperature를 기본값(1) 말고는 받지 않는다
# (실제로 0.0을 보내면 400 에러 - 직접 호출해서 확인함). 이런 모델은 temperature를
# 아예 안 보낸다.
_NO_CUSTOM_TEMPERATURE_PREFIXES = ("gpt-5", "o1", "o3", "o4")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def embed_text(text: str) -> List[float]:
    """OpenAI 임베딩 API로 텍스트 1건을 벡터로 변환한다. PDF 원문 청크 색인과
    사용자 질의 임베딩 양쪽에 공용으로 쓴다 - 반드시 같은 모델이어야 코사인 유사도가
    의미 있으므로 EMBEDDING_MODEL 상수 하나만 쓴다."""
    if not _OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_OPENAI_KEY}"}
    payload = {"model": EMBEDDING_MODEL, "input": text}
    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["data"][0]["embedding"]


# 2026-09-10 실측 사고: 타임아웃 30초 고정이었는데 GPT-5.5로 서류첨삭 시도 시
# "The read operation timed out"으로 실패했다. GPT-5.5/o-시리즈 같은 추론형
# 고급 모델은 답변 생성에 30초를 훌쩍 넘기는 경우가 흔하다 - 모델별로 여유
# 있게 타임아웃을 다르게 준다(빠른 기본 모델까지 무작정 오래 기다리게 하진
# 않되, 느린 고급 모델은 충분히 기다려준다).
def _llm_timeout_seconds(model: str) -> int:
    if model.startswith(_NO_CUSTOM_TEMPERATURE_PREFIXES):  # gpt-5*, o1/o3/o4 (추론형)
        return 150
    return 60


def _call_openai_messages(messages: List[Dict[str, str]], model: str, temperature: float = 0.0) -> str:
    if not _OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_OPENAI_KEY}"}
    payload: Dict[str, Any] = {"model": model, "messages": messages}
    if not model.startswith(_NO_CUSTOM_TEMPERATURE_PREFIXES):
        payload["temperature"] = temperature
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    # 2026-09-16: gpt-5.6-luna로 4,016개 청크를 8개 동시 호출로 밀어붙이다가
    # 429(Too Many Requests)에 전부 걸려버린 사고가 있었다 - 이 함수를 부르는
    # 쪽(예: 02_Art_Admission_Entity_Linker.py의 extract_entities_llm)이 예외를
    # 조용히 삼키고 빈 결과를 반환하는 구조라, 레이트리밋에 걸려도 "실패"로
    # 안 잡히고 그냥 "아무것도 못 찾았다"로 보여서 원인 파악이 어려웠다. 429/5xx는
    # 여기서 지수 백오프로 몇 번 재시도해서, 호출부까지 레이트리밋이 새어나가지
    # 않게 막는다(호출부 코드는 손댈 필요 없음).
    last_err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=_llm_timeout_seconds(model)) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code not in (429, 500, 502, 503, 504) or attempt == 3:
                raise
            time.sleep(2 ** attempt)  # 1, 2, 4초
    raise last_err


# 2026-09-22 [day47 재검토]: 강의 원본(교안_02)은 하위질문 분해를 Pydantic
# 스키마로 강제하는데, 우리는 자유 텍스트로 JSON을 받아 정규식으로 잘라
# 파싱하고 실패하면 원본 질문으로 조용히 폴백하는 방어 코드만 있었다 -
# LLM이 형식을 안 지킬 위험을 "감지 후 폴백"으로만 막았지 "애초에 못
# 어기게" 막진 않았다. OpenAI structured outputs(response_format=
# json_schema, strict=true)는 API 차원에서 스키마를 강제해서 이 실패
# 유형 자체를 없앤다 - Decomposition 전용으로 좁게 추가한다(전체 provider
# 추상화를 다 구조화 출력으로 바꾸는 건 지금 필요한 범위를 넘어선다).
def call_openai_json_schema(system_prompt: str, user_prompt: str, model: str,
                             schema_name: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    if not _OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {_OPENAI_KEY}"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "schema": schema, "strict": True},
        },
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=_llm_timeout_seconds(model)) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return json.loads(body["choices"][0]["message"]["content"])


def _call_anthropic_messages(messages: List[Dict[str, str]], model: str, temperature: float = 0.0) -> str:
    if not _ANTHROPIC_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY가 설정되어 있지 않습니다.")
    system_prompt = "\n".join(m["content"] for m in messages if m["role"] == "system")
    conv = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
    headers = {
        "Content-Type": "application/json",
        "x-api-key": _ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
    }
    payload: Dict[str, Any] = {"model": model, "system": system_prompt, "messages": conv, "max_tokens": 1024}
    # 2026-09-16: claude-sonnet-5/opus-5(추론 모델)는 temperature 파라미터 자체를
    # 거부한다("temperature is deprecated for this model" - 실제 호출로 확인). OpenAI의
    # gpt-5/o-계열과 같은 패턴이라 같은 접두어 목록으로 판단해 아예 안 보낸다.
    if not model.startswith(("claude-sonnet-5", "claude-opus-5")):
        payload["temperature"] = temperature
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=_llm_timeout_seconds(model)) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in body.get("content", []) if b.get("type") == "text")


def _call_gemini_messages(messages: List[Dict[str, str]], model: str, temperature: float = 0.0) -> str:
    if not _GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY가 설정되어 있지 않습니다.")
    system_prompt = "\n".join(m["content"] for m in messages if m["role"] == "system")
    contents = []
    for m in messages:
        if m["role"] == "system":
            continue
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload: Dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": temperature}}
    if system_prompt:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={_GEMINI_KEY}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=_llm_timeout_seconds(model)) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["candidates"][0]["content"]["parts"][0]["text"]


def _call_llm_messages(messages: List[Dict[str, str]], model_id: str, temperature: float = 0.0) -> str:
    info = _model_info(model_id)
    if not info["available"]:
        raise RuntimeError(f"'{info['label']}'는 API 키가 설정되어 있지 않아 사용할 수 없습니다.")
    if info["provider"] == "openai":
        return _call_openai_messages(messages, model_id, temperature)
    if info["provider"] == "anthropic":
        return _call_anthropic_messages(messages, model_id, temperature)
    if info["provider"] == "gemini":
        return _call_gemini_messages(messages, model_id, temperature)
    raise RuntimeError(f"provider '{info['provider']}'는 아직 지원되지 않습니다.")


def _call_llm(system_prompt: str, user_prompt: str, model_id: str, temperature: float = 0.0) -> str:
    return _call_llm_messages(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        model_id, temperature,
    )


_RERANK_SYSTEM_PROMPT = """당신은 검색 결과 재순위화기입니다. 주어진 질문과 번호가 매겨진 후보
발췌문 목록을 보고, 각 발췌문이 그 질문에 답하는 데 얼마나 직접적으로 관련 있는지 0~10점으로
채점하십시오. 반드시 JSON 배열로만 응답하고 다른 말은 절대 덧붙이지 마십시오.
형식: [{"index": 0, "score": 8}, {"index": 1, "score": 3}, ...]
새로운 사실을 만들지 말고, 오직 관련도 점수만 매기십시오."""


_cross_encoder = None
_cross_encoder_failed = False


def _get_cross_encoder():
    """BGE-Reranker(다국어 크로스인코더)를 지연 로딩한다. GPU 없이 CPU로 돌아가고,
    한 번 로드하면 프로세스 생존 기간 내내 재사용한다(모듈 전역 싱글턴). 모델을
    못 받거나 로드에 실패하면 이후 호출에서는 재시도하지 않고 바로 LLM 재순위화로
    폴백한다 - 매 요청마다 다시 실패하며 지연시간만 잡아먹지 않기 위함."""
    global _cross_encoder, _cross_encoder_failed
    if _cross_encoder_failed:
        return None
    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
            _cross_encoder = CrossEncoder("BAAI/bge-reranker-base", max_length=512, device="cpu")
        except Exception:
            _cross_encoder_failed = True
            return None
    return _cross_encoder


def warm_up_reranker() -> None:
    """서버 프로세스가 막 시작됐을 때(배포 직후) 실제 사용자의 첫 /qa 질문이
    크로스인코더 모델 로딩 비용(약 15초)을 떠안는 문제가 있었다 - 배포 직후
    질문한 사용자가 "왜 이렇게 오래 걸리지?"라고 느낀 원인이 이거였음(실측
    확인: 1차 호출 17.5초 vs 같은 프로세스 내 2차 호출 3.2초). 서버 시작 시
    미리 한 번 로딩해두면 실제 사용자는 이 비용을 겪지 않는다. 실패해도
    조용히 넘어간다 - 어차피 cross_encoder_rerank가 실패 시 LLM 재순위화로
    자동 폴백하므로 워밍업 실패가 서비스 장애로 이어지지 않는다."""
    try:
        _get_cross_encoder()
    except Exception:
        pass


def cross_encoder_rerank(query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> Optional[List[Dict[str, Any]]]:
    """전용 크로스인코더 리랭커(day48). LLM에게 "몇 점이야?"라고 채팅으로 물어보던
    기존 rerank_chunks와 달리, 애초에 "질문-문서 쌍 관련도 점수"만 내도록 학습된
    작은 모델이라 GPU 없이도 빠르고(수백 ms), 결정적이고(같은 입력엔 같은 점수),
    LLM 호출 비용이 전혀 없다. 모델 로드나 추론이 실패하면 None을 반환해서 호출부가
    기존 LLM 재순위화로 폴백하게 한다."""
    if not candidates:
        return []
    encoder = _get_cross_encoder()
    if encoder is None:
        return None
    try:
        pairs = [[query, c["text"][:512]] for c in candidates]
        scores = encoder.predict(pairs)
        for c, score in zip(candidates, scores):
            c["rerank_score"] = float(score)
            c["rerank_method"] = "cross_encoder"
        candidates = sorted(candidates, key=lambda c: c["rerank_score"], reverse=True)
        return candidates[:top_k]
    except Exception:
        return None


def rerank_chunks(query: str, candidates: List[Dict[str, Any]], model_id: str = "gpt-4o-mini",
                   top_k: int = 5) -> List[Dict[str, Any]]:
    """하이브리드 검색 후보를 LLM으로 재순위화한다 (cross-encoder 대용 - 전용 rerank API가
    없으므로 LLM에게 관련도 점수만 매기게 함). 실패하면 원래 순서(융합점수 순) 그대로
    top_k만 잘라 반환한다 - 재순위화 실패가 검색 자체를 죽이지 않게 함."""
    if not candidates:
        return []
    info = _model_info(model_id)
    if not info["available"]:
        return candidates[:top_k]

    listing = "\n\n".join(f"[{i}] (대학: {c['university']}) {c['text'][:500]}" for i, c in enumerate(candidates))
    user_prompt = f"질문: {query}\n\n후보 발췌문 목록:\n{listing}"
    try:
        raw = _call_llm(_RERANK_SYSTEM_PROMPT, user_prompt, model_id, temperature=0.0)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        scores = json.loads(cleaned)
        score_map = {item["index"]: item["score"] for item in scores if "index" in item}
        for i, c in enumerate(candidates):
            c["rerank_score"] = score_map.get(i, 0)
            c["rerank_method"] = "llm"
        candidates = sorted(candidates, key=lambda c: c.get("rerank_score", 0), reverse=True)
    except Exception:
        pass
    return candidates[:top_k]


_QA_SYSTEM_PROMPT = """당신은 "미술 실기 입시 도우미"의 답변 생성기입니다. 반드시 아래 규칙을 지키십시오.

1. 사용자 메시지에 JSON으로 주어지는 "context_tracks"(공식 모집요강 사실),
   "context_estimates"(비공식 추정치), "context_raw_excerpts"(PDF 원문 발췌, 의미기반
   검색 결과) 안에 있는 값만 사용하십시오. 그 안에 없는 학교/학과/숫자/날짜/조건은
   절대 새로 만들어내지 마십시오. 모르면 반드시 "정보 없음"이라고 답하십시오.
1-1. 아래 두 질문 유형은 겉보기에 비슷해 보이지만("실기로 지원 가능한 학교") 서로
   다른 규칙을 따라야 합니다 - 절대 섞지 마십시오:
   (a) 사용자가 "소묘"/"기초디자인" 같은 실기유형 키워드를 질문 문장에 직접 이름으로
       언급하며 "그 실기로 볼 수 있는 학교"를 물은 경우 → context_tracks의 각 항목에
       있는 exam_type_keyword_match 값을 그대로 따르십시오. true인 트랙만 직접적인
       답으로 제시하고, false인 트랙은 "실기유형은 다름"이라고 밝히십시오.
   (b) 사용자가 특정 학교/학과 이름을 기준으로 "OO대학 OO학과와 같은/호환되는 실기로
       지원 가능한 학교"를 물은 경우(실기유형 키워드를 직접 이름으로 대지 않고 다른
       학교를 기준점으로 삼은 경우) → 이건 exam_type_keyword_match와 전혀 무관합니다.
       context_tracks에는 그 기준 학교 자신의 트랙만 들어있어 다른 학교 비교에 애초에
       쓸 수 없는 데이터이므로 절대 근거로 삼지 마십시오. 대신 context_compatible_tracks
       (규칙 7)를 유일한 근거로 써서 답하십시오 - exam_type_keyword_match가 전부
       false라는 이유로 "호환 학교가 없다"고 결론짓지 마십시오, 그건 이 질문 유형과
       무관한 값입니다.
   두 경우를 헷갈리면 실제로 존재하는 호환 학교를 "없다"고 잘못 답하게 되므로
   (b) 유형인지 먼저 판단한 뒤 규칙을 적용하십시오.
2. context_raw_excerpts는 구조화되지 않은 PDF 원문 그대로이므로, 여기서 근거를
   찾으면 반드시 어느 대학의 몇 페이지에서 나온 내용인지(university, page_start~page_end)
   함께 밝히고, 원문에 실제로 있는 문장만 인용/요약하십시오. 원문에 없는 해석을
   덧붙이지 마십시오.
3. 서로 다른 admission_year(학년도)를 가진 전형끼리는 같은 회차인 것처럼 비교하거나
   섞어서 말하지 마십시오. 답변에서 학년도를 항상 함께 표기하십시오.
4. "공식 사실"(context_tracks)과 "추정치"(context_estimates)를 답변에서 절대 같은
   문장으로 섞지 말고, 추정치를 말할 때는 반드시 "(추정치, 공식 아님)"이라고 표시하십시오.
5. 답변 끝에 반드시 "출처:" 항목으로, 답변에 사용한 각 트랙의 source_url 또는
   원문 발췌의 (대학명, 페이지)를 context에 있는 값 그대로(가공하지 말고) 나열하십시오.
   context에 없는 URL/페이지는 쓰지 마십시오.
6. "context_graph_related"는 질문에 나온 학교/학과와 같은 커뮤니티(동시출현 그래프
   상 자주 함께 언급되는 군집)로 묶인 다른 학교/학과 이름 목록입니다. 이것은
   사실이 아니라 구조적 힌트일 뿐입니다 - 여기 나온 학교에 대한 날짜/점수/조건 등
   구체적 사실은 그 학교가 context_tracks나 context_raw_excerpts에도 실제로 나올
   때만 말하십시오. 목록에만 있고 다른 context에 없다면 "○○대학교도 같은 계열이라
   비교해볼 만합니다" 정도의 제안으로만 언급하고, 세부 사실을 지어내지 마십시오.
7. "context_compatible_tracks"는 질문에서 인식된 기준 학교/학과와 실기유형·허용재료
   단어가 겹치는 다른 학교/학과를 실제 구조화 데이터로 계산한 결과입니다. 각 항목의
   shared_keywords(실기유형 자체가 겹침)와 shared_materials(재료·규격만 겹침)는
   전혀 다른 신뢰도입니다 - 반드시 구분해서 답하십시오:
   - shared_keywords가 있는 항목만 "같은 실기", "호환 전형"이라고 부르십시오.
   - shared_materials만 있고 shared_keywords가 비어 있는 항목은 "같은 실기"라고
     절대 부르지 말고, "재료(예: 연필)만 겹치고 실기 종목 자체는 다릅니다 - 준비
     내용을 원문에서 직접 확인하세요" 처럼 재료만 겹친다는 걸 명확히 표시하십시오.
   목록에 있는 학교/학과명과 shared_keywords/shared_materials를 그대로 인용하고,
   이 목록이 비어 있으면 "적재된 데이터 범위 내에서는 실기유형/재료가 겹치는
   다른 학교를 찾지 못했습니다"라고 명확히 답하고, 지어내지 마십시오.
   목록은 shared_keywords가 있는 항목(정렬 순서상 항상 앞쪽에 옵니다)이 우선입니다:
   그 항목들은 개수가 몇 건이든 절대 요약하지 말고 학교/학과명을 전부 빠짐없이
   나열하십시오(이게 이 질문 유형에서 가장 중요한 답입니다 - 실제로 존재하는데도
   "호환 학교가 없다"고 답하면 안 됩니다). shared_materials만 있는(재료만 겹치는)
   항목은 개수가 많을 수 있으니, 전부 나열하는 대신 "그 외 재료만 비슷한 전형은
   총 N건(대표로 학교 2~3곳: ...)" 처럼 총 개수와 대표 사례 몇 개만 언급해도
   됩니다 - 정확도가 더 중요한 shared_keywords 목록에 답변 분량을 쓰십시오.
8. 사용자 질문이 context에 있는 정보로 확인되지 않으면, 절대 짐작하거나 일반
   상식으로 답하지 말고 정확히 이렇게 답하십시오: "현재 적재된 공식 모집요강
   데이터에서 확인하지 못했습니다. 최종 지원 전 해당 대학 입학처 공지를
   확인하세요."
9. 간결하고 친절한 한국어로, 수험생에게 답하듯 작성하십시오. "RAG 검증됨",
   "실측 검증된" 같은 확정적 신뢰 문구는 쓰지 마십시오 - 근거는 출처 링크로만
   보여주고, 검증을 보장하는 표현은 쓰지 않습니다.
"""


# day62~64: 코드 레벨 가드레일. 프롬프트에 "쓰지 마라"고 적어두는 것만으로는 LLM이
# 언젠가 규칙을 어길 수 있다(프롬프트는 강제력이 없다) - 그래서 답변이 나온 뒤 문자열
# 자체를 코드로 검사하는 마지막 방어선을 둔다.
_BANNED_PHRASES = [
    "RAG VERIFIED", "RAG 검증됨", "실측 검증", "실측 검증된", "AI가 찾았다",
    "100% 정확", "100% 무환각", "다른 AI는 거짓말", "합격 예측", "합격을 보장",
    "내신 역전 보장", "합격할 것 같다", "떨어질 것 같다",
]


def _strip_banned_phrases(answer: str) -> tuple:
    """금지 문구가 실제로 있으면 그 문구만 지우고(문장 전체를 버리지 않음), 무엇을
    지웠는지 로그용으로 같이 돌려준다."""
    hit = [p for p in _BANNED_PHRASES if p in answer]
    cleaned = answer
    for p in hit:
        cleaned = cleaned.replace(p, "")
    return cleaned, hit


def _self_check_grounding(answer: str, context_tracks: List[Dict[str, Any]],
                           context_compatible_tracks: List[Dict[str, Any]],
                           context_graph_related: List[Dict[str, Any]],
                           all_universities: Optional[List[str]],
                           query: str = "") -> List[str]:
    """Self-RAG류 자기검증(day53~54): 답변에 등장하는 학교명이 이번 요청에 실제로
    근거로 준 context 안에 있었는지 대조한다. all_universities(전체 등록 대학 목록)
    중 하나가 답변 텍스트에 등장했는데 이번 context_tracks/compatible/graph_related
    어디에도 없다면, LLM이 아예 다른 학교를 지어냈거나 착각한 것일 위험이 있다.

    2026-09-09 오탐 수정: query(사용자 질문 원문)에 이미 등장한 학교명은 grounded로
    취급한다. "성적 추천" 결과 화면의 "이 결과로 질문하기" 기능이 상위 학교 요약을
    질문 앞에 그대로 붙여서 보내는데, 이 요약 자체가 실제 그래프 계산 결과(허구가
    아님)라서 LLM이 그 학교명을 답변에서 그대로 언급하면 "이번 조회 근거에는
    없다"는 이유로 오탐(false positive)이 났다 - 질문에 이미 있던 이름을 답변에서
    반복하는 건 지어낸 게 아니라 질문 그대로 답한 것이다."""
    if not all_universities:
        return []
    grounded_names = {t["university"] for t in context_tracks}
    grounded_names |= {t["university"] for t in context_compatible_tracks}
    grounded_names |= {r.get("name") for r in context_graph_related if r.get("name")}
    grounded_names |= {name for name in all_universities if name in query}
    issues = []
    for name in all_universities:
        if name in answer and name not in grounded_names:
            issues.append(f"'{name}'가 답변에 등장하지만 이번 조회의 근거 데이터에는 없었습니다(환각 의심)")
    return issues


_GIVE_UP_PHRASES = ("확인하지 못했습니다", "찾지 못했습니다", "찾을 수 없습니다")


def _self_check_compat_claim_keyword(answer: str, context_compatible_tracks: List[Dict[str, Any]]) -> List[str]:
    """재료만 겹치는 걸 '같은 실기'/'호환'이라고 부르면 안 된다는 규칙(§4)을 코드로 재검증.
    두 방향의 실수를 모두 잡는다:
    1. (과잉 주장) 답변에 '호환'/'같은 실기' 표현이 있는데 shared_keywords(실기유형
       자체 일치)가 있는 후보가 하나도 없으면, 근거 없이 그 표현을 썼다는 뜻이다.
    2. (포기) context_compatible_tracks에 shared_keywords가 있는 진짜 호환 학교가
       있는데도 답변이 '확인하지 못했습니다'류로 포기하면, 근거를 두고도 안 쓴
       것이다(2026-09-18 실측 발견 - 한예종 무대미술과 질문에서 context에 21건의
       진짜 호환 학교가 있었는데도 gpt-4o-mini가 반복해서 포기하는 현상 확인)."""
    warnings = []
    has_exact_match = any((c.get("shared_keywords") or []) for c in context_compatible_tracks)
    if ("호환" in answer or "같은 실기" in answer) and not has_exact_match:
        warnings.append("'호환'/'같은 실기' 표현이 쓰였지만 실기유형 자체가 일치하는(shared_keywords) 근거가 없습니다")
    if has_exact_match and any(p in answer for p in _GIVE_UP_PHRASES):
        warnings.append(
            "context_compatible_tracks 안에 실기유형이 실제로 일치하는(shared_keywords) 학교가 "
            "있는데도 답변이 '확인하지 못했다'는 취지로 포기했습니다 - 그 목록을 실제로 사용해서 "
            "구체적인 학교 이름과 실기유형을 나열해 답하십시오"
        )
    return warnings


def _self_check_compat_claim(answer: str, context_compatible_tracks: List[Dict[str, Any]]) -> List[str]:
    """_self_check_compat_claim_keyword()의 문자열 매칭은 '호환'/'같은 실기'라는
    정확한 단어나 3개의 고정 포기 문구만 잡아서, "성격이 비슷한 학교"나 "안내드리기
    어렵습니다"처럼 같은 의미를 다른 표현으로 썼을 때 놓친다(2026-09-22 A/B 실측:
    8개 케이스 중 키워드 5/8, Jev(의미 판정) 8/8 - 놓친 3개가 전부 이런 패러프레이즈).
    Jev 호출 실패(키 없음/네트워크 오류) 시 기존 키워드 방식으로 자동 폴백한다.

    2026-09-22 실측 발견(15문항 전체 파이프라인 스윕): context_compatible_tracks가
    애초에 빈 리스트(= 이번 질문이 호환학교 검색 자체를 시도하지 않은 경우 - 예:
    "소묘로 지원 가능한 학교", 성적 추천 질문)일 때도 Jev가 답변 속 '~로 일치합니다'
    같은 무관한 표현을 호환 과잉주장으로 오판해서 정상 답변에 경고+불필요한 재시도를
    유발했다(get_compatible_tracks_for_query가 실제로 0건을 반환하는 쿼리로 확인됨).
    이 체크는 '호환학교 검색이 실제로 시도된 질문'에만 의미가 있으므로,
    context_compatible_tracks가 처음부터 비어 있으면(후보가 전혀 없어서 shared_keywords/
    shared_materials 어느 쪽도 없는 게 아니라, 애초에 비교 기준 자체를 못 찾은 경우)
    Jev를 호출하지 않고 바로 통과시킨다."""
    if not context_compatible_tracks:
        return []
    has_exact_match = any((c.get("shared_keywords") or []) for c in context_compatible_tracks)
    try:
        from typesafe_sdk import Noul, TypeSafeClient
        client = TypeSafeClient(timeout=8.0)
        model = os.getenv("TYPESAFE_MODEL", "jev-1.13.0")
        warnings = []
        if not has_exact_match:
            resp = client.system_one(
                model=model, state=answer,
                questions={"overclaim": Noul(instructions=(
                    "실제로는 이 질문에 대해 실기유형(과제/재료)이 정확히 일치하는 진짜 "
                    "호환 학교 후보가 하나도 없는 상태입니다. 그런데 아래 답변이 특정 "
                    "학교를 '호환된다'/'유사하다'/'성격이 비슷하다'/'같은 계열이다' 등의 "
                    "취지로 실제로 존재한다고 주장하고 있나요? 단순히 '찾지 못했다'는 "
                    "정직한 답변이면 '아니오'입니다."
                ))},
            )
            if resp.answers["overclaim"].noul >= 0.5:
                warnings.append("'호환'/'유사' 취지의 주장이 있지만 실기유형 자체가 일치하는 근거가 없습니다(Jev 판정)")
        if has_exact_match:
            resp = client.system_one(
                model=model, state=answer,
                questions={"giveup": Noul(instructions=(
                    "실제로는 실기유형(과제/재료)이 정확히 일치하는 진짜 호환 학교 후보가 "
                    "존재하는 상태입니다. 그런데 아래 답변이 그런 학교를 찾지 못했다/확인할 "
                    "수 없다/안내하기 어렵다는 취지로 실질적으로 포기하고 있나요? 실제로 "
                    "구체적인 학교명을 제시하며 답했다면 '아니오'입니다."
                ))},
            )
            if resp.answers["giveup"].noul >= 0.5:
                warnings.append(
                    "실기유형이 실제로 일치하는 호환 학교 후보가 있는데도 답변이 사실상 "
                    "포기했습니다(Jev 판정) - 구체적인 학교 이름과 실기유형을 나열해 답하십시오"
                )
        return warnings
    except Exception:
        return _self_check_compat_claim_keyword(answer, context_compatible_tracks)


def answer_with_llm(context_tracks: List[Dict[str, Any]], context_estimates: List[Dict[str, Any]],
                     query: str, model_id: str = "gpt-4o-mini",
                     context_raw_excerpts: Optional[List[Dict[str, Any]]] = None,
                     context_graph_related: Optional[List[Dict[str, Any]]] = None,
                     context_compatible_tracks: Optional[List[Dict[str, Any]]] = None,
                     all_universities: Optional[List[str]] = None) -> Dict[str, Any]:
    """조회된 그래프 사실(context_tracks/estimates), PDF 원문 벡터검색 결과
    (context_raw_excerpts), 개체 동시출현 그래프에서 뽑은 관련 학교 힌트
    (context_graph_related, GraphRAG 연동), 그리고 실기유형/재료 키워드가 겹치는
    구조화 호환학교 검색 결과(context_compatible_tracks, find_compatible_tracks)를
    근거로 LLM이 자연어 답변을 생성한다. 넷 다 비어 있으면 LLM 호출 없이 바로
    '정보 없음'을 반환한다 (환각 방지)."""
    context_raw_excerpts = context_raw_excerpts or []
    context_graph_related = context_graph_related or []
    context_compatible_tracks = context_compatible_tracks or []
    if not context_tracks and not context_estimates and not context_raw_excerpts and not context_compatible_tracks:
        return {
            "answer": "현재 적재된 공식 모집요강 데이터에서 확인하지 못했습니다. 학교명을 정확히 포함해서 다시 질문하거나, 최종 지원 전 해당 대학 입학처 공지를 확인하세요.",
            "model": model_id,
            "grounded_on": [],
        }

    user_payload = {
        "question": query,
        "context_tracks": context_tracks,
        "context_estimates": context_estimates,
        "context_raw_excerpts": context_raw_excerpts,
        "context_graph_related": context_graph_related,
        "context_compatible_tracks": context_compatible_tracks,
    }
    user_prompt = json.dumps(user_payload, ensure_ascii=False, indent=2)

    try:
        answer = _call_llm(_QA_SYSTEM_PROMPT, user_prompt, model_id, temperature=0.0)
    except Exception as e:
        # 2026-09-16: 여기서 예외를 삼키고 "answer" 필드에 원문 그대로 넣어 반환하는
        # 구조라, api_art_admission.py의 /qa, /agent-chat try/except(원문 에러 노출
        # 방지용)를 그대로 통과해 사용자 화면에 지출한도 초과 메시지가 그대로 샜었다
        # (실측 발견). 원인은 로그에만 남기고, 사용자에게는 순화된 문구만 준다.
        print(f"[answer_with_llm] LLM 호출 실패: {e}")
        return {
            "answer": _LLM_FRIENDLY_ERROR + "\n\n(위쪽 규칙기반 조회 결과를 참고해주세요.)",
            "model": model_id,
            "grounded_on": [],
            "error": True,
        }

    # Self-RAG류 자기검증 루프(day53~54): 생성된 답변을 코드로 재검사해서 문제가
    # 있으면 그 문제를 구체적으로 지적하며 딱 한 번만 재생성을 시도한다(무한루프 방지 -
    # 비용은 최대 2배로만 늘어남). 재시도 후에도 문제가 남으면 경고를 붙여서라도
    # 투명하게 알린다 - 조용히 숨기지 않는다.
    self_check_warnings = (
        _self_check_grounding(answer, context_tracks, context_compatible_tracks, context_graph_related, all_universities, query)
        + _self_check_compat_claim(answer, context_compatible_tracks)
    )
    if self_check_warnings:
        retry_prompt = (
            user_prompt
            + "\n\n[자기검증 실패 - 재작성 필요]\n이전 답변에서 다음 문제가 발견되었습니다:\n- "
            + "\n- ".join(self_check_warnings)
            + "\n위 문제를 고쳐서 규칙을 지키는 답변으로 다시 작성하십시오."
        )
        try:
            retried = _call_llm(_QA_SYSTEM_PROMPT, retry_prompt, model_id, temperature=0.0)
            retry_issues = (
                _self_check_grounding(retried, context_tracks, context_compatible_tracks, context_graph_related, all_universities, query)
                + _self_check_compat_claim(retried, context_compatible_tracks)
            )
            answer = retried
            self_check_warnings = retry_issues
        except Exception:
            pass  # 재시도 실패하면 원래 답변 유지, 아래에서 경고만 표시

    answer, banned_hit = _strip_banned_phrases(answer)

    grounded_on = [f"{t['university']} {t['department']}" for t in context_tracks]
    grounded_on += [f"{e['university']} p.{e.get('page_start')}-{e.get('page_end')}" for e in context_raw_excerpts]
    result = {
        "answer": answer,
        "model": model_id,
        "grounded_on": grounded_on,
    }
    if self_check_warnings or banned_hit:
        result["self_check_warnings"] = self_check_warnings + [f"금지 문구 제거됨: {p}" for p in banned_hit]
    return result


_REVIEW_SYSTEM_PROMPT = """당신은 대학 미술 실기 입시 수험생의 서류(자소서/미술활동보고서 등)를
첨삭해주는 AI 도우미입니다. 반드시 아래 규칙을 지키십시오.

1. 당신은 이 지원자의 실제 합격 가능성이나 합격 여부를 절대 단정하지 마십시오.
   ("합격할 것 같다/안 될 것 같다" 같은 표현 금지)
2. 사실관계(예: 지원자가 언급한 대회 수상 경력이 진짜인지)를 검증할 수 없다는 점을
   답변 앞부분에 명시하십시오.
3. 글쓰기 관점(논리 구성, 구체성, 진정성, 분량, 반복/상투적 표현 여부)에서만
   강점과 개선점을 제시하고, 개선점마다 구체적인 수정 방향을 제안하십시오.
4. 한국어로, 존중하는 어조로 작성하십시오.
5. "감지된 계열 정보"가 주어지면, 이 지원자가 어떤 실기/전형 계열(예: 회화 계열,
   디자인 계열, 서류/면접 중심 전형)에 해당하는지 참고해서 그 계열에 맞는 어조와
   강조점으로 피드백하십시오. 단, 이 정보만으로 특정 대학/학과에 대한 사실을
   단정하지 말고 어디까지나 글쓰기 방향을 잡는 참고용으로만 쓰십시오.
6. "해당 학교 서류 규정 원문 발췌"가 주어지면, 그 학교는 다른 학교와 서류 규정이
   다를 수 있으므로 반드시 그 발췌 안에 실제로 있는 규정(분량/글자수 제한, 블라인드
   평가로 인한 특정 정보 기재 금지, 표절·대필 금지 등)만 근거로 지원자의 글이
   그 규정을 어기고 있지 않은지 구체적으로 짚어주십시오. 발췌에 없는 규정을
   그 학교 규정인 것처럼 지어내지 마십시오. 규정 발췌를 찾았는지 여부를 알리는
   화면 배너는 이 답변과 별개로 앱이 결정론적으로 표시하므로, 당신은 답변 맨
   앞이나 다른 곳에 "규정을 확인하지 못했습니다/확인했습니다" 같은 자체 판단
   문장을 절대 추가로 쓰지 마십시오 - 발췌가 있으면 그 내용을 근거로 첨삭하고,
   없으면 학교 규정 언급 없이 그냥 일반 글쓰기 관점으로만 첨삭하십시오(found/not
   found 여부는 아래 7번의 마지막 섹션 한 줄에서만 언급).
7. 답변은 반드시 아래 5개 섹션을 이 순서 그대로, 이 제목 그대로(### 헤더) 써서
   구성하십시오. 근거가 없는 섹션은 "해당 없음"이라고 짧게 쓰고 넘어가되,
   섹션 자체를 생략하지는 마십시오.
   ### 강점
   ### 입시 관점의 부족한 근거
   ### 개선 포인트
   ### 수정 예시
   ### 적용한 학교별 규정 근거
   마지막 섹션("적용한 학교별 규정 근거")은 반드시 아래 세 가지 중 정확히 하나로만
   쓰고, 서로 절대 혼동하지 마십시오:
   - "해당 학교 서류 규정 원문 발췌" 자체가 비어 있었다면: "적용한 학교별 규정
     없음(일반 글쓰기 관점)"이라고만 쓰십시오.
   - 발췌는 있었지만 그 안에 이 글에 적용할 만한 구체적 작성 규정(분량/글자수
     제한, 특정 정보 기재 금지, 표절·대필 금지 등)이 없었다면(예: 접수일정,
     평가기준 안내 같은 절차성 내용뿐이었다면): "학교 규정 발췌를 확인했으나
     이 글에 직접 적용할 작성 규정은 없었습니다(참고: [발췌 내용을 한 줄로 요약])"
     라고 쓰십시오. 이 경우 "규정 없음"이라고 단정하지 말고 반드시 발췌를
     확인했다는 사실을 먼저 밝히십시오.
   - 발췌 안에 실제로 적용한 규정이 있었다면: 그 규정을 한 줄로 인용/요약하십시오.
"""


def review_document(text: str, model_id: str = "gpt-4o-mini", doc_type: str = "자기소개서/활동보고서",
                     graph_hint: Optional[List[Dict[str, Any]]] = None,
                     university: Optional[str] = None,
                     context_doc_rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """서류/자소서 텍스트를 AI가 글쓰기 관점에서 첨삭한다. 사실 판정이 아니라
    의견이므로 화면에서도 반드시 '공식 평가 아님' 라벨을 별도로 붙여야 한다.
    graph_hint(GraphRAG 연동): 개체 동시출현 그래프에서 이름매칭으로 감지된
    학교/학과와 그 커뮤니티 라벨 - 어떤 계열 글인지 감을 잡는 참고 정보로만 쓴다.
    context_doc_rules: 학교마다 다른 서류 규정을 실제 PDF 원문에서 찾아온 발췌
    (get_document_rule_excerpts) - 학교를 지정했는데 발췌가 비어 있으면 그 학교의
    규정 원문을 못 찾았다는 뜻이고, LLM이 규정을 지어내지 않도록 프롬프트에서 못박는다."""
    text = (text or "").strip()
    if not text:
        return {"feedback": "첨삭할 텍스트가 비어 있습니다.", "model": model_id, "error": True}

    hint_line = ""
    if graph_hint:
        labels = sorted({h["community_label"] for h in graph_hint if h.get("community_label")})
        names = [h["name"] for h in graph_hint]
        hint_line = f"\n\n감지된 계열 정보(참고용, 사실 단정 금지): 언급된 개체 {names} / 계열 {labels}"

    context_doc_rules = context_doc_rules or []
    rules_block = ""
    if university:
        if context_doc_rules:
            excerpts = "\n\n".join(
                f"[p.{r.get('page_start')}-{r.get('page_end')}] {r['text'][:600]}" for r in context_doc_rules
            )
            rules_block = f"\n\n해당 학교({university}) 서류 규정 원문 발췌:\n{excerpts}"
        else:
            rules_block = f"\n\n해당 학교({university}) 서류 규정 원문 발췌: (찾지 못함 - 빈 목록)"

    user_prompt = f"문서 종류: {doc_type}\n\n--- 첨삭할 텍스트 ---\n{text[:12000]}{hint_line}{rules_block}"

    try:
        feedback = _call_llm(_REVIEW_SYSTEM_PROMPT, user_prompt, model_id, temperature=0.3)
    except Exception as e:
        print(f"[review_document] LLM 호출 실패: {e}")
        return {"feedback": _LLM_FRIENDLY_ERROR, "model": model_id, "error": True}

    return {"feedback": feedback, "model": model_id}


_REVIEW_CHAT_SYSTEM_PROMPT = _REVIEW_SYSTEM_PROMPT + """

지금은 방금 드린 첨삭 의견에 대해 사용자와 이어서 대화하며 보완하는 중입니다.
사용자가 질문을 하거나, 수정한 문장/문단을 다시 보여주면 같은 원칙
(합격 가능성 단정 금지, 사실관계 검증 불가 명시, 글쓰기 관점 피드백만 제공)을
유지하면서 대화를 이어가십시오. 앞서 나온 원본 문서와 첫 첨삭 내용을 계속 기억하고
일관되게 답하십시오. 단, 위의 "5개 섹션(### 강점 ~ ### 적용한 학교별 규정 근거)"
형식은 최초 첨삭 1회에만 적용됩니다 - 이 대화 턴에서는 그 형식을 강제로 반복하지
말고, 사용자의 질문에 자연스러운 대화체로 답하십시오.

사용자가 "보완해서 다시 써줘" 등 재작성/수정을 요청하면, 다시 쓴 글만 덧붙이지
말고 반드시 다음 두 가지를 함께 답하십시오(위에 "해당 학교 서류 규정 원문 발췌"가
주어진 경우에 한함 - 없으면 이 두 가지는 생략하고 일반 글쓰기 관점으로만 안내):
1. 이번에 다시 쓰면서 그 발췌 중 실제로 반영한 규정이 있다면 어떤 규정을 근거로
   무엇을 바꿨는지 한두 문장으로 밝히십시오. 발췌 안에 이 글에 적용할 규정이
   없었다면 "이번 재작성에는 적용할 학교 규정이 없었습니다"라고 명시하십시오.
   규정을 지어내지 마십시오.
2. 다시 쓴 글이 그 발췌의 규정(분량/글자 수 제한, 기재 금지 정보, 표절·대필 금지 등)에
   여전히 어긋나거나 애매한 부분이 있으면, 어떤 규정 때문에 어느 부분을 더
   손봐야 하는지 구체적으로 짚어주십시오. 문제없으면 "규정 위반 소지 없음"이라고
   짧게 밝히십시오.
"""


def chat_about_review(doc_text: str, doc_type: str, history: List[Dict[str, str]],
                       model_id: str = "gpt-4o-mini", university: Optional[str] = None,
                       context_doc_rules: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """서류 첨삭 후 이어지는 대화. history는 [{'role': 'assistant'|'user', 'content': ...}, ...]
    형태로, 최초 첨삭(assistant) 이후 사용자와 주고받은 턴을 그대로 담아 전달한다.
    university/context_doc_rules는 최초 첨삭(review_document)에 준 것과 동일한 학교
    규정 발췌를 그대로 다시 넣어준다 - 이게 없으면 이어지는 대화에서 모델이 "규정을
    확인할 수 없다"고 답해 최초 첨삭 결과와 모순되는 답을 하게 된다(2026-09-21 발견)."""
    context_doc_rules = context_doc_rules or []
    rules_block = ""
    if university:
        if context_doc_rules:
            excerpts = "\n\n".join(
                f"[p.{r.get('page_start')}-{r.get('page_end')}] {r['text'][:600]}" for r in context_doc_rules
            )
            rules_block = f"\n\n해당 학교({university}) 서류 규정 원문 발췌:\n{excerpts}"
        else:
            rules_block = f"\n\n해당 학교({university}) 서류 규정 원문 발췌: (찾지 못함 - 빈 목록)"

    messages = [
        {"role": "system", "content": _REVIEW_CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": f"문서 종류: {doc_type}\n\n--- 원본 텍스트 ---\n{text_or_empty(doc_text)}{rules_block}"},
    ]
    messages.extend(history)

    try:
        reply = _call_llm_messages(messages, model_id, temperature=0.3)
    except Exception as e:
        print(f"[chat_about_review] LLM 호출 실패: {e}")
        return {"reply": _LLM_FRIENDLY_ERROR, "model": model_id, "error": True}

    return {"reply": reply, "model": model_id}


def text_or_empty(text: Optional[str]) -> str:
    return (text or "").strip()[:12000]
