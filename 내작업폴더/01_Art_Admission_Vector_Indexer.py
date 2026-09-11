# -*- coding: utf-8 -*-
"""
🎨 [미술 실기 입시 도우미] PDF 원문 벡터 색인기
================================================================================
- 이미 구조화된 필드(정원/일정/실기종목 등)로 못 잡아내는 세세한 질문
  ("이 학과 지원자격에 대회 수상 우대 있어?" 같은)에 답하기 위해, PDF 원문
  텍스트를 청크 단위로 잘라 OpenAI 임베딩으로 변환하고 Neo4j 벡터 인덱스에 저장한다.
- 여기서 색인하는 파일은 반드시 "실제로 확인된 2027학년도 원문"만 대상으로 한다.
  구(2026학년도 이전) 자료를 섞어 색인하면 벡터검색이 학년도 뒤섞임 사고를
  다시 일으킬 수 있으므로, 파일 목록은 이 세션에서 직접 검증한 것만 하드코딩한다.
- 기본 DRY-RUN(청크 개수/미리보기만 출력), --commit 시에만 실제 임베딩 호출 + 적재.
================================================================================
"""

import os
import sys
import argparse
from pathlib import Path

import pypdf
from neo4j import GraphDatabase, WRITE_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
sys.path.insert(0, str(BASE_DIR))
load_dotenv(REPO_ROOT / ".env")

from services.art_admission_llm import embed_text, EMBEDDING_DIM  # noqa: E402

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

PDF_DIR = REPO_ROOT / "data" / "art_admission_raw" / "prospectus"

# (대학명, 파일명, admission_year) - 이 세션에서 실제로 표지/본문 확인해서
# 2027학년도 원문임을 검증한 파일만 나열한다. 파일명이 "2026학년도"로 되어 있어도
# (예: 한국예술종합학교) 본문 내용이 2027학년도면 그대로 포함한다.
INDEX_TARGETS = [
    ("한국예술종합학교", "한국예술종합학교_2026학년도_예술사모집요강.pdf", 2027),
    ("중앙대학교", "중앙대학교_2027학년도_수시모집요강.pdf", 2027),
    ("가천대학교", "가천대학교_2027학년도_수시모집요강.pdf", 2027),
    ("서경대학교", "서경대학교_2027학년도_수시모집요강.pdf", 2027),
    ("용인대학교", "용인대학교_2027학년도_수시모집요강.pdf", 2027),
    ("계원예술대학교", "계원예술대학교_2027학년도_수시1차모집요강.pdf", 2027),
    ("추계예술대학교", "추계예술대학교_2027학년도_수시모집요강.pdf", 2027),
    ("홍익대학교", "홍익대학교_2027학년도_수시모집요강.pdf", 2027),
    ("경희대학교", "경희대학교_2027학년도_수시모집요강.pdf", 2027),
    ("동국대학교", "동국대학교_2027학년도_수시모집요강.pdf", 2027),
    ("상명대학교", "상명대학교_2027학년도_수시모집요강.pdf", 2027),
    ("서울과학기술대학교", "서울과학기술대학교_2027학년도_수시모집요강.pdf", 2027),
    ("명지대학교", "명지대학교_2027학년도_수시모집요강.pdf", 2027),
    ("삼육대학교", "삼육대학교_2027학년도_수시모집요강.pdf", 2027),
    ("국민대학교", "2027_kookmin_susi.pdf", 2027),
    ("서울대학교", "2027_snu_susi.pdf", 2027),
    ("고려대학교", "2027_korea_susi.pdf", 2027),
    ("한양대학교", "2027_hanyang_seoul_susi.pdf", 2027),
    ("인천대학교", "2027_incheon_susi.pdf", 2027),
    ("국립공주대학교", "2027_kongju_susi.pdf", 2027),
    ("청주대학교", "2027_cheongju_susi.pdf", 2027),
    # 인천가톨릭대학교는 공식 요강이 PDF가 아닌 HWP로만 제공되어(2027_incheon_catholic_susi.hwp)
    # 현재 pypdf 기반 인덱서로는 텍스트 추출이 불가능하다 - HWP 파서(pyhwp 등) 도입 전까지는
    # 구조화 사실(Neo4j Track)만 적재되고 "원문 발췌"/하이브리드 검색 대상에서는 빠진다.
    ("숙명여자대학교", "숙명여자대학교_2027학년도_수시모집요강.pdf", 2027),
    ("성신여자대학교", "성신여자대학교_2027학년도_수시모집요강.pdf", 2027),
    ("이화여자대학교", "이화여자대학교_2027학년도_수시모집요강.pdf", 2027),
    ("동덕여자대학교", "동덕여자대학교_2027학년도_수시모집요강.pdf", 2027),
    ("덕성여자대학교", "덕성여자대학교_2027학년도_수시모집요강.pdf", 2027),
    ("단국대학교", "단국대학교_2027학년도_수시모집요강.pdf", 2027),
    # 경기대학교 PDF는 96쪽 전체가 스캔 이미지(용인대와 동일 유형)라 pypdf로 텍스트
    # 추출 시 0글자가 나온다 - OCR 파이프라인 도입 전까지는 구조화 사실(Neo4j Track)만
    # 적재되고 "원문 발췌"/하이브리드 검색 대상에서는 빠진다. 목록엔 남겨둔다(파일 없음
    # 경고와 구분하기 위해 - 실행 로그에서 0개 청크로 표시됨).
    ("경기대학교", "경기대학교_2027학년도_수시모집요강.pdf", 2027),
    ("한성대학교", "한성대학교_2027학년도_수시모집요강.pdf", 2027),
    # 한양대학교는 서울캠퍼스(2027_hanyang_seoul_susi.pdf)와 ERICA캠퍼스가 raw JSON에서
    # 같은 "한양대학교" university 이름을 쓴다 - DETACH DELETE가 source_file도 매칭하도록
    # 고쳐뒀으니 두 캠퍼스를 각각 등록해도 서로 지우지 않는다.
    ("한양대학교", "한양대학교_ERICA_2027학년도_수시모집요강.pdf", 2027),
]

CHUNK_CHAR_SIZE = 1500  # 대략 400~500 토큰 - 임베딩 품질/개수 균형


def extract_chunks(pdf_path: Path):
    """페이지 텍스트를 이어붙이다가 CHUNK_CHAR_SIZE를 넘으면 끊는다. 청크마다
    실제로 포함된 페이지 범위를 기록해서, 나중에 '몇 페이지 근거'인지 보여줄 수 있게 한다."""
    reader = pypdf.PdfReader(str(pdf_path))
    chunks = []
    buf = ""
    start_page = 1
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        if buf and len(buf) + len(text) > CHUNK_CHAR_SIZE:
            chunks.append({"text": buf, "page_start": start_page, "page_end": i - 1})
            buf = text
            start_page = i
        else:
            buf = f"{buf}\n{text}" if buf else text
    if buf:
        chunks.append({"text": buf, "page_start": start_page, "page_end": len(reader.pages)})
    return chunks


def ensure_vector_index(driver):
    with driver.session(default_access_mode=WRITE_ACCESS) as s:
        s.run(f"""
            CREATE VECTOR INDEX admission_chunk_embedding IF NOT EXISTS
            FOR (c:Admission_TextChunk) ON (c.embedding)
            OPTIONS {{indexConfig: {{
                `vector.dimensions`: {EMBEDDING_DIM},
                `vector.similarity_function`: 'cosine'
            }}}}
        """)
        # 하이브리드 검색용 풀텍스트(키워드) 인덱스 - 벡터가 놓치기 쉬운 고유명사/숫자/
        # 정확한 용어 매칭을 키워드 쪽이 보완한다.
        s.run("""
            CREATE FULLTEXT INDEX admission_chunk_fulltext IF NOT EXISTS
            FOR (c:Admission_TextChunk) ON EACH [c.text]
        """)


def main():
    parser = argparse.ArgumentParser(description="미술 실기 입시 PDF 원문 벡터 색인기")
    parser.add_argument("--commit", action="store_true", help="실제 임베딩 호출 + Neo4j 적재 (미지정 시 DRY-RUN)")
    parser.add_argument("--university", default=None, help="특정 대학만 재색인 (기본: 전체)")
    args = parser.parse_args()

    total_chunks = 0
    plan = []
    for univ, filename, admission_year in INDEX_TARGETS:
        if args.university and univ != args.university:
            continue
        path = PDF_DIR / filename
        if not path.exists():
            print(f"⚠️ 파일 없음, 건너뜀: {path}")
            continue
        chunks = extract_chunks(path)
        total_chunks += len(chunks)
        plan.append((univ, admission_year, path, chunks))
        print(f"{univ}: {len(chunks)}개 청크 (파일: {filename})")

    print(f"\n총 색인 대상: {len(plan)}개 대학, {total_chunks}개 청크")

    if not args.commit:
        print("\nDRY-RUN 완료 (임베딩 호출/DB 쓰기 0건). --commit 플래그로 재실행 시 실제 색인됩니다.")
        if plan:
            sample = plan[0][3][0]["text"][:200]
            print(f"\n[미리보기: {plan[0][0]} 1번째 청크]\n{sample}...")
        return

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        ensure_vector_index(driver)
        for univ, admission_year, path, chunks in plan:
            with driver.session(default_access_mode=WRITE_ACCESS) as s:
                # source_file도 매칭 조건에 넣는다 - 한양대(서울)/한양대(ERICA)처럼 같은
                # university 이름을 캠퍼스별로 다른 PDF에서 공유하는 경우, university만
                # 매칭해서 삭제하면 나중에 색인한 캠퍼스가 먼저 색인한 캠퍼스의 청크를
                # 지워버리는 사고가 난다.
                s.run(
                    "MATCH (c:Admission_TextChunk {university: $univ, source_file: $source_file}) DETACH DELETE c",
                    univ=univ, source_file=path.name,
                )
            for idx, ch in enumerate(chunks):
                vec = embed_text(ch["text"])
                with driver.session(default_access_mode=WRITE_ACCESS) as s:
                    s.run("""
                        CREATE (c:Admission_TextChunk {
                            university: $univ, admission_year: $year, chunk_index: $idx,
                            page_start: $ps, page_end: $pe, text: $text,
                            source_file: $source_file, embedding: $embedding
                        })
                    """, univ=univ, year=admission_year, idx=idx,
                         ps=ch["page_start"], pe=ch["page_end"], text=ch["text"],
                         source_file=path.name, embedding=vec)
            print(f"[커밋 완료] {univ}: {len(chunks)}개 청크 색인")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
