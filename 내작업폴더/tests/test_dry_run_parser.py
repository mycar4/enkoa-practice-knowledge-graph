# -*- coding: utf-8 -*-
"""
🧪 [v1.3.0 순수 오프라인 단위 테스트] 2D 헤더 그리드 및 4대 독립 팩트 무결성 검증
========================================================================================================
[테스트 핵심 철학]
1. [True-Zero 정당성 검증]:
   - 실 DART 공시(SK하이닉스 2023 사업보고서) 원문 표에 독립적 소유형태 컬럼이 없으므로,
     가정값 없이 엄격히 '0건의 planned_creations'가 도출되고 모든 행이 skipped_records로 안전 격리됨을 검증.
2. [2D 헤더 매트릭스 복원 검증]:
   - ROWSPAN, COLSPAN을 전개하여 각 컬럼의 계층 경로(Header Path)가 동적으로 올바르게 산출되는지 검증.
3. [4대 독립 팩트 완비 시에만 승격 검증]:
   - 가상 합성 표(Synthetic Table)에 주식종류, 의결권, 직접소유형태, 3대 엔티티가 모두 독립 명시되었을 때만
     planned_creations 1건으로 정당하게 승격되는지 대조 검증.
========================================================================================================
"""

import os
import sys
import hashlib
from typing import Dict, Set, Tuple, Optional

sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    MasterEntityProvider,
    build_2d_header_paths,
    run_dry_run_simulation_v13,
    canonical_json_bytes,
    compute_canonical_sha256
)

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"

class Fake3EntityManager:
    """3대 공인 엔티티 Exact-Match 가상 Provider (Zero DB Network)"""
    def __init__(self):
        self.companies = {"SK스퀘어㈜": "01596425", "SK스퀘어": "01596425"}
        self.persons = {"최태원": "PERSON_CHOI_TW_01"}
        self.orgs = {"국민연금공단": "ORG_NPS_KR"}
        self.existing_keys = set()
        self.node_count = 5592
        self.rel_count = 1873

    def resolve_company(self, name_or_code: str) -> Optional[str]:
        return self.companies.get(name_or_code) or self.companies.get(name_or_code.replace("㈜", "").strip())

    def resolve_person(self, name: str, resident_no_or_id: str = "") -> Optional[str]:
        return self.persons.get(name)

    def resolve_organization(self, name_or_id: str) -> Optional[str]:
        return self.orgs.get(name_or_id)

    def get_existing_edge_keys(self) -> Set[str]:
        return self.existing_keys

    def get_pre_counts(self) -> Tuple[int, int]:
        return (self.node_count, self.rel_count)

def test_2d_header_grid_reconstruction():
    """1. 2D 헤더 매트릭스 ROWSPAN/COLSPAN 동적 전개 검증"""
    sample_table = """
    <TABLE>
      <TR>
        <TH ROWSPAN="3">성 명</TH>
        <TH ROWSPAN="3">관 계</TH>
        <TH ROWSPAN="3">주식의종류</TH>
        <TH COLSPAN="4">소유주식수 및 지분율</TH>
      </TR>
      <TR>
        <TH COLSPAN="2">기 초</TH>
        <TH COLSPAN="2">기 말</TH>
      </TR>
      <TR>
        <TH>주식수</TH>
        <TH>지분율</TH>
        <TH>주식수</TH>
        <TH>지분율</TH>
      </TR>
      <TR><TD>A</TD><TD>B</TD><TD>C</TD><TD>1</TD><TD>2</TD><TD>3</TD><TD>4</TD></TR>
    </TABLE>
    """
    paths, num_rows = build_2d_header_paths(sample_table)
    assert num_rows == 3, f"❌ 헤더 행 수 불일치: {num_rows}"
    assert paths[0] == ["성 명"], f"❌ Col 0 경로 오류: {paths[0]}"
    assert paths[1] == ["관 계"], f"❌ Col 1 경로 오류: {paths[1]}"
    assert paths[2] == ["주식의종류"], f"❌ Col 2 경로 오류: {paths[2]}"
    assert paths[5] == ["소유주식수 및 지분율", "기 말", "주식수"], f"❌ Col 5 경로 오류: {paths[5]}"
    assert paths[6] == ["소유주식수 및 지분율", "기 말", "지분율"], f"❌ Col 6 경로 오류: {paths[6]}"
    print("  ✅ [Test 1 통과] 2D 헤더 매트릭스 ROWSPAN/COLSPAN 계층 경로(Header Path) 완벽 복원 입증")

def test_true_zero_candidate_legitimacy():
    """2. 실 공시 표에서 독립적 소유형태/주식종류 결측 시 '0건 WRITE 후보' 정상 판정 검증"""
    with open(FIXTURE_PATH, "rb") as f:
        xml_bytes = f.read()
        
    provider = Fake3EntityManager()
    res = run_dry_run_simulation_v13(
        xml_bytes=xml_bytes,
        rcept_no="20240319000684",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_TEST_DB",
        manifest_id="TEST_TRUE_ZERO_MANIFEST"
    )
    
    manifest = res["manifest"]
    
    # 실 원문에는 '소유형태(직접/간접)' 독립 컬럼이 없으므로 planned_creations는 0건이어야 함
    assert len(manifest["planned_creations"]) == 0, f"❌ 원문 결측에도 planned_creations가 생성됨: {len(manifest['planned_creations'])}"
    assert len(manifest["planned_updates"]) == 0
    
    # 모든 행이 skipped_records로 안전 격리되었는지 검증
    skipped = manifest["skipped_records"]
    assert len(skipped) > 0, "❌ 결측 행들이 skipped_records로 격리되지 않음"
    
    reasons = [s.get("skip_reason") for s in skipped]
    # 독립 주식종류 또는 소유형태 결측 사유 확인
    assert any("UNVERIFIED_INDEPENDENT" in r for r in reasons), f"❌ 독립 팩트 미확인 사유 누락: {set(reasons)}"
    
    print(f"  ✅ [Test 2 통과] 원문 독립 증거 결측 시 '0건 WRITE 후보 (True-Zero 무결성)' 완벽 입증 (격리: {len(skipped)}건)")

def test_synthetic_table_with_all_4_independent_facts():
    """3. 4대 독립 팩트(종류, 의결권, 소유형태, 엔티티)가 모두 완비된 합성 표 승격 검증"""
    synthetic_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      기준일 : 2023년 12월 31일
      <TABLE>
        <TR>
          <TH ROWSPAN="2">성 명</TH>
          <TH ROWSPAN="2">관 계</TH>
          <TH ROWSPAN="2">소유형태</TH>
          <TH ROWSPAN="2">주식의종류</TH>
          <TH COLSPAN="2">기 말</TH>
        </TR>
        <TR>
          <TH>주식수</TH>
          <TH>지분율</TH>
        </TR>
        <TR>
          <TD>SK스퀘어㈜</TD>
          <TD>최대주주</TD>
          <TD>직접소유</TD>
          <TD>보통주 (의결권 있는 주식)</TD>
          <TD>146,100,000</TD>
          <TD>20.07</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = Fake3EntityManager()
    res = run_dry_run_simulation_v13(
        xml_bytes=synthetic_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_TEST_DB",
        manifest_id="TEST_SYNTHETIC_ALL_FACTS"
    )
    
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 1, f"❌ 4대 팩트 완비 시 planned_creations 1건 승격 실패: {len(manifest['planned_creations'])}"
    
    rec = manifest["planned_creations"][0]
    assert rec["holder_name"] == "SK스퀘어㈜"
    assert rec["holder_pk"] == "01596425"
    assert rec["share_class"] == "COMMON"
    assert rec["voting_type"] == "VOTING"
    assert rec["ownership_basis"] == "DIRECT"
    assert rec["stake"] == 20.07
    assert rec["as_of_date"] == "2023-12-31"
    assert rec["source_edge_key"] == "99999999999999_01596425_00164779_COMMON_VOTING_DIRECT"
    print("  ✅ [Test 3 통과] 4대 독립 팩트 100% 완비 시에만 정당하게 planned_creations 승격 입증")

def main():
    print("="*80)
    print("🧪 [v1.3.0 순수 오프라인 단위 테스트 실행] (Zero DB Network)")
    print("="*80)
    
    test_2d_header_grid_reconstruction()
    test_true_zero_candidate_legitimacy()
    test_synthetic_table_with_all_4_independent_facts()
    
    print("\n" + "="*80)
    print("🎉 [단위 테스트 100% 전수 통과] 2D 헤더 그리드 및 4대 독립 팩트 규격 완전 무결성 확인!")
    print("="*80)

if __name__ == "__main__":
    main()
