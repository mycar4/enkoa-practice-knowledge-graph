# -*- coding: utf-8 -*-
"""
🧪 [v1.3.1 순수 오프라인 단위 테스트] 2D 좌표 보존 및 다중 매칭 방어 검증
========================================================================================================
[테스트 핵심 검증]
1. [True-Zero 정당성 검증]:
   - 실 DART 공시(SK하이닉스) 표 내부 기준일 및 소유형태 부재 시 0건 WRITE 후보 도출 및 100% 격리 검증.
2. [빈 셀 열 밀림 방지(Column Shift Prevention) 검증]:
   - 데이터 행에 빈 셀(<TD></TD>)이 존재할 때도 2D 좌표가 온전히 보존되어 열이 밀리지 않는지 검증.
3. [동명이인/다중 매칭 방어 검증]:
   - 동일 이름의 PK가 2개 이상일 때 AMBIGUOUS_MASTER_ENTITY_MULTIPLE_MATCHES로 100% 차단 격리 검증.
4. [소유형태 None 누수 원천 차단 검증]:
   - 알 수 없는 소유형태 값 입력 시 None으로 통과하지 않고 즉시 격리되는지 검증.
========================================================================================================
"""

import os
import sys
from typing import Dict, Set, Tuple, Optional, List

sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    MasterEntityProvider,
    build_2d_table_matrix,
    run_dry_run_simulation_v131
)

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"

class Fake3EntityAmbiguityManager:
    """동명이인/동일법인명 다중 매칭 방어 가상 Provider"""
    def __init__(self):
        # name -> list of PKs
        self.companies: Dict[str, List[str]] = {
            "SK스퀘어㈜": ["01596425"],
            "SK스퀘어": ["01596425"],
            "중복법인": ["CORP_DUP_01", "CORP_DUP_02"] # 다중 매칭 케이스
        }
        self.persons: Dict[str, List[str]] = {
            "최태원": ["PERSON_CHOI_TW_01"],
            "김철수": ["PERSON_KIM_01", "PERSON_KIM_02"] # 동명이인 케이스
        }
        self.orgs: Dict[str, List[str]] = {
            "국민연금공단": ["ORG_NPS_KR"]
        }
        self.existing_keys = set()
        self.node_count = 5592
        self.rel_count = 1873

    def resolve_company(self, name_or_code: str) -> Tuple[Optional[str], bool]:
        clean = name_or_code.replace("(주)", "").replace("주식회사", "").replace("㈜", "").strip()
        pks = self.companies.get(name_or_code) or self.companies.get(clean) or []
        if len(pks) > 1: return (None, True) # 다중 매칭
        if len(pks) == 1: return (pks[0], False) # 단일 매칭
        return (None, False)

    def resolve_person(self, name: str, resident_no_or_id: str = "") -> Tuple[Optional[str], bool]:
        pks = self.persons.get(name) or []
        if len(pks) > 1: return (None, True)
        if len(pks) == 1: return (pks[0], False)
        return (None, False)

    def resolve_organization(self, name_or_id: str) -> Tuple[Optional[str], bool]:
        pks = self.orgs.get(name_or_id) or []
        if len(pks) > 1: return (None, True)
        if len(pks) == 1: return (pks[0], False)
        return (None, False)

    def get_existing_edge_keys(self) -> Set[str]:
        return self.existing_keys

    def get_pre_counts(self) -> Tuple[int, int]:
        return (self.node_count, self.rel_count)

def test_column_shift_prevention_with_empty_cells():
    """1. 빈 셀(<TD></TD>) 존재 시에도 열 밀림 없이 2D 좌표 보존 검증"""
    table_with_empty = """
    <TABLE>
      <TR><TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>기말 지분율</TH></TR>
      <TR><TD>홍길동</TD><TD></TD><TD>직접소유</TD><TD>10.5</TD></TR>
    </TABLE>
    """
    matrix, num_header = build_2d_table_matrix(table_with_empty)
    assert num_header == 1
    assert len(matrix) == 2
    row = matrix[1]
    assert row[0] == "홍길동"
    assert row[1] == "" # 빈 셀 보존 확인!
    assert row[2] == "직접소유" # 열이 왼쪽으로 밀리지 않고 Col 2에 정확히 위치!
    assert row[3] == "10.5" # Col 3에 정확히 위치!
    print("  ✅ [Test 1 통과] 빈 셀(<TD></TD>) 존재 시 열 밀림(Column Shift) 원천 차단 확인")

def test_true_zero_candidate_on_real_fixture():
    """2. 실 공시 표에서 독립 팩트 결측 시 True-Zero(0건) 정상 격리 검증"""
    with open(FIXTURE_PATH, "rb") as f:
        xml_bytes = f.read()
        
    provider = Fake3EntityAmbiguityManager()
    res = run_dry_run_simulation_v131(
        xml_bytes=xml_bytes,
        rcept_no="20240319000684",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_TEST_DB",
        manifest_id="TEST_TRUE_ZERO_V131"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0, "❌ 0건 후보 원칙 위반"
    assert len(manifest["planned_updates"]) == 0
    assert len(manifest["skipped_records"]) > 0
    print(f"  ✅ [Test 2 통과] 실 공시 표에서 '0건 WRITE 후보 (True-Zero)' 정상 도출 확인 (격리: {len(manifest['skipped_records'])}건)")

def test_ambiguous_master_entity_defense():
    """3. 동명이인/동일법인명 다중 매칭 시 AMBIGUOUS_MASTER_ENTITY 차단 검증"""
    dup_table_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <TR><TH>기준일: 2023년 12월 31일</TH></TR>
        <TR>
          <TH ROWSPAN="2">성명</TH>
          <TH ROWSPAN="2">관계</TH>
          <TH ROWSPAN="2">소유형태</TH>
          <TH ROWSPAN="2">주식의종류</TH>
          <TH COLSPAN="2">기말</TH>
        </TR>
        <TR><TH>주식수</TH><TH>지분율</TH></TR>
        <TR>
          <TD>김철수</TD>
          <TD>최대주주</TD>
          <TD>직접소유</TD>
          <TD>보통주 (의결권 있는 주식)</TD>
          <TD>1,000</TD>
          <TD>5.0</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = Fake3EntityAmbiguityManager()
    res = run_dry_run_simulation_v131(
        xml_bytes=dup_table_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_TEST_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0, "❌ 동명이인이 planned_creations에 유입됨!"
    
    reasons = [s.get("skip_reason") for s in manifest["skipped_records"]]
    assert "AMBIGUOUS_MASTER_ENTITY_MULTIPLE_MATCHES" in reasons, "❌ 다중 매칭 격리 사유 누락!"
    print("  ✅ [Test 3 통과] 동명이인(김철수 2명) 발견 시 AMBIGUOUS_MASTER_ENTITY 차단 완벽 입증")

def test_ownership_basis_none_leak_defense():
    """4. 소유형태 미확인 값 입력 시 None 누수 원천 차단 검증"""
    unknown_own_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <TR><TH>기준일: 2023년 12월 31일</TH></TR>
        <TR>
          <TH ROWSPAN="2">성명</TH>
          <TH ROWSPAN="2">관계</TH>
          <TH ROWSPAN="2">소유형태</TH>
          <TH ROWSPAN="2">주식의종류</TH>
          <TH COLSPAN="2">기말</TH>
        </TR>
        <TR><TH>주식수</TH><TH>지분율</TH></TR>
        <TR>
          <TD>SK스퀘어㈜</TD>
          <TD>최대주주</TD>
          <TD>불명확소유방식</TD>
          <TD>보통주 (의결권 있는 주식)</TD>
          <TD>1,000</TD>
          <TD>5.0</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = Fake3EntityAmbiguityManager()
    res = run_dry_run_simulation_v131(
        xml_bytes=unknown_own_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_TEST_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0, "❌ 불명확 소유형태가 planned_creations에 유입됨!"
    reasons = [s.get("skip_reason") for s in manifest["skipped_records"]]
    assert "UNVERIFIED_INDEPENDENT_OWNERSHIP_BASIS_NO_RELATION_CONVERSION" in reasons, "❌ 소유형태 미확인 사유 누락!"
    print("  ✅ [Test 4 통과] 불명확 소유형태(None) 누수 원천 차단 완벽 입증")

def main():
    print("="*80)
    print("🧪 [v1.3.1 순수 오프라인 단위 테스트 실행] (Zero DB Network)")
    print("="*80)
    
    test_column_shift_prevention_with_empty_cells()
    test_true_zero_candidate_on_real_fixture()
    test_ambiguous_master_entity_defense()
    test_ownership_basis_none_leak_defense()
    
    print("\n" + "="*80)
    print("🎉 [단위 테스트 100% 전수 통과] 2D 좌표 보존 및 다중 매칭 방어 완벽 검증!")
    print("="*80)

if __name__ == "__main__":
    main()
