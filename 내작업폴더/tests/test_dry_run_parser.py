# -*- coding: utf-8 -*-
"""
🧪 [순수 오프라인 단위 테스트] DRY_RUN 파서 엔진 및 변조 탐지 매니페스트 검증
========================================================================================================
[설계 원칙 준수]
1. [Zero Network / Zero DB Connection]:
   - 외부 Neo4j Aura 네트워크 연결을 100% 배제하고, `FakeEdgeProvider` 인터페이스를 통해 순수 격리 검증.
2. [마스터 미해결 엔티티 격리 검증]:
   - 마스터에 없는 주체가 planned_creations에 단 1건도 들어가지 않고 skipped_records로 격리되는지 검증.
3. [의결권 및 직접성 원문 팩트 검증]:
   - 원문에 명시된 팩트와 상장사 마스터가 일치하는 건(SK스퀘어)만 정확히 planned_*에 진입하는지 검증.
4. [식별자 고유성 검증]:
   - source_edge_key에 ownership_basis가 포함되어 있는지 검증.
========================================================================================================
"""

import os
import sys
import hashlib
from typing import Dict, Set, Tuple

sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    ExistingEdgeProvider,
    run_dry_run_with_provider,
    canonical_json_bytes,
    compute_canonical_sha256
)

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"
EXPECTED_XML_BYTES = 5936670
EXPECTED_XML_SHA256 = "e276b64a391e79bd31ae06e074d8254c1406bf220ef8043c8e1a115e7fe10a1d"

class FakeEdgeProvider:
    """오프라인 단위 테스트용 가상 Provider 구현체 (Zero DB Network)"""
    def __init__(self, master_map: Dict[str, str] = None, existing_keys: Set[str] = None):
        if master_map is not None:
            self.master_map = master_map
        else:
            self.master_map = {
                "SK스퀘어㈜": "01596425",
                "SK스퀘어": "01596425"
            }
        self.existing_keys = existing_keys if existing_keys is not None else set()
        self.node_count = 1000
        self.rel_count = 500

    def get_corp_master_map(self) -> Dict[str, str]:
        return self.master_map

    def get_existing_edge_keys(self) -> Set[str]:
        return self.existing_keys

    def get_pre_counts(self) -> Tuple[int, int]:
        return (self.node_count, self.rel_count)

def test_fixture_integrity():
    """1. 고정 XML Fixture 바이트 크기 및 SHA-256 불변 검증"""
    assert os.path.exists(FIXTURE_PATH), f"❌ Fixture 누락: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "rb") as f:
        content = f.read()
    assert len(content) == EXPECTED_XML_BYTES, f"❌ 바이트 불일치: {len(content)} != {EXPECTED_XML_BYTES}"
    assert hashlib.sha256(content).hexdigest() == EXPECTED_XML_SHA256, "❌ SHA-256 불일치"
    print("  ✅ [Test 1 통과] XML Fixture 바이트 및 SHA-256 무결성 확인")

def test_canonical_json_rfc_sorting():
    """2. Canonical JSON 사전식 정렬 및 순환 참조 방지 해시 검증"""
    d1 = {"z": 9, "a": 1, "manifest_sha256": "EXCLUDE_ME"}
    d2 = {"a": 1, "z": 9}
    assert canonical_json_bytes(d1) == canonical_json_bytes(d2)
    assert compute_canonical_sha256(d1) == compute_canonical_sha256(d2)
    print("  ✅ [Test 2 통과] Canonical JSON 사전식 정렬 및 순환 참조 방지 확인")

def test_pure_offline_zero_write_and_quarantine():
    """3. FakeProvider 기반 순수 오프라인 실행 및 마스터 미해결 엔티티 격리 검증"""
    with open(FIXTURE_PATH, "rb") as f:
        xml_bytes = f.read()
        
    provider = FakeEdgeProvider()
    res = run_dry_run_with_provider(
        xml_bytes=xml_bytes,
        rcept_no="20240319000684",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_TEST_DB",
        manifest_id="TEST_OFFLINE_MANIFEST_01"
    )
    
    manifest = res["manifest"]
    
    # 1) Zero-Write 불변 검증
    assert manifest["pre_execution_state"]["total_nodes"] == 1000
    assert manifest["post_execution_state_expected"]["total_nodes"] == 1000
    assert manifest["pre_execution_state"]["total_relationships"] == 500
    assert manifest["post_execution_state_expected"]["total_relationships"] == 500
    
    # 2) 마스터 미해결 주체 planned_* 유입 차단 검증
    all_planned = manifest["planned_creations"] + manifest["planned_updates"]
    planned_holders = [r["holder_name"] for r in all_planned]
    assert "박정호" not in planned_holders, "❌ 미해결 개인(박정호)이 planned_*에 포함됨!"
    assert "곽노정" not in planned_holders, "❌ 미해결 개인(곽노정)이 planned_*에 포함됨!"
    
    # 2) 0% 지분율 및 비적격 행 skipped_records 격리 사유 검증
    skipped = manifest["skipped_records"]
    reasons = [s.get("skip_reason") for s in skipped]
    assert "ZERO_STAKE_RATIO_EXCLUDED" in reasons, "❌ 지분율 0% 행이 skipped_records에 격리되지 않음!"
    
    # 3) 마스터에 주체가 없을 때 UNRESOLVED_MASTER_ENTITY 격리 검증 (마스터 비어있는 Provider로 검증)
    empty_provider = FakeEdgeProvider(master_map={})
    res_unresolved = run_dry_run_with_provider(
        xml_bytes=xml_bytes,
        rcept_no="20240319000684",
        target_corp_code="00164779",
        provider=empty_provider,
        database_instance_id="FAKE_TEST_DB"
    )
    unres_manifest = res_unresolved["manifest"]
    unres_skipped = unres_manifest["skipped_records"]
    unres_reasons = [s.get("skip_reason") for s in unres_skipped]
    assert "UNRESOLVED_MASTER_ENTITY_AWAITING_MASTER_RESOLUTION" in unres_reasons, "❌ 마스터 미해결 시 격리 사유 누락!"
    assert len(unres_manifest["planned_creations"]) == 0, "❌ 마스터 미해결 시 planned_creations는 0건이어야 함!"
    
    # 4) 유일하게 공인 마스터와 원문 팩트가 일치하는 SK스퀘어만 planned_creations 진입 확인
    assert len(manifest["planned_creations"]) == 1, f"❌ planned_creations 건수 오류: {len(manifest['planned_creations'])}"
    sq_rec = manifest["planned_creations"][0]
    assert sq_rec["holder_name"] == "SK스퀘어㈜"
    assert sq_rec["holder_pk"] == "01596425"
    assert sq_rec["stake"] == 20.07
    assert sq_rec["voting_type"] == "VOTING"
    assert sq_rec["ownership_basis"] == "DIRECT"
    assert sq_rec["as_of_date"] == "2023-12-31"
    
    # 5) source_edge_key에 ownership_basis 포함 검증
    expected_edge_key = "20240319000684_01596425_00164779_COMMON_VOTING_DIRECT"
    assert sq_rec["source_edge_key"] == expected_edge_key, f"❌ 키 불일치: {sq_rec['source_edge_key']} != {expected_edge_key}"
    
    print(f"  ✅ [Test 3 통과] 오프라인 Zero-Write 및 마스터 미해결 엔티티 격리 검증 완료 (planned: {len(all_planned)}건, skipped: {len(skipped)}건)")

def main():
    print("="*80)
    print("🧪 [순수 오프라인 단위 테스트 실행] (Zero DB Network)")
    print("="*80)
    
    test_fixture_integrity()
    test_canonical_json_rfc_sorting()
    test_pure_offline_zero_write_and_quarantine()
    
    print("\n" + "="*80)
    print("🎉 [단위 테스트 100% 통과] 순수 오프라인 환경에서 4대 엄격 원칙 완벽 검증!")
    print("="*80)

if __name__ == "__main__":
    main()
