#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏛️ [DART-Trace v1.0] 자본이벤트 512차원 임베딩 및 인덱스 적재 파이프라인
================================================================================
1. 313개 자본이벤트 원본 JSON(CB, BW, 유상증자, 합병, 주식취득)에서 자연어 purpose_text 및 scale_amount 추출
2. OpenAI text-embedding-3-small (512차원) 배치 임베딩 생성
3. Cloud Neo4j Aura :DART_CapitalEvent 노드에 embedding_512, purpose_text, scale_amount 적재
4. Vector Index (HNSW 코사인 512차원) 및 Fulltext Index 생성
================================================================================
"""

import os
import sys
import json
import glob
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from neo4j import GraphDatabase
from openai import OpenAI

# Windows stdout UTF-8 보장
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
ENV_PATH = PROJECT_ROOT / ".env"
if not ENV_PATH.exists():
    ENV_PATH = PROJECT_ROOT.parent / ".env"
load_dotenv(ENV_PATH, override=True)

AURA_URI = os.getenv("AURA_URI")
AURA_USER = os.getenv("AURA_USER")
AURA_PASSWORD = os.getenv("AURA_PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not AURA_URI or not OPENAI_API_KEY:
    raise ValueError("AURA_URI 및 OPENAI_API_KEY가 .env에 설정되어 있어야 합니다.")


def parse_korean_amount(val: Any) -> int:
    """쉼표, 하이픈 등이 포함된 금액 문자열을 정수(원)로 변환"""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().replace(",", "")
    if not s or s == "-" or not re.search(r"\d", s):
        return 0
    try:
        return int(float(s))
    except Exception:
        return 0


def extract_event_fields(data: Dict[str, Any], event_id: str) -> Dict[str, Any]:
    """JSON 원본에서 표준 purpose_text 및 scale_amount 추출"""
    corp_name = data.get("corp_name") or ""
    corp_code = data.get("corp_code") or ""
    rcept_no = data.get("rcept_no") or ""
    bddd = data.get("bddd") or ""

    # 타입 추론
    if "CB_ISSUE" in event_id:
        etype = "CB_ISSUE"
        etype_kr = "전환사채(CB) 발행"
    elif "BW_ISSUE" in event_id:
        etype = "BW_ISSUE"
        etype_kr = "신주인수권부사채(BW) 발행"
    elif "PAID" in event_id:
        etype = "PAID"
        etype_kr = "유상증자"
    elif "MERGER" in event_id:
        etype = "MERGER"
        etype_kr = "회사합병"
    elif "STOCK_ACQUISITION" in event_id:
        etype = "STOCK_ACQUISITION"
        etype_kr = "타법인 주식 및 출자증권 취득"
    else:
        etype = "UNKNOWN"
        etype_kr = "주요 자본변동 이벤트"

    scale_amount = 0
    purpose_segments = []

    if etype in ("CB_ISSUE", "BW_ISSUE"):
        bd_fta = parse_korean_amount(data.get("bd_fta"))
        scale_amount = bd_fta
        bd_knd = data.get("bd_knd", "사채")
        fclt = parse_korean_amount(data.get("fdpp_fclt"))
        op = parse_korean_amount(data.get("fdpp_op"))
        dtrp = parse_korean_amount(data.get("fdpp_dtrp"))
        ocsa = parse_korean_amount(data.get("fdpp_ocsa"))
        etc = parse_korean_amount(data.get("fdpp_etc"))

        fund_desc = []
        if fclt > 0:
            fund_desc.append(f"시설자금 {fclt:,}원")
        if op > 0:
            fund_desc.append(f"운영자금 {op:,}원")
        if dtrp > 0:
            fund_desc.append(f"채무상환자금 {dtrp:,}원")
        if ocsa > 0:
            fund_desc.append(f"타법인 증권 취득자금 {ocsa:,}원")
        if etc > 0:
            fund_desc.append(f"기타자금 {etc:,}원")

        fund_summary = ", ".join(fund_desc) if fund_desc else "운영 및 일반 사업자금 조달"
        purpose_text = (
            f"{corp_name}의 {etype_kr}({bd_knd}) 공시입니다. "
            f"총 조달규모는 {bd_fta:,}원이며, 조달자금의 세부 목적은 {fund_summary}입니다. "
            f"이사회결의일은 {bddd}입니다."
        )

    elif etype == "PAID":
        fclt = parse_korean_amount(data.get("fdpp_fclt"))
        op = parse_korean_amount(data.get("fdpp_op"))
        dtrp = parse_korean_amount(data.get("fdpp_dtrp"))
        ocsa = parse_korean_amount(data.get("fdpp_ocsa"))
        etc = parse_korean_amount(data.get("fdpp_etc"))
        scale_amount = fclt + op + dtrp + ocsa + etc

        fund_desc = []
        if fclt > 0:
            fund_desc.append(f"시설자금 {fclt:,}원")
        if op > 0:
            fund_desc.append(f"운영자금 {op:,}원")
        if dtrp > 0:
            fund_desc.append(f"채무상환자금 {dtrp:,}원")
        if ocsa > 0:
            fund_desc.append(f"타법인 증권 취득자금 {ocsa:,}원")
        if etc > 0:
            fund_desc.append(f"기타자금 {etc:,}원")

        fund_summary = ", ".join(fund_desc) if fund_desc else "경영 및 시설 확충을 위한 유상증자 자금 조달"
        ic_mthn = data.get("ic_mthn") or "주주배정/제3자배정"
        purpose_text = (
            f"{corp_name}의 {etype_kr}(방식: {ic_mthn}) 공시입니다. "
            f"총 조달목적 규모는 {scale_amount:,}원이며, 세부 자금 용도는 {fund_summary}입니다."
        )

    elif etype == "MERGER":
        mg_pp = (data.get("mg_pp") or "").strip()
        mg_mth = (data.get("mg_mth") or "").strip()
        partner = (data.get("mgptncmp_cmpnm") or "합병상대기업").strip()
        scale_amount = parse_korean_amount(data.get("rbsnfdtl_tast")) or parse_korean_amount(data.get("ffdtl_tast"))
        purpose_text = (
            f"{corp_name}의 {partner} 대상 {etype_kr} 공시입니다. "
            f"합병목적: {mg_pp or '경영 효율성 제고 및 시너지 창출'}. "
            f"합병방법: {mg_mth or '소규모/흡수합병'}. "
            f"합병결의일은 {bddd}입니다."
        )

    elif etype == "STOCK_ACQUISITION":
        inh_pp = (data.get("inh_pp") or data.get("acq_pp") or "").strip()
        partner = (data.get("dlptn_cmpnm") or data.get("iscmp_cmpnm") or data.get("tgcmp_cmpnm") or "대상기업").strip()
        scale_amount = parse_korean_amount(data.get("inhdtl_inhprc")) or parse_korean_amount(data.get("acq_amt"))
        purpose_text = (
            f"{corp_name}의 {partner} {etype_kr} 공시입니다. "
            f"취득/양수 목적: {inh_pp or '신규 사업 진출 및 지배력 확보, 사업 시너지 강화'}. "
            f"총 취득금액은 {scale_amount:,}원입니다."
        )

    else:
        purpose_text = f"{corp_name}의 {etype_kr} 주요사항 공시입니다."

    # scale_amount가 0인 경우 최소 1억원으로 기본 보정(로그 스케일 안전성 보장)
    if scale_amount <= 0:
        scale_amount = 100_000_000

    return {
        "event_id": event_id,
        "corp_name": corp_name,
        "corp_code": corp_code,
        "rcept_no": rcept_no,
        "event_type": etype,
        "scale_amount": scale_amount,
        "purpose_text": purpose_text
    }


def generate_embeddings(client: OpenAI, texts: List[str], batch_size: int = 50) -> List[List[float]]:
    """OpenAI text-embedding-3-small (dimensions=512) 배치 생성"""
    embeddings = []
    total = len(texts)
    for i in range(0, total, batch_size):
        batch = texts[i:i+batch_size]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            dimensions=512,
            input=batch
        )
        for item in response.data:
            embeddings.append(item.embedding)
        print(f"  [임베딩 생성] {len(embeddings)}/{total} 건 완료")
    return embeddings


def build_and_ingest():
    print("=" * 80)
    print("🚀 [Step 1] 자본이벤트 313건 purpose_text 파싱 & 512차원 임베딩 생성 시작")
    print("=" * 80)

    # 1. 파일 목록 수집
    filing_dir = PROJECT_ROOT / "data" / "dart_raw_filings" / "capital_events"
    json_files = sorted(glob.glob(str(filing_dir / "*.json")))
    print(f"📁 발견된 원본 JSON 파일: {len(json_files)}개")

    parsed_events = []
    for fpath in json_files:
        event_id = Path(fpath).stem
        with open(fpath, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        event = extract_event_fields(data, event_id)
        parsed_events.append(event)

    print(f"✅ 원본 파싱 완료: {len(parsed_events)}건 (전수 정상 처리)")
    print("   [샘플 purpose_text]:", parsed_events[0]["purpose_text"])

    # 2. OpenAI 임베딩 생성 (dimensions=512)
    print("\n🔮 OpenAI text-embedding-3-small (512차원) 배치 임베딩 시작...")
    client = OpenAI(api_key=OPENAI_API_KEY)
    all_texts = [e["purpose_text"] for e in parsed_events]
    embeddings_512 = generate_embeddings(client, all_texts, batch_size=50)

    for e, emb in zip(parsed_events, embeddings_512):
        e["embedding_512"] = emb

    print(f"✅ 512차원 임베딩 생성 완료: {len(embeddings_512)}개 (차원={len(embeddings_512[0])})")

    # 3. Neo4j Aura DB에 주입
    print(f"\n🌐 Cloud Neo4j Aura 연결: {AURA_URI}")
    driver = GraphDatabase.driver(AURA_URI, auth=(AURA_USER, AURA_PASSWORD))

    update_query = """
    UNWIND $events AS evt
    MATCH (e:DART_CapitalEvent {event_id: evt.event_id})
    SET e.purpose_text = evt.purpose_text,
        e.scale_amount = evt.scale_amount,
        e.embedding_512 = evt.embedding_512,
        e.rcept_no = coalesce(e.rcept_no, e.source_rcept_no, evt.rcept_no),
        e.embedding_dim = 512,
        e.embedding_model = 'text-embedding-3-small'
    RETURN count(e) AS updated_count
    """

    def _atomic_update_and_audit(tx, events_list):
        # 1) 전체 이벤트를 단일 트랜잭션 내에서 UNWIND 업데이트
        res = tx.run(update_query, events=events_list)
        updated_count = res.single()["updated_count"]

        # 2) 커밋 전 트랜잭션 내 정합성 감사
        audit_res = tx.run("""
        MATCH (e:DART_CapitalEvent)
        RETURN count(e) AS total,
               count(e.purpose_text) AS has_text,
               count(e.scale_amount) AS has_scale,
               count(e.embedding_512) AS has_vector
        """)
        rec = audit_res.single()
        
        # 계약 검증: 갱신된 노드 수 검증
        if updated_count < len(events_list):
            raise RuntimeError(
                f"[트랜잭션 롤백] 원자적 업데이트 건수 불일치: 대상 {len(events_list)}건 중 {updated_count}건만 갱신됨"
            )
        
        return updated_count, rec

    with driver.session() as session:
        print("  [트랜잭션 시작] session.execute_write() 단일 트랜잭션으로 313건 원자적 갱신 진행...")
        total_updated, rec = session.execute_write(_atomic_update_and_audit, parsed_events)
        print(f"  [DB 트랜잭션 커밋 완료] 총 {total_updated}/{len(parsed_events)} 노드 원자적 갱신 성공")
        print(f"📊 [DB 감사 결과]: 총 노드={rec['total']}, purpose_text 보유={rec['has_text']}, scale_amount 보유={rec['has_scale']}, embedding_512 보유={rec['has_vector']}")

    # 4. HNSW Vector Index 및 Fulltext Index 생성
    print("\n" + "=" * 80)
    print("⚡ [Step 2] Neo4j Aura HNSW Vector Index & Fulltext Index 빌드 DDL")
    print("=" * 80)

    vector_index_ddl = """
    CREATE VECTOR INDEX dart_capital_event_vector_idx IF NOT EXISTS
    FOR (e:DART_CapitalEvent)
    ON (e.embedding_512)
    OPTIONS {
      indexConfig: {
        `vector.dimensions`: 512,
        `vector.similarity_function`: 'cosine'
      }
    }
    """

    fulltext_index_ddl = """
    CREATE FULLTEXT INDEX dart_purpose_fulltext_idx IF NOT EXISTS
    FOR (e:DART_CapitalEvent)
    ON EACH [e.purpose_text, e.corp_name]
    """

    with driver.session() as session:
        print("  1) Vector Index 생성 시도...")
        session.run(vector_index_ddl)
        print("     ✅ dart_capital_event_vector_idx 생성 완료 (512차원, cosine)")

        print("  2) Fulltext Index 생성 시도...")
        session.run(fulltext_index_ddl)
        print("     ✅ dart_purpose_fulltext_idx 생성 완료 (purpose_text, corp_name)")

        # 인덱스 상태 점검
        idx_res = session.run("""
        SHOW INDEXES YIELD name, type, state, populationPercent
        WHERE name IN ['dart_capital_event_vector_idx', 'dart_purpose_fulltext_idx']
        RETURN name, type, state, populationPercent
        """)
        for r in idx_res:
            print(f"     -> Index: {r['name']} ({r['type']}), State: {r['state']}, Pop: {r['populationPercent']}%")

    driver.close()
    print("\n🎉 [Step 1 & Step 2 완료] 자본이벤트 512차원 임베딩 및 인덱스 구축 완료!")


if __name__ == "__main__":
    build_and_ingest()
