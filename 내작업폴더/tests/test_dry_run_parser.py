# -*- coding: utf-8 -*-
"""
🧪 [v1.3.2 순수 오프라인 단위 테스트] 엄격 4대 가드 검증
========================================================================================================
[테스트 핵심 검증]
1. [True-Zero 정당성]: 실 공시 표에서 0건 WRITE 후보 및 100% 안전 격리
2. [데이터 행 병합 셀 차단]: ROWSPAN/COLSPAN이 있는 데이터 행의 UNSUPPORTED_MERGED_DATA_ROW 격리
3. [교차 타입 다의성 방어]: 동일 명칭이 복수 타입/복수 PK에 매칭 시 AMBIGUOUS_MASTER_ENTITY_CROSS_TYPE 차단
4. [소유형태 TRUST 분리]: '신탁'의 독립적 TRUST 분리 및 모호성 차단
5. [엄격 기준일 결속]: 본문 셀 임의 날짜 배제 및 <CAPTION>/1행 단독 <TH>만 인정
========================================================================================================
"""

import os
import sys
from typing import Dict, Set, Tuple, Optional, List

sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    MasterEntityProvider,
    extract_strict_structural_as_of_date,
    run_dry_run_simulation_v132
)

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"

class FakeCrossTypeMasterProvider:
    """3대 엔티티 교차 다의성 방어 가상 Provider"""
    def __init__(self):
        # name -> List of (PK, TYPE)
        self.registry: Dict[str, List[Tuple[str, str]]] = {
            "SK스퀘어㈜": [("01596425", "COMPANY")],
            "SK스퀘어": [("01596425", "COMPANY")],
            "최태원": [("PERSON_CHOI_TW_01", "PERSON")],
            "동명하이브리드": [("CORP_HYBRID_01", "COMPANY"), ("PERSON_HYBRID_02", "PERSON")], # 교차 다의성
            "김철수": [("PERSON_KIM_01", "PERSON"), ("PERSON_KIM_02", "PERSON")] # 동명이인 다의성
        }
        self.existing_keys = set()
        self.node_count = 5592
        self.rel_count = 1873

    def resolve_all_types(self, name_or_code: str) -> List[Tuple[str, str]]:
        clean = name_or_code.replace("(주)", "").replace("주식회사", "").replace("㈜", "").strip()
        matches = self.registry.get(name_or_code) or self.registry.get(clean) or []
        return matches

    def get_existing_edge_keys(self) -> Set[str]:
        return self.existing_keys

    def get_pre_counts(self) -> Tuple[int, int]:
        return (self.node_count, self.rel_count)

def test_strict_as_of_date_structural_binding():
    """1. 표 본문 텍스트 내 날짜 배제 및 엄격 <CAPTION>/1행 단독 <TH> 기준일만 인정 검증"""
    bad_table = """
    <TABLE>
      <TR><TD>주석 1: 기준일 : 2023년 12월 31일 현재 유효</TD></TR>
      <TR><TH>성명</TH><TH>지분율</TH></TR>
    </TABLE>
    """
    assert extract_strict_structural_as_of_date(bad_table) == "", "❌ 본문 셀의 날짜를 기준일로 잘못 파싱함!"
    
    good_caption_table = """
    <TABLE>
      <CAPTION>최대주주 및 특수관계인의 주식소유 현황 (기준일 : 2023년 12월 31일)</CAPTION>
      <TR><TH>성명</TH><TH>지분율</TH></TR>
    </TABLE>
    """
    assert extract_strict_structural_as_of_date(good_caption_table) == "2023-12-31", "❌ <CAPTION> 기준일 파싱 실패"
    
    good_th_table = """
    <TABLE>
      <TR><TH COLSPAN="5">최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</TH></TR>
      <TR><TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>지분율</TH></TR>
    </TABLE>
    """
    assert extract_strict_structural_as_of_date(good_th_table) == "2023-12-31", "❌ 단독 <TH> 기준일 파싱 실패"
    print("  ✅ [Test 1 통과] 표 본문 셀 날짜 배제 및 엄격 <CAPTION>/단독 <TH> 결속 검증 완료")

def test_unsupported_merged_data_row_guard():
    """2. 데이터 행에 ROWSPAN/COLSPAN 존재 시 임의 채우기 금지 및 UNSUPPORTED_MERGED_DATA_ROW 격리 검증"""
    merged_data_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>
          <TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>기말 지분율</TH>
        </TR>
        <TR>
          <TD ROWSPAN="2">SK스퀘어㈜</TD>
          <TD>최대주주</TD><TD>직접소유</TD><TD>보통주 (의결권 있는 주식)</TD><TD>20.07</TD>
        </TR>
        <TR>
          <TD>특수관계인</TD><TD>직접소유</TD><TD>보통주 (의결권 있는 주식)</TD><TD>1.05</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v132(
        xml_bytes=merged_data_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0, "❌ 병합 데이터 행이 planned_creations에 유입됨!"
    reasons = [s.get("skip_reason") for s in manifest["skipped_records"]]
    assert any("UNSUPPORTED_MERGED_DATA_ROW" in r for r in reasons), "❌ 병합 행 격리 사유 누락!"
    print("  ✅ [Test 2 통과] 데이터 행 병합 셀(ROWSPAN/COLSPAN) 임의 채우기 금지 및 안전 격리 완료")

def test_cross_type_ambiguity_defense():
    """3. 동일 명칭이 복수 엔티티 타입에 매칭 시 AMBIGUOUS_MASTER_ENTITY_CROSS_TYPE 차단 검증"""
    hybrid_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>
          <TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>기말 지분율</TH>
        </TR>
        <TR>
          <TD>동명하이브리드</TD>
          <TD>최대주주</TD><TD>직접소유</TD><TD>보통주 (의결권 있는 주식)</TD><TD>15.0</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v132(
        xml_bytes=hybrid_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0, "❌ 교차 다의성 엔티티가 planned_creations에 유입됨!"
    reasons = [s.get("skip_reason") for s in manifest["skipped_records"]]
    assert any("AMBIGUOUS_MASTER_ENTITY_CROSS_TYPE" in r for r in reasons), "❌ 교차 다의성 격리 사유 누락!"
    print("  ✅ [Test 3 통과] 3대 엔티티 교차 다의성(Company & Person 동시 매칭) 완벽 차단 확인")

def test_trust_ownership_basis_distinction():
    """4. 소유형태 '신탁'의 독립적 TRUST 분리 및 모호성 차단 검증"""
    trust_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>
          <TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>기말 지분율</TH>
        </TR>
        <TR>
          <TD>SK스퀘어㈜</TD>
          <TD>최대주주</TD><TD>신탁계약</TD><TD>보통주 (의결권 있는 주식)</TD><TD>5.0</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v132(
        xml_bytes=trust_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 1, "❌ 신탁 정규 레코드 승격 실패"
    rec = manifest["planned_creations"][0]
    assert rec["ownership_basis"] == "TRUST", f"❌ 소유형태가 TRUST가 아님: {rec['ownership_basis']}"
    assert rec["source_edge_key"] == "99999999999999_01596425_00164779_COMMON_VOTING_TRUST"
    print("  ✅ [Test 4 통과] '신탁' 소유형태의 TRUST 독립 분리 완벽 입증")

def test_true_zero_on_sk_hynix_real_fixture():
    """5. 실 공시(SK하이닉스) 표에서 엄격 가드 적용 시 True-Zero(0건) 정상 격리 검증"""
    with open(FIXTURE_PATH, "rb") as f:
        xml_bytes = f.read()
        
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v132(
        xml_bytes=xml_bytes,
        rcept_no="20240319000684",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0, "❌ 0건 후보 원칙 위반"
    assert len(manifest["planned_updates"]) == 0
    assert len(manifest["skipped_records"]) > 0
    print(f"  ✅ [Test 5 통과] 실 공시 표에서 '0건 WRITE 후보 (True-Zero)' 정상 도출 확인 (격리: {len(manifest['skipped_records'])}건)")

def main():
    print("="*80)
    print("🧪 [v1.3.2 순수 오프라인 단위 테스트 실행] (Zero DB Network)")
    print("="*80)
    
    test_strict_as_of_date_structural_binding()
    test_unsupported_merged_data_row_guard()
    test_cross_type_ambiguity_defense()
    test_trust_ownership_basis_distinction()
    test_true_zero_on_sk_hynix_real_fixture()
    
    print("\n" + "="*80)
    print("🎉 [단위 테스트 100% 전수 통과] 엄격 4대 가드 완전 무결성 확인!")
    print("="*80)

if __name__ == "__main__":
    main()
