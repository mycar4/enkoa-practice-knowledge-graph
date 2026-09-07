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
        candidates = sorted(candidates, key=lambda c: c.get("rerank_score", 0), reverse=True)
    except Exception:
        pass
    return candidates[:top_k]


_QA_SYSTEM_PROMPT = """당신은 "미술 실기 입시 도우미"의 답변 생성기입니다. 반드시 아래 규칙을 지키십시오.

1. 사용자 메시지에 JSON으로 주어지는 "context_tracks"(공식 모집요강 사실),
   "context_estimates"(비공식 추정치), "context_raw_excerpts"(PDF 원문 발췌, 의미기반
   검색 결과) 안에 있는 값만 사용하십시오. 그 안에 없는 학교/학과/숫자/날짜/조건은
   절대 새로 만들어내지 마십시오. 모르면 반드시 "정보 없음"이라고 답하십시오.
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
7. 간결하고 친절한 한국어로, 수험생에게 답하듯 작성하십시오.
"""


def answer_with_llm(context_tracks: List[Dict[str, Any]], context_estimates: List[Dict[str, Any]],
                     query: str, model_id: str = "gpt-4o-mini",
                     context_raw_excerpts: Optional[List[Dict[str, Any]]] = None,
                     context_graph_related: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """조회된 그래프 사실(context_tracks/estimates), PDF 원문 벡터검색 결과
    (context_raw_excerpts), 그리고 개체 동시출현 그래프에서 뽑은 관련 학교 힌트
    (context_graph_related, GraphRAG 연동)를 근거로 LLM이 자연어 답변을 생성한다.
    셋 다 비어 있으면 LLM 호출 없이 바로 '정보 없음'을 반환한다 (환각 방지)."""
    context_raw_excerpts = context_raw_excerpts or []
    context_graph_related = context_graph_related or []
    if not context_tracks and not context_estimates and not context_raw_excerpts:
        return {
            "answer": "적재된 데이터 중에 관련된 학교/학과를 찾지 못했습니다. 학교명을 정확히 포함해서 다시 질문해주세요.",
            "model": model_id,
            "grounded_on": [],
        }

    user_payload = {
        "question": query,
        "context_tracks": context_tracks,
        "context_estimates": context_estimates,
        "context_raw_excerpts": context_raw_excerpts,
        "context_graph_related": context_graph_related,
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

    grounded_on = [f"{t['university']} {t['department']}" for t in context_tracks]
    grounded_on += [f"{e['university']} p.{e.get('page_start')}-{e.get('page_end')}" for e in context_raw_excerpts]
    return {
        "answer": answer,
        "model": model_id,
        "grounded_on": grounded_on,
    }


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
"""


def review_document(text: str, model_id: str = "gpt-4o-mini", doc_type: str = "자기소개서/활동보고서",
                     graph_hint: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """서류/자소서 텍스트를 AI가 글쓰기 관점에서 첨삭한다. 사실 판정이 아니라
    의견이므로 화면에서도 반드시 '공식 평가 아님' 라벨을 별도로 붙여야 한다.
    graph_hint(GraphRAG 연동): 개체 동시출현 그래프에서 이름매칭으로 감지된
    학교/학과와 그 커뮤니티 라벨 - 어떤 계열 글인지 감을 잡는 참고 정보로만 쓴다."""
    text = (text or "").strip()
    if not text:
        return {"feedback": "첨삭할 텍스트가 비어 있습니다.", "model": model_id, "error": True}

    hint_line = ""
    if graph_hint:
        labels = sorted({h["community_label"] for h in graph_hint if h.get("community_label")})
        names = [h["name"] for h in graph_hint]
        hint_line = f"\n\n감지된 계열 정보(참고용, 사실 단정 금지): 언급된 개체 {names} / 계열 {labels}"

    user_prompt = f"문서 종류: {doc_type}\n\n--- 첨삭할 텍스트 ---\n{text[:12000]}{hint_line}"

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
일관되게 답하십시오.
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
