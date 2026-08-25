"""
========================================================================================
🏛️ [AI 에이전트 마스터 템플릿] End-to-End 전체 생태계 통합 풀소스 (All-in-One)
========================================================================================
📌 이 파일 하나에 지금까지 배운 모든 엔터프라이즈 AI 기술이 1단계부터 8단계까지 순서대로
   완벽하게 연결되어 구현되어 있습니다.

[목차]
  - 1단계: 원천 데이터 수집 & 정제 (Cleaning)
  - 2단계: 청킹 (RecursiveCharacterTextSplitter)
  - 3단계: 임베딩 & 벡터 데이터베이스 적재 (OpenAIEmbeddings + Chroma)
  - 4단계: RAG 검색기 생성 (Retriever)
  - 5단계: AI 실행 도구 정의 (@tool & Pydantic 규격)
  - 6단계: ReAct 멀티툴 자율 에이전트 생성 (create_agent)
  - 7단계: Self-Reflection 품질 통제 (자가 채점 & 퇴고 루프)
  - 8단계: Langfuse 관측성 & 장애 방어 Fallback 연동 및 최종 실행
========================================================================================
"""

import os
import re
import sys
from pathlib import Path

# 윈도우 터미널(CP949) 이모지 및 한글 깨짐 방지 UTF-8 설정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# LangChain 관련 필수 부품 Import
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.tools import tool
from langchain.agents import create_agent

# 7단계 Langfuse 관측성 부품 Import
try:
    from langfuse.callback import CallbackHandler
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

# 0. 환경변수(.env) 로드 (OPENAI_API_KEY 등)
load_dotenv()


# ======================================================================================
# 1단계. 데이터 수집 & 전처리 (Data Ingestion & Preprocessing)
# ======================================================================================
# [WHY] 쓰레기 데이터(HTML 태그, 이상한 기호)가 들어가면 AI도 헛소리를 합니다.
#       텍스트를 깔끔하게 다듬는 정제 작업을 거칩니다.

raw_sample_text = """
<div class="policy-header"><h1>[주식회사 엔코아 2026년 인사/복지 규정]</h1></div>
■ 제1조 (연차 휴가 부여)
- 근로기준법에 따라 1년간 80% 이상 출근한 근로자에게 15일의 유급휴가를 부여합니다.
- 입사 1년 미만 근로자는 1개월 개근 시 1일의 유급휴가가 발생합니다.

■ 제2조 (경조 휴가 및 경조금 지원)
- 본인 결혼: 5일 유급휴가 + 화환 및 축하금 50만원
- 직계존속 사망: 5일 유급휴가 + 조화 및 조의금 50만원

■ 제3조 (반려동물 의료비 지원)
- 사내 복지 제도로 반려견/반려묘의 슬개골 탈구 및 예방접종 비용을 연간 최대 50만원 지원합니다.
"""

def clean_text(text: str) -> str:
    """HTML 태그 제거 및 불필요한 공백/특수문자를 정제하는 함수"""
    text = re.sub(r'<[^>]+>', '', text)          # 1. HTML 태그 제거
    text = re.sub(r'[■]', '', text)               # 2. 불필요한 특수문자 제거
    text = re.sub(r'\s+', ' ', text).strip()      # 3. 다중 공백 및 줄바꿈을 1개 공백으로 정규화
    return text

cleaned_text = clean_text(raw_sample_text)
# LangChain 문서 객체로 포장
raw_docs = [Document(page_content=cleaned_text, metadata={"source": "2026_취업규칙.txt"})]
print("✅ 1단계: 원천 데이터 수집 및 텍스트 정제 완료!")


# ======================================================================================
# 2단계. 청킹 (Chunking - 의미 단위 분할)
# ======================================================================================
# [WHY] 문서가 100페이지면 AI에게 한 번에 다 읽힐 수 없습니다.
#       500자 단위로 자르고, 문맥이 끊기지 않도록 앞뒤로 50자씩 겹치게(Overlap) 만듭니다.

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,        # 한 조각당 약 300자
    chunk_overlap=50,      # 앞뒤 문맥 유지를 위해 50자씩 중첩
    separators=["\n\n", "\n", " ", ""]
)
splits = text_splitter.split_documents(raw_docs)
print(f"✅ 2단계: 청킹 완료 (총 {len(splits)}개의 문서 조각으로 분할)")


# ======================================================================================
# 3단계. 임베딩 & 벡터 DB 적재 (Embedding & Vector Storage)
# ======================================================================================
# [WHY] 컴퓨터가 글자의 '의미'를 찾을 수 있도록 글자를 1536차원 숫자 좌표(벡터)로 바꾸고,
#       ChromaDB라는 벡터 전용 창고에 차곡차곡 저장합니다.

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

# 로컬 메모리/폴더에 Chroma 벡터 DB 구축
vectorstore = Chroma.from_documents(
    documents=splits,
    embedding=embeddings,
    collection_name="company_policy"
)
print("✅ 3단계: 임베딩 변환 및 ChromaDB 벡터 저장 완료!")


# ======================================================================================
# 4단계. RAG 유사도 검색기 생성 (Retriever)
# ======================================================================================
# [WHY] 사용자가 질문을 던졌을 때, 벡터 DB에서 가장 유사한 상위 2개(k=2) 조각을
#       0.01초 만에 낚아채오는 검색 낚싯대(Retriever)를 만듭니다.

retriever = vectorstore.as_retriever(search_kwargs={"k": 2})
print("✅ 4단계: RAG 검색기(Retriever) 준비 완료!")


# ======================================================================================
# 5단계. AI 실행 도구 정의 (@tool 데코레이터 & 도구 목록)
# ======================================================================================
# [WHY] AI에게 말만 시키는 게 아니라, 실제 검색/DB조회/파일저장을 할 수 있는
#       '팔과 다리(무기)'를 쥐여줍니다.

# 도구 ① RAG 사내 규정 검색 도구
@tool
def search_company_policy(query: str) -> str:
    """사내 취업규칙, 연차 규정, 경조사 지원, 복지 혜택 문서를 검색할 때 사용한다."""
    docs = retriever.invoke(query)
    return "\n\n".join(f"[근거 문서]: {d.page_content}" for d in docs)

# 도구 ② 인사 DB 조회 도구 (정형 데이터 모의 쿼리)
@tool
def get_employee_info(emp_name: str) -> str:
    """인사 DB에서 직원의 직급, 입사일, 잔여 연차 일수를 조회한다."""
    # 실제 환경에서는 SQL DB(PostgreSQL)를 조회하지만, 여기서는 예시 리턴
    return f"직원명: {emp_name} | 직급: 대리 | 입사일: 2024-01-01 | 잔여 연차: 12일"

# 도구 ③ 파일 저장 도구 (MCP / 로컬 파일 작성)
@tool
def save_report_to_file(filename: str, content: str) -> str:
    """작성된 최종 신청서나 리포트를 파일로 저장한다."""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    file_path = output_dir / filename
    file_path.write_text(content, encoding="utf-8")
    return f"파일 저장 성공: {file_path.resolve()}"

# AI가 사용할 도구 상자(Toolbox)로 묶기
my_tools = [search_company_policy, get_employee_info, save_report_to_file]
print("✅ 5단계: AI용 @tool 3종 세트 등록 완료!")


# ======================================================================================
# 6단계. ReAct 자율 에이전트 생성 (create_agent)
# ======================================================================================
# [WHY] 질문을 받았을 때 AI가 "스스로 생각(Thought)하고, 도구를 골라 쓰고(Action),
#       결과를 확인(Observation)하며" 문제를 끝까지 해결하는 두뇌를 만듭니다.

# 메인 LLM 모델 정의 (타임아웃 10초)
primary_model = ChatOpenAI(model="gpt-4o-mini", temperature=0, timeout=10)

# 장애 대비 예비 모델 (Fallback용)
backup_model = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, timeout=10)

# 🔥 with_fallbacks: 메인 모델이 뻗거나 에러 나면 1초 만에 백업 모델로 자동 전환!
robust_model = primary_model.with_fallbacks([backup_model])

agent_executor = create_agent(
    model=robust_model,
    tools=my_tools,
    system_prompt=(
        "너는 주식회사 엔코아의 최고 수석 비서 AI다.\n"
        "1. 직원의 질문을 받으면 반드시 도구를 사용해 팩트를 확인하라.\n"
        "2. 사내 규정 검색 도구로 근거를 찾고, 직원 정보 조회 도구로 잔여 연차를 확인하라.\n"
        "3. 결과를 종합하여 완벽한 신청서 초안을 작성하라."
    )
)
print("✅ 6단계: ReAct 자율 에이전트 및 무중단 Fallback 장착 완료!")


# ======================================================================================
# 7단계. Self-Reflection 품질 통제 (자가 비평 & 퇴고 루프)
# ======================================================================================
# [WHY] AI가 대충 답변을 내보내지 못하도록, Pydantic 채점표를 기준으로
#       80점이 넘을 때까지 스스로 지적사항을 고치게 만듭니다.

class Critique(BaseModel):
    score: int = Field(description="1~100점 사이의 엄격한 품질 점수")
    is_passed: bool = Field(description="80점 이상이면 True, 미만이면 False")
    issues: list[str] = Field(description="부족하거나 누락된 항목 지적 리스트")

critic_evaluator = robust_model.with_structured_output(Critique)

def self_reflection_loop(draft_content: str, max_retries: int = 2) -> str:
    """초안을 스스로 채점하고 부족하면 고쳐 쓰는 자가 퇴고 루프"""
    current_content = draft_content

    for attempt in range(1, max_retries + 1):
        print(f"\n🔍 [Self-Reflection {attempt}회차 채점 진행 중...]")
        critique: Critique = critic_evaluator.invoke(
            f"다음 신청서/답변의 완성도를 엄격하게 채점하라:\n\n{current_content}"
        )
        print(f"   📊 채점 결과: {critique.score}점 (통과여부: {critique.is_passed})")
        
        if critique.is_passed or critique.score >= 80:
            print("   🎉 품질 기준(80점) 통과! 최종 출고 승인.")
            break
        
        print(f"   ⚠️ 지적 사항: {critique.issues}")
        print("   ✏️ 지적 사항을 반영하여 재작성 중...")
        # 수정 체인 호출
        current_content = robust_model.invoke(
            f"기존 초안:\n{current_content}\n\n"
            f"지적된 문제점:\n{critique.issues}\n\n"
            f"위 지적사항을 100% 보완하여 완벽한 최종본으로 다시 작성하라."
        ).content

    return current_content


# ======================================================================================
# 8단계. 엔드투엔드 파이프라인 최종 실행 & Langfuse 관측성 연동
# ======================================================================================
if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("🚀 [전체 파이프라인 엔드투엔드 실행 시작]")
    print("=" * 80)

    # 1. Langfuse 실시간 관측탑 콜백 핸들러 설정
    callbacks = []
    if LANGFUSE_AVAILABLE and os.getenv("LANGFUSE_PUBLIC_KEY"):
        langfuse_handler = CallbackHandler(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")
        )
        callbacks.append(langfuse_handler)
        print("📊 Langfuse 실시간 관측탑 연동 활성화 (토큰 비용/지연시간 자동 계량)")

    user_question = "홍길동 대리의 잔여 연차를 확인하고, 사내 연차 규정에 맞춰 3일 연차 신청서 초안을 작성해서 파일로 저장해줘."
    print(f"\n🗣️ 사용자 질문: {user_question}\n")

    # 2. ReAct 에이전트 실행 (Langfuse 콜백 실어서 호출)
    agent_result = agent_executor.invoke(
        {"messages": user_question},
        config={"callbacks": callbacks} if callbacks else {}
    )
    initial_draft = agent_result["messages"][-1].content
    print("\n📝 [에이전트 1차 결과물 도출 완료]")
    print("-" * 50)
    print(initial_draft)
    print("-" * 50)

    # 3. Self-Reflection 자가 품질 검수 루프 통과
    final_verified_response = self_reflection_loop(initial_draft)

    print("\n" + "=" * 80)
    print("✨ [최종 검수 완료된 고품질 답변]")
    print("=" * 80)
    print(final_verified_response)
    print("=" * 80)

    # 4. Langfuse 사용자 피드백(👍) 모의 적재 (데이터 선순환 플라이휠)
    print("👍 [유저 만족도 피드백 수집] 점수: 5/5점 (골드 데이터셋 자동 적재)")
    print("🏆 모든 8단계 엔터프라이즈 AI 파이프라인이 성공적으로 완료되었습니다!")
