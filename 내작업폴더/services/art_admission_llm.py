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
    {"id": "claude-3-5-sonnet-latest", "label": "Claude 3.5 Sonnet (Anthropic, 최신·고급)", "provider": "anthropic", "available": bool(_ANTHROPIC_KEY), "gated": True},
    {"id": "gemini-1.5-pro", "label": "Gemini 1.5 Pro (Google, 최신·고급)", "provider": "gemini", "available": bool(_GEMINI_KEY), "gated": True},
]


def get_available_models() -> List[Dict[str, Any]]:
    return MODEL_REGISTRY


def _model_info(model_id: str) -> Dict[str, Any]:
    for m in MODEL_REGISTRY:
        if m["id"] == model_id:
            return m
    return MODEL_REGISTRY[0]


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
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


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
    payload = {"model": model, "system": system_prompt, "messages": conv, "max_tokens": 1024, "temperature": temperature}
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
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
    with urllib.request.urlopen(req, timeout=30) as resp:
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
1-1. 사용자가 특정 실기유형 키워드(예: "소묘", "기초디자인")를 언급하며 "그 실기로
   볼 수 있는 학교"를 물으면, context_tracks의 각 항목에 있는 exam_type_keyword_match
   값을 반드시 그대로 따르십시오. exam_type_keyword_match가 true인 트랙만 그 실기
   유형에 대한 직접적인 답으로 제시하십시오. exam_type_keyword_match가 false인
   트랙은 exam_type_name이나 allowed_materials가 비슷해 보이더라도 "실기유형은
   다름"이라고 반드시 밝히고, 별도 절("참고: 실기유형은 다르지만 재료가 비슷한
   전형") 아래에서만 언급하십시오. exam_type_keyword_match를 무시하고 재료(연필 등)
   유사성만으로 두 실기유형을 같은 것처럼 답하지 마십시오.
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
   가장 중요: context_compatible_tracks에 들어있는 항목은 반드시 전부(빠짐없이)
   나열하십시오. "이 외에도 여러 학교가 있다" 같은 말로 일부만 보여주고 요약해서
   끝내지 마십시오 - 목록 개수가 몇 건이든 전부 답변에 포함하는 것이 이 질문
   유형에서는 요약보다 훨씬 중요합니다.
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


def _self_check_compat_claim(answer: str, context_compatible_tracks: List[Dict[str, Any]]) -> List[str]:
    """재료만 겹치는 걸 '같은 실기'/'호환'이라고 부르면 안 된다는 규칙(§4)을 코드로 재검증.
    답변에 '호환'/'같은 실기' 표현이 있는데 shared_keywords(실기유형 자체 일치)가 있는
    후보가 하나도 없으면, 근거 없이 그 표현을 썼다는 뜻이다."""
    if "호환" not in answer and "같은 실기" not in answer:
        return []
    has_exact_match = any((c.get("shared_keywords") or []) for c in context_compatible_tracks)
    if not has_exact_match:
        return ["'호환'/'같은 실기' 표현이 쓰였지만 실기유형 자체가 일치하는(shared_keywords) 근거가 없습니다"]
    return []


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
        return {
            "answer": f"⚠️ AI 답변 생성 실패: {e}\n\n(위쪽 규칙기반 조회 결과를 참고해주세요.)",
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
        return {"feedback": f"⚠️ AI 첨삭 실패: {e}", "model": model_id, "error": True}

    return {"feedback": feedback, "model": model_id}


_REVIEW_CHAT_SYSTEM_PROMPT = _REVIEW_SYSTEM_PROMPT + """

지금은 방금 드린 첨삭 의견에 대해 사용자와 이어서 대화하며 보완하는 중입니다.
사용자가 질문을 하거나, 수정한 문장/문단을 다시 보여주면 같은 원칙
(합격 가능성 단정 금지, 사실관계 검증 불가 명시, 글쓰기 관점 피드백만 제공)을
유지하면서 대화를 이어가십시오. 앞서 나온 원본 문서와 첫 첨삭 내용을 계속 기억하고
일관되게 답하십시오. 단, 위의 "5개 섹션(### 강점 ~ ### 적용한 학교별 규정 근거)"
형식은 최초 첨삭 1회에만 적용됩니다 - 이 대화 턴에서는 그 형식을 강제로 반복하지
말고, 사용자의 질문에 자연스러운 대화체로 답하십시오.
"""


def chat_about_review(doc_text: str, doc_type: str, history: List[Dict[str, str]],
                       model_id: str = "gpt-4o-mini") -> Dict[str, Any]:
    """서류 첨삭 후 이어지는 대화. history는 [{'role': 'assistant'|'user', 'content': ...}, ...]
    형태로, 최초 첨삭(assistant) 이후 사용자와 주고받은 턴을 그대로 담아 전달한다."""
    messages = [
        {"role": "system", "content": _REVIEW_CHAT_SYSTEM_PROMPT},
        {"role": "user", "content": f"문서 종류: {doc_type}\n\n--- 원본 텍스트 ---\n{text_or_empty(doc_text)}"},
    ]
    messages.extend(history)

    try:
        reply = _call_llm_messages(messages, model_id, temperature=0.3)
    except Exception as e:
        return {"reply": f"⚠️ AI 응답 실패: {e}", "model": model_id, "error": True}

    return {"reply": reply, "model": model_id}


def text_or_empty(text: Optional[str]) -> str:
    return (text or "").strip()[:12000]
