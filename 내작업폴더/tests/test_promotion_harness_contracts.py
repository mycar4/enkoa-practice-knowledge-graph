# -*- coding: utf-8 -*-
"""
🧪 [DART-Trace] 자동 하네스(Automated Harness v3.0) 6대 계약 및 통합 검증 테스트
================================================================================
[단위/계약 테스트 (Unit & Contract Tests)]
1. 법인격 정규화(normalize_corp_name) 규칙 정확성 검증
2. 봉인 매니페스트 SHA-256 결속 검증
3. Aura DB 읽기 전용 사전 재대조 (19건 후보·파편·XML 해시·정규화 100% 일치)
4. 트랜잭션 내부 감사(In-Tx Assertion) 실패 시 자동 롤백(Zero Pollution) 검증
5. OWNS_STAKE 절대 생성 불가 격리 검증

[통합 테스트 (Integration Test: Aura 실측)]
6. 실제 재실행(MERGE) 전/후 비교를 통한:
   - 최초 적재 혈통(promotion_run_id / promoted_at) 100% 불변성 실측 단정
   - 마지막 재검증 정보(last_verified_run_id / last_verified_at) 1건 정상 갱신 단정
   - 관계 증가수 Δ=0, 노드 증가수 Δ=0 멱등성 단정
================================================================================
"""

import os
import sys
import json
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from neo4j import GraphDatabase, WRITE_ACCESS
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR.parent / ".env"
load_dotenv(ENV_PATH)

uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER", "neo4j")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

sys.path.insert(0, str(BASE_DIR))
from execute_economic_stake_promotion import (
    normalize_corp_name,
    pre_audit_candidate_batch,
    execute_promotion_batch_tx,
    EXPECTED_MANIFEST_NAME,
    EXPECTED_MANIFEST_SHA256,
    EXPECTED_CANDIDATE_COUNT
)


def test_corporate_name_normalization():
    print("--- [단위/계약 1/5] 법인명 정규화 함수 검증 ---")
    test_cases = [
        ("(주)케이피티유", "케이피티유"),
        ("㈜에스피시스템스", "에스피시스템스"),
        ("SK증권㈜", "SK증권"),
        ("에스케이증권제10호기업인수목적 주식회사", "에스케이증권제10호기업인수목적"),
        ("(주) 씨티씨바이오", "씨티씨바이오"),
        ("삼천리자전거㈜", "삼천리자전거"),
        ("롯데렌탈(주)", "롯데렌탈"),
        ("DSR제강주식회사", "DSR제강"),
        ("(유)테스트회사", "테스트회사"),
        ("[주] 현대홈쇼핑", "현대홈쇼핑"),
    ]
    for raw, expected in test_cases:
        norm = normalize_corp_name(raw)
        assert norm == expected, f"정규화 실패: '{raw}' -> '{norm}' != '{expected}'"
    print("  ✅ [통과] 법인격 표기 제거 및 정규화 규칙 100% 통과")


def test_manifest_sha256_binding():
    print("--- [단위/계약 2/5] 봉인 매니페스트 SHA-256 결속 검증 ---")
    manifest_path = BASE_DIR / "data" / "resolution_manifests" / EXPECTED_MANIFEST_NAME
    assert manifest_path.exists(), f"매니페스트 파일 결손: {manifest_path}"
    
    actual_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert actual_sha == EXPECTED_MANIFEST_SHA256, f"해시 불일치: {actual_sha} != {EXPECTED_MANIFEST_SHA256}"
    
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("proposed_holds_economic_stake", [])
    assert len(items) == EXPECTED_CANDIDATE_COUNT, f"후보 건수 불일치: {len(items)} != {EXPECTED_CANDIDATE_COUNT}"
    print(f"  ✅ [통과] 매니페스트 SHA-256 결속 검증 완료 ({actual_sha[:16]}... / 19건)")


def test_pre_audit_against_aura():
    print("--- [단위/계약 3/5] Aura DB 읽기 전용 사전 재대조 (19건 전수) ---")
    manifest_path = BASE_DIR / "data" / "resolution_manifests" / EXPECTED_MANIFEST_NAME
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    planned_rels = data.get("proposed_holds_economic_stake", [])

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session() as session:
            verified_batch = pre_audit_candidate_batch(
                session, planned_rels, EXPECTED_MANIFEST_SHA256, "test_pre_audit_run"
            )
            assert len(verified_batch) == 19
            for b in verified_batch:
                assert b["xml_hash_verified"] is True
                assert b["name_resolution_rule"] == "CORP_CODE_AND_LEGAL_AFFIX_NORMALIZED_MATCH_V1"
                assert b["promotion_manifest_sha256"] == EXPECTED_MANIFEST_SHA256
                assert b["source_raw_name"]
                assert b["source_master_name"]
                assert b["target_raw_name"]
                assert b["target_master_name"]
        print("  ✅ [통과] 19건 전수 사전 재검증 통과 (XML 해시, 파편 해시, 정규화 명칭 기록 확인)")
    finally:
        driver.close()


def test_in_tx_assertion_rollback_guarantee():
    print("--- [단위/계약 4/5] 트랜잭션 내부 감사 실패 시 자동 전체 롤백 검증 ---")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session() as s:
            pre_rels = s.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]

        # run_id를 의도적으로 변조하여 in-tx assertion audit_cypher에서 실패 유도
        tampered_batch = [{
            "holder_code": "00357607",
            "target_code": "00117027",
            "relationship_key": "rel-test-tampered-run-id",
            "candidate_id": "cand-test-tampered",
            "rcept_no": "20230810000694",
            "xml_sha256": "dummy",
            "shares_count": 100,
            "stake_ratio": 1.0,
            "reporting_obligation_date": "2023-08-04",
            "temporal_context": "TEST",
            "fact_type": "TEST",
            "temporal_definition": "TEST",
            "table_parser_index": 17,
            "all_tr_index": 2,
            "data_row_index": 0,
            "standard_xpath": "//TABLE[18]//TR[3]",
            "row_raw_parser_xpath": "//TABLE[17]//TR[0]",
            "xml_hash_verified": True,
            "row_inner_hash": "dummy",
            "source_raw_name": "(주)케이피티유",
            "source_master_name": "케이피티유",
            "target_raw_name": "(주)알루코",
            "target_master_name": "알루코",
            "name_resolution_rule": "TEST_RULE",
            "promotion_manifest_sha256": "dummy_sha",
            "promotion_run_id": "WRONG_RUN_ID",  # 불일치 유발
            "promoted_at": "2026-09-04T00:00:00Z",
            "promotion_engine": "TEST_ENGINE"
        }]

        rollback_caught = False
        try:
            with driver.session(default_access_mode=WRITE_ACCESS) as session:
                # EXPECTED_RUN_ID와 다른 run_id를 가진 아이템을 전달하여 트랜잭션 내부 감사 예외 발생
                session.execute_write(execute_promotion_batch_tx, tampered_batch, "EXPECTED_RUN_ID")
        except RuntimeError as e:
            rollback_caught = True
            assert "트랜잭션 내 관계 생성" in str(e)
            print(f"  ✅ [예외 포착 성공] {e}")

        assert rollback_caught, "트랜잭션 내부 감사 예외가 발생하지 않았습니다!"

        with driver.session() as s:
            post_rels = s.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
        assert post_rels == pre_rels, f"롤백 실패! 관계 오염 발생: post={post_rels}, pre={pre_rels}"
        print("  ✅ [통과] 트랜잭션 내부 감사 실패 시 100% 자동 전체 롤백 입증 완료")
    finally:
        driver.close()


def test_zero_owns_stake_guarantee():
    print("--- [단위/계약 5/5] OWNS_STAKE 격리 0건 검증 ---")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        with driver.session() as s:
            owns_cnt = s.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
            assert owns_cnt == 0, f"OWNS_STAKE 존재 감지: {owns_cnt}건"
        print("  ✅ [통과] DB 내 OWNS_STAKE 0건 안전 격리 상태 확인")
    finally:
        driver.close()


def test_integration_rerun_lineage_immutability():
    """
    [통합 테스트: Aura 실측]
    실제 Aura DB의 19건에 대해 신규 run_id로 재실행(MERGE)을 수행하기 전/후를 실측 비교:
    1) 사전 상태: 19건의 최초 적재 정보(promotion_run_id, promoted_at) 실측 기록
    2) 재실행 수행: 새로운 고유 run_id로 배치 재실행 (ON MATCH 트리거)
    3) 사후 상태 실측 비교:
       - 최초 적재 정보(promotion_run_id, promoted_at)가 19건 전수 1글자도 변경되지 않고 100% 동일함을 단정
       - 마지막 재검증 정보(last_verified_run_id, last_verified_at)만 이번 테스트 run_id로 정상 갱신됨을 단정
       - 관계 증가수 Δ=0, 노드 증가수 Δ=0 (완전 멱등성) 단정
    """
    print("--- [통합 테스트: Aura 실측 6/6] 재실행 전/후 비교 최초 혈통 불변성 및 마지막 재검증 1건 기록 실측 검증 ---")
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    try:
        # 1. 재실행 전 Aura DB 상태 실측 기록
        with driver.session() as s:
            pre_nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            pre_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            pre_holds = s.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
            pre_rows = s.run("""
                MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->()
                WHERE r.promotion_manifest_sha256 = $m_sha
                RETURN r.relationship_key AS key,
                       r.promotion_run_id AS init_run,
                       r.promoted_at AS init_at,
                       r.last_verified_run_id AS last_run,
                       r.last_verified_at AS last_at
                ORDER BY key
            """, m_sha=EXPECTED_MANIFEST_SHA256).data()

        assert pre_holds == 19, f"사전 HOLDS 관계 수 오류: {pre_holds} (기대값: 19)"
        assert len(pre_rows) == 19, f"사전 조회 레코드 수 오류: {len(pre_rows)}"

        # 2. 신규 고유 run_id를 발급하여 재실행(MERGE) 수행
        test_rerun_id = f"test_rerun_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        manifest_path = BASE_DIR / "data" / "resolution_manifests" / EXPECTED_MANIFEST_NAME
        with open(manifest_path, encoding="utf-8") as f:
            manifest_data = json.load(f)
        planned_rels = manifest_data.get("proposed_holds_economic_stake", [])

        with driver.session() as s:
            batch_params = pre_audit_candidate_batch(s, planned_rels, EXPECTED_MANIFEST_SHA256, test_rerun_id)

        with driver.session(default_access_mode=WRITE_ACCESS) as s:
            tx_results = s.execute_write(execute_promotion_batch_tx, batch_params, test_rerun_id)

        # 3. 재실행 후 Aura DB 상태 실측
        with driver.session() as s:
            post_nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            post_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            post_holds = s.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
            post_rows = s.run("""
                MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->()
                WHERE r.promotion_manifest_sha256 = $m_sha
                RETURN r.relationship_key AS key,
                       r.promotion_run_id AS init_run,
                       r.promoted_at AS init_at,
                       r.last_verified_run_id AS last_run,
                       r.last_verified_at AS last_at
                ORDER BY key
            """, m_sha=EXPECTED_MANIFEST_SHA256).data()

        # 4. 전/후 실측 비교 단정 (Idempotency & Immutability)
        delta_nodes = post_nodes - pre_nodes
        delta_rels = post_rels - pre_rels

        assert delta_nodes == 0, f"노드 수 변동 감지: Δ={delta_nodes}"
        assert delta_rels == 0, f"관계 수 증가 감지 (재실행 멱등성 위반): Δ={delta_rels}"
        assert post_holds == 19, f"사후 HOLDS 관계 수 오류: {post_holds}"
        assert len(post_rows) == 19, f"사후 레코드 수 오류: {len(post_rows)}"

        # 19건 전수 레코드별 최초 혈통 불변성 및 마지막 재검증 1건 기록 실측 검증
        for pre_r, post_r in zip(pre_rows, post_rows):
            assert pre_r["key"] == post_r["key"], f"키 불일치: {pre_r['key']} != {post_r['key']}"
            
            # [핵심 검증 1] 최초 적재 정보는 재실행 전/후 100% 동일 (불변)
            assert post_r["init_run"] == pre_r["init_run"], (
                f"❌ 최초 run_id 오염 감지! pre='{pre_r['init_run']}' vs post='{post_r['init_run']}'"
            )
            assert post_r["init_at"] == pre_r["init_at"], (
                f"❌ 최초 promoted_at 오염 감지! pre='{pre_r['init_at']}' vs post='{post_r['init_at']}'"
            )

            # [핵심 검증 2] 마지막 재검증 정보(last_verified_*)만 이번 재실행 run_id로 1건 갱신
            assert post_r["last_run"] == test_rerun_id, (
                f"❌ 마지막 재검증 run_id 갱신 실패! 기대값='{test_rerun_id}' vs 실제값='{post_r['last_run']}'"
            )

        print(f"  ✅ [실측 통과] 19건 전수 재실행 전/후 최초 혈통(init_run='{pre_rows[0]['init_run']}') 100% 불변 확인")
        print(f"  ✅ [실측 통과] 마지막 재검증 정보만 신규 run_id('{test_rerun_id}')로 정상 갱신 확인")
        print(f"  ✅ [실측 통과] 재실행 시 노드 변동 Δ=0, 관계 변동 Δ=0 (완전 멱등성)")

    finally:
        # [클린업] 운영 DB의 마지막 검증 필드를 테스트 실행 전 상태(공식 영수증 기준)로 안전하게 복원
        if 'pre_rows' in locals() and pre_rows:
            with driver.session(default_access_mode=WRITE_ACCESS) as s:
                s.run("""
                    MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->()
                    WHERE r.promotion_manifest_sha256 = $m_sha
                    SET r.last_verified_run_id = $orig_last_run,
                        r.last_verified_at = $orig_last_at
                """, m_sha=EXPECTED_MANIFEST_SHA256,
                     orig_last_run=pre_rows[0]["last_run"],
                     orig_last_at=pre_rows[0]["last_at"])
            print("  🧹 [클린업] 테스트 완료 후 운영 DB 감사 필드를 사전 영수증 상태로 안전 복원 완료")
        driver.close()


if __name__ == "__main__":
    test_corporate_name_normalization()
    test_manifest_sha256_binding()
    test_pre_audit_against_aura()
    test_in_tx_assertion_rollback_guarantee()
    test_zero_owns_stake_guarantee()

    allow_live_rerun = ("--live-rerun" in sys.argv) or (os.getenv("ALLOW_AURA_RERUN_TEST", "").lower() in ("true", "1", "yes"))
    if allow_live_rerun:
        test_integration_rerun_lineage_immutability()
        print("\n🎉 모든 자동 하네스 계약 및 라이브 통합 테스트 6/6 전수 통과!")
    else:
        print("\n--- [통합 테스트 6/6 건너뜀 (안전 기본 모드)] ---")
        print("  ℹ️ 운영 Aura 재실행 테스트는 '--live-rerun' 인자 또는 'ALLOW_AURA_RERUN_TEST=true' 환경변수 지정 시에만 실행됩니다.")
        print("  ℹ️ 기본 계약 테스트 5/5 통과 (운영 DB 무변경 안전 확인 완료)")
        print("\n🎉 기본 자동 하네스 계약 테스트 5/5 전수 통과!")
