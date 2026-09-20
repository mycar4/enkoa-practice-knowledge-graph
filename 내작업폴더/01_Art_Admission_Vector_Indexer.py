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

# 2026-09-13: art-admission 전용 Neo4j 인스턴스 - DART-Trace가 쓰는 AURA_*와 분리됨
uri = os.getenv("ART_ADMISSION_NEO4J_URI") or os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("ART_ADMISSION_NEO4J_USER") or os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("ART_ADMISSION_NEO4J_PASSWORD") or os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

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
    # 2026-09-20: 서류첨삭(review.html)이 "미술활동보고서" 규정을 찾을 때 이 학교
    # 원문에는 활동유형 분류(드로잉/조형/매체활용/감상/진로 등)·글자수 제한·인적사항
    # 노출 금지 같은 핵심 작성 규칙이 아예 없다는 걸 확인 - 별도 공식 안내 PDF를
    # 같은 university로 추가 색인해서 get_document_rule_excerpts()가 찾을 수 있게 한다.
    ("홍익대학교", "홍익대학교_2027학년도_미술활동보고서_작성안내.pdf", 2027),
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
    # 2026-09-17: 인천가톨릭대학교 공식 요강은 PDF가 아닌 HWP로만 제공된다
    # (2027_incheon_catholic_susi.hwp) - hwp5txt(pyhwp) CLI 우회 추출로 지원 추가.
    ("인천가톨릭대학교", "2027_incheon_catholic_susi.hwp", 2027),
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

    # 2026-09-13: 국립대 전국 확장 배치(60개교 마스터 리스트 완료)로 새로 추가된
    # 27개교 - 각 학교 raw JSON의 data_sources.local_file을 그대로 가져와 등록.
    ("건국대학교", "건국대학교_GLOCAL_2027학년도_수시모집요강.pdf", 2027),
    ("경북대학교", "경북대학교_2027학년도_수시모집요강.pdf", 2027),
    ("계명대학교", "계명대학교_2027학년도_수시모집요강.pdf", 2027),
    ("국립한밭대학교", "국립한밭대학교_2027학년도_수시모집요강.pdf", 2027),
    ("남서울대학교", "남서울대학교_2027학년도_수시모집요강.pdf", 2027),
    ("대진대학교", "대진대학교_2027학년도_수시모집요강.pdf", 2027),
    ("목원대학교", "2027_mokwon_susi.pdf", 2027),
    ("부산대학교", "2027_pusan_susi.pdf", 2027),
    ("서울여자대학교", "서울여자대학교_2027학년도_수시모집요강.pdf", 2027),
    ("서울예술대학교", "서울예술대학교_2027학년도_수시모집요강.pdf", 2027),
    ("세종대학교", "세종대학교_2027학년도_수시모집요강.pdf", 2027),
    ("수원대학교", "수원대학교_2027학년도_수시모집요강.pdf", 2027),
    ("신한대학교", "신한대학교_2027학년도_수시모집요강.pdf", 2027),
    # 영남대학교 PDF는 텍스트 레이어가 없는 이미지 PDF라(경기대/용인대와 동일 유형)
    # pypdf 추출 시 0글자가 나온다 - OCR 도입 전까지는 구조화 사실만 적재되고
    # 하이브리드 검색 대상에서는 빠진다. 목록엔 남겨둔다.
    ("영남대학교", "영남대학교_2027학년도_수시모집요강.pdf", 2027),
    ("원광대학교", "원광대학교_2027학년도_수시모집요강.pdf", 2027),
    ("인하대학교", "인하대학교_2027학년도_수시모집요강.pdf", 2027),
    ("전남대학교", "2027_jnu_susi.pdf", 2027),
    ("조선대학교", "조선대학교_2027학년도_수시모집요강.pdf", 2027),
    ("충남대학교", "충남대학교_2027학년도_수시모집요강.pdf", 2027),
    ("충북대학교", "충북대학교_2027학년도_수시모집요강.pdf", 2027),
    ("평택대학교", "평택대학교_2027학년도_수시모집요강.pdf", 2027),
    ("한경국립대학교", "한경국립대학교_2027학년도_수시모집요강.pdf", 2027),
    ("한남대학교", "한남대학교_2027학년도_수시모집요강.pdf", 2027),
    ("협성대학교", "협성대학교_2027학년도_수시모집요강.pdf", 2027),
    ("호서대학교", "호서대학교_2027학년도_수시모집요강.pdf", 2027),
]

CHUNK_CHAR_SIZE = 1500  # 대략 400~500 토큰 - 임베딩 품질/개수 균형


def extract_chunks(pdf_path: Path):
    """페이지 텍스트를 이어붙이다가 CHUNK_CHAR_SIZE를 넘으면 끊는다. 청크마다
    실제로 포함된 페이지 범위를 기록해서, 나중에 '몇 페이지 근거'인지 보여줄 수 있게 한다.
    2026-09-17: .hwp 확장자는 pypdf로 못 읽으므로 hwp5txt CLI(pyhwp 패키지)로 우회
    추출한다 - HWP는 페이지 경계 정보가 없어 page_start/page_end를 0으로 둔다.

    2026-09-17: 경기대/영남대처럼 전체가 스캔 이미지인 PDF는 pypdf가 0글자를 반환한다.
    Tesseract OCR을 실측해봤는데 한글 음절 사이에 공백이 끼는 등 품질이 원문 검증
    (anti-hallucination) 게이트를 통과 못할 수준이라 폐기했고, 대신 gpt-5.6-luna 비전
    호출로 페이지별 사전 OCR한 결과를 `prospectus/ocr_cache/<파일명>.json`에 캐싱해두고
    (`scratchpad/ocr_scanned_pdfs.py`), 여기서는 그 캐시가 있으면 pypdf 대신 사용한다."""
    ocr_cache_path = pdf_path.parent / "ocr_cache" / f"{pdf_path.name}.json"
    if ocr_cache_path.exists():
        import json
        with open(ocr_cache_path, encoding="utf-8") as f:
            cached = json.load(f)
        chunks = []
        buf = ""
        start_page = 1
        pages = cached["pages"]
        for i, text in enumerate(pages, start=1):
            text = (text or "").strip()
            if not text:
                continue
            if buf and len(buf) + len(text) > CHUNK_CHAR_SIZE:
                chunks.append({"text": buf, "page_start": start_page, "page_end": i - 1})
                buf = text
                start_page = i
            else:
                buf = f"{buf}\n{text}" if buf else text
        if buf:
            chunks.append({"text": buf, "page_start": start_page, "page_end": len(pages)})
        return chunks

    if pdf_path.suffix.lower() == ".hwp":
        # 2026-09-19: hwp5txt는 표(<표>) 내용을 통째로 못 읽고 자리표시자만 남긴다 -
        # 실측으로 확인(인천가톨릭대 전형일정/모집인원표가 전부 유실됨). 같은 pyhwp
        # 패키지의 hwp5html은 표를 실제 <table>로 렌더링하므로, 이를 파싱해서 표 행도
        # 텍스트로 살린다(hwp5txt 대비 글자수 약 8.5배 증가, 날짜/정원 실측 확인됨).
        import subprocess
        import tempfile
        from bs4 import BeautifulSoup

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["hwp5html", "--output", tmpdir, str(pdf_path)],
                capture_output=True, text=True, encoding="utf-8",
            )
            if result.returncode != 0:
                raise RuntimeError(f"hwp5html 추출 실패: {result.stderr}")
            html_path = Path(tmpdir) / "index.xhtml"
            with open(html_path, encoding="utf-8") as f:
                soup = BeautifulSoup(f.read(), "html.parser")

        def table_to_lines(table):
            lines = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
                cells = [c for c in cells if c]
                if cells:
                    lines.append(" | ".join(cells))
            return lines

        out_lines = []
        body = soup.find("body")
        for el in body.find_all(["p", "table"]):
            if el.name == "p":
                if el.find_parent("table") is not None:
                    continue  # 표 안 문단은 표 처리에서 이미 다룸
                text = el.get_text(" ", strip=True)
                if text:
                    out_lines.append(text)
            elif el.name == "table":
                if el.find_parent("table") is not None:
                    continue  # 중첩 표는 바깥 표에서 이미 포함됨
                out_lines.extend(table_to_lines(el))

        chunks = []
        buf = ""
        for line in out_lines:
            line = line.strip()
            if not line:
                continue
            if buf and len(buf) + len(line) > CHUNK_CHAR_SIZE:
                chunks.append({"text": buf, "page_start": 0, "page_end": 0})
                buf = line
            else:
                buf = f"{buf}\n{line}" if buf else line
        if buf:
            chunks.append({"text": buf, "page_start": 0, "page_end": 0})
        return chunks

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
