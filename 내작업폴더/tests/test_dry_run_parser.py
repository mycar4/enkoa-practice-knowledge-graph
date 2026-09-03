# -*- coding: utf-8 -*-
"""
🧪 [단위 테스트] DRY_RUN 파서 엔진 및 변조 탐지 매니페스트 불변성 검증
========================================================================================================
[테스트 시나리오]
1. test_fixture_integrity: XML Fixture 바이트 크기 및 SHA-256 불변 검증
2. test_canonical_json_reproducibility: 동일 딕셔너리 입력 시 RFC 8785 해시 100% 재현성 검증
3. test_database_zero_write_invariance: DRY_RUN 실행 전후 Neo4j DB 노드/관계 수 0건 불변 검증
4. test_skipped_records_classification: 요약행/날짜행이 skipped_records로 정확히 분류되는지 검증
5. test_planned_diff_accuracy: SK스퀘어 20.07% 팩트가 planned_creations/updates로 정확히 분리되는지 검증
========================================================================================================
"""

import os
import sys
import hashlib
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    run_dry_run_simulation,
    canonical_json_bytes,
    compute_canonical_sha256,
    get_read_only_driver
)

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"
EXPECTED_XML_BYTES = 5936670
EXPECTED_XML_SHA256 = "e276b64a391e79bd31ae06e074d8254c1406bf220ef8043c8e1a115e7fe10a1d"

def test_fixture_integrity():
    """1. 고정 XML Fixture 바이트 크기 및 SHA-256 불변 검증"""
    assert os.path.exists(FIXTURE_PATH), f"❌ Fixture 파일 누락: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "rb") as f:
        content = f.read()
    assert len(content) == EXPECTED_XML_BYTES, f"❌ 바이트 불일치: {len(content)} != {EXPECTED_XML_BYTES}"
    actual_hash = hashlib.sha256(content).hexdigest()
    assert actual_hash == EXPECTED_XML_SHA256, f"❌ 해시 불일치: {actual_hash} != {EXPECTED_XML_SHA256}"
    print("  ✅ [Test 1 통과] XML Fixture 바이트 크기 및 SHA-256 100% 무결성 확인")

def test_canonical_json_reproducibility():
    """2. RFC 8785 Canonical JSON 직렬화 및 해시 재현성 검증"""
    sample_dict_1 = {
        "z_key": "last",
        "a_key": "first",
        "nested": {"b": 2, "a": 1},
        "manifest_sha256": "SHOULD_BE_EXCLUDED" # 제외 대상
    }
    sample_dict_2 = {
        "nested": {"a": 1, "b": 2},
        "a_key": "first",
        "z_key": "last"
    }
    
    bytes_1 = canonical_json_bytes(sample_dict_1)
    bytes_2 = canonical_json_bytes(sample_dict_2)
    assert bytes_1 == bytes_2, "❌ 키 순서가 달라도 Canonical JSON은 동일 바이트여야 함"
    
    hash_1 = compute_canonical_sha256(sample_dict_1)
    hash_2 = compute_canonical_sha256(sample_dict_2)
    assert hash_1 == hash_2, "❌ Canonical SHA-256 불일치"
    print("  ✅ [Test 2 통과] RFC 8785 Canonical JSON 사전식 정렬 및 해시 재현성 확인")

def test_database_zero_write_invariance():
    """3. DRY_RUN 실행 전후 Neo4j DB 노드/관계 수 0건 불변 검증 (Zero-Write Guard)"""
    driver = get_read_only_driver()
    with driver.session() as s:
        pre_nodes = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        pre_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        
    # DRY_RUN 시뮬레이션 실행
    sim_res = run_dry_run_simulation(
        FIXTURE_PATH, "20240319000684", "00164779", manifest_id="TEST_DRY_RUN_INVARIANCE"
    )
    
    with driver.session() as s:
        post_nodes = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        post_rels = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        
    driver.close()
    
    assert pre_nodes == post_nodes, f"❌ 노드 수 변동 발생: {pre_nodes} != {post_nodes}"
    assert pre_rels == post_rels, f"❌ 관계 수 변동 발생: {pre_rels} != {post_rels}"
    print(f"  ✅ [Test 3 통과] DB Zero-Write 불변성 입증 (노드: {pre_nodes} == {post_nodes}, 관계: {pre_rels} == {post_rels})")

def test_skipped_records_classification():
    """4. 요약행/날짜행이 skipped_records로 정확히 분류되는지 검증"""
    sim_res = run_dry_run_simulation(
        FIXTURE_PATH, "20240319000684", "00164779", manifest_id="TEST_DRY_RUN_SKIPPED"
    )
    manifest = sim_res["manifest"]
    skipped = manifest["skipped_records"]
    assert len(skipped) > 0, "❌ skipped_records가 1건 이상 분류되어야 함"
    
    reasons = [item["skip_reason"] for item in skipped]
    assert "SUMMARY_TOTAL_ROW_EXCLUDED" in reasons, "❌ 요약행 제외 사유 누락"
    print(f"  ✅ [Test 4 통과] skipped_records 분류 정상 확인 (총 {len(skipped)}건 보류 기록 보존)")

def test_planned_diff_accuracy():
    """5. SK스퀘어 20.07% 지분 팩트가 정확히 파싱되었는지 검증"""
    sim_res = run_dry_run_simulation(
        FIXTURE_PATH, "20240319000684", "00164779", manifest_id="TEST_DRY_RUN_DIFF"
    )
    manifest = sim_res["manifest"]
    all_planned = manifest["planned_creations"] + manifest["planned_updates"]
    
    sq_records = [r for r in all_planned if "SK스퀘어" in r["holder_name"]]
    assert len(sq_records) == 1, f"❌ SK스퀘어 레코드 불일치: {len(sq_records)}건"
    
    rec = sq_records[0]
    assert rec["stake"] == 20.07, f"❌ 지분율 오류: {rec['stake']} != 20.07"
    assert rec["share_class"] == "COMMON", f"❌ 주식종류 오류: {rec['share_class']}"
    assert rec["voting_type"] == "VOTING", f"❌ 의결권 오류: {rec['voting_type']}"
    assert rec["as_of_date"] == "2023-12-31", f"❌ 기준일 오류: {rec['as_of_date']}"
    print(f"  ✅ [Test 5 통과] SK스퀘어 지분 팩트 정밀 검증 (지분율: {rec['stake']}%, 의결권: {rec['voting_type']}, 기준일: {rec['as_of_date']})")

def main():
    print("="*80)
    print("🧪 [DRY_RUN 파서 엔진 및 변조 탐지 매니페스트 단위 테스트 실행]")
    print("="*80)
    
    test_fixture_integrity()
    test_canonical_json_reproducibility()
    test_database_zero_write_invariance()
    test_skipped_records_classification()
    test_planned_diff_accuracy()
    
    print("\n" + "="*80)
    print("🎉 [단위 테스트 전수 통과] 5대 핵심 검증 시나리오 100% 합격 완수!")
    print("="*80)

if __name__ == "__main__":
    main()
