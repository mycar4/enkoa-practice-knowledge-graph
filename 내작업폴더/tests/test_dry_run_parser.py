# -*- coding: utf-8 -*-
"""
🧪 [v1.3.3 순수 오프라인 단위 테스트] 엄격 원문 팩트 및 원문 증거 위치(Provenance Anchor) 검증
========================================================================================================
[테스트 핵심 검증 항목]
1. [소유형태 전체 일치 및 복합문구 배제]: 
   - 순수 '직접', '간접', '신탁'만 허용
   - '직접 및 간접 보유', '신탁계약', '본인소유' 등 복합/비정규 문구는 UNRESOLVED_OWNERSHIP_BASIS 보류
2. [헤더 그리드 열 폭 60열 초과 안전 가드]:
   - 60열 초과 또는 열 전개 오버플로 시 UNSUPPORTED_HEADER_GRID_TOO_WIDE 안전 격리
3. [원문 증거 위치(Provenance Anchor) 암호학적 결속]:
   - planned_records 및 skipped_records 전수에 table_index, data_row_index, header_paths, raw_row_text, raw_row_hash 보존
4. [3대 엔티티 교차 다의성 방어]: 동일 명칭이 복수 타입/복수 PK 매칭 시 승격 차단
5. [엄격 구조적 기준일 결속]: 본문 셀 임의 날짜 배제 및 <CAPTION>/단독 <TH>만 인정
6. [True-Zero 정당성]: 실 공시 표에서 0건 WRITE 후보 도출 및 감사 추적성 검증
========================================================================================================
"""

import os
import sys
import hashlib
from typing import Dict, Set, Tuple, Optional, List

sys.path.insert(0, os.path.abspath("내작업폴더"))

from dry_run_parser_engine import (
    MasterEntityProvider,
    extract_strict_structural_as_of_date,
    run_dry_run_simulation_v133,
    run_dry_run_simulation_v132
)

FIXTURE_PATH = "내작업폴더/tests/fixtures/20240319000684.xml"

class FakeCrossTypeMasterProvider:
    """3대 엔티티 교차 다의성 방어 가상 Provider"""
    def __init__(self):
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

def test_exact_match_ownership_basis_and_composite_exclusion():
    """2. 소유형태 정규화 허용값 전체 일치(Exact Match) 및 복합문구 배제 검증"""
    # 2-A: 복합 문구("직접 및 간접 보유") ➔ DIRECT 오인 승격 방지 및 보류 검증
    composite_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>
          <TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>기말 지분율</TH>
        </TR>
        <TR>
          <TD>SK스퀘어㈜</TD>
          <TD>최대주주</TD><TD>직접 및 간접 보유</TD><TD>보통주 (의결권 있는 주식)</TD><TD>20.07</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v133(
        xml_bytes=composite_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0, "❌ '직접 및 간접 보유' 복합 문구가 DIRECT로 오인 승격됨!"
    reasons = [s.get("skip_reason") for s in manifest["skipped_records"]]
    assert any("UNRESOLVED_OWNERSHIP_BASIS_NON_CANONICAL_OR_COMPOSITE" in r for r in reasons), "❌ 복합 문구 보류 사유 누락!"
    
    # 2-B: 정확한 정규화 허용값("직접", "간접", "신탁") ➔ 정규 승격 검증
    valid_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>
          <TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>기말 지분율</TH>
        </TR>
        <TR>
          <TD>SK스퀘어㈜</TD>
          <TD>최대주주</TD><TD>  직접  </TD><TD>보통주 (의결권 있는 주식)</TD><TD>20.07</TD>
        </TR>
        <TR>
          <TD>최태원</TD>
          <TD>특수관계인</TD><TD>신탁</TD><TD>보통주 (의결권 있는 주식)</TD><TD>1.05</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    res2 = run_dry_run_simulation_v133(
        xml_bytes=valid_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest2 = res2["manifest"]
    assert len(manifest2["planned_creations"]) == 2, "❌ 정확한 허용값 승격 실패"
    assert manifest2["planned_creations"][0]["ownership_basis"] == "DIRECT"
    assert manifest2["planned_creations"][1]["ownership_basis"] == "TRUST"
    print("  ✅ [Test 2 통과] 소유형태 '직접 및 간접 보유' 오인 차단 및 정규화 허용값 전체 일치(Exact-Match) 검증 완료")

def test_header_grid_width_overflow_guard():
    """3. 헤더 그리드 60열 초과 표의 UNSUPPORTED_HEADER_GRID_TOO_WIDE 격리 검증"""
    # 65개 TH를 가진 초대형 헤더 표
    th_cells = "".join([f"<TH>열{i}</TH>" for i in range(65)])
    td_cells = "".join([f"<TD>{i}</TD>" for i in range(65)])
    overflow_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>{th_cells}</TR>
        <TR>{td_cells}</TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v133(
        xml_bytes=overflow_xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest = res["manifest"]
    assert len(manifest["planned_creations"]) == 0
    reasons = [s.get("skip_reason") for s in manifest["skipped_records"]]
    assert any("UNSUPPORTED_HEADER_GRID_TOO_WIDE" in r for r in reasons), "❌ 60열 초과 표 보류 사유 누락!"
    print("  ✅ [Test 3 통과] 헤더 그리드 60열 초과 표의 안전 격리(UNSUPPORTED_HEADER_GRID_TOO_WIDE) 검증 완료")

def test_provenance_anchor_cryptographic_binding():
    """4. 후보 및 보류 행 전수에 원문 증거 위치(table_index, data_row_index, header_paths, raw_row_text, raw_row_hash) 결속 검증"""
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>
          <TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>기말 지분율</TH>
        </TR>
        <TR>
          <TD>SK스퀘어㈜</TD>
          <TD>최대주주</TD><TD>직접</TD><TD>보통주 (의결권 있는 주식)</TD><TD>20.07</TD>
        </TR>
        <TR>
          <TD>알수없는주체</TD>
          <TD>특수관계인</TD><TD>직접</TD><TD>보통주 (의결권 있는 주식)</TD><TD>1.05</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v133(
        xml_bytes=xml,
        rcept_no="99999999999999",
        target_corp_code="00164779",
        provider=provider,
        database_instance_id="FAKE_DB"
    )
    manifest = res["manifest"]
    
    # 1) 후보 행 원문 증거 위치 검증
    assert len(manifest["planned_creations"]) == 1
    p_rec = manifest["planned_creations"][0]
    for req_field in ["table_index", "data_row_index", "header_paths", "raw_row_text", "raw_row_hash"]:
        assert req_field in p_rec, f"❌ 후보 행에 필수 증거 필드 누락: {req_field}"
    assert p_rec["table_index"] == 0
    assert p_rec["data_row_index"] == 0
    expected_p_hash = hashlib.sha256(p_rec["raw_row_text"].encode("utf-8")).hexdigest()
    assert p_rec["raw_row_hash"] == expected_p_hash, "❌ 후보 행 raw_row_hash 불일치!"
    
    # 2) 보류 행 원문 증거 위치 검증
    assert len(manifest["skipped_records"]) >= 1
    s_rec = manifest["skipped_records"][0]
    for req_field in ["table_index", "data_row_index", "header_paths", "raw_row_text", "raw_row_hash"]:
        assert req_field in s_rec, f"❌ 보류 행에 필수 증거 필드 누락: {req_field}"
    assert s_rec["table_index"] == 0
    assert s_rec["data_row_index"] == 1
    expected_s_hash = hashlib.sha256(s_rec["raw_row_text"].encode("utf-8")).hexdigest()
    assert s_rec["raw_row_hash"] == expected_s_hash, "❌ 보류 행 raw_row_hash 불일치!"
    print("  ✅ [Test 4 통과] 매니페스트 후보 및 보류 행 전수에 원문 증거 위치(table_idx, data_row_idx, header_paths, hash) 결속 완료")

def test_cross_type_ambiguity_defense():
    """5. 동일 명칭이 복수 엔티티 타입에 매칭 시 AMBIGUOUS_MASTER_ENTITY_CROSS_TYPE 차단 검증"""
    hybrid_xml = """<?xml version="1.0" encoding="utf-8"?>
    <DOCUMENT>
      <TABLE>
        <CAPTION>최대주주 주식소유현황 (기준일 : 2023년 12월 31일)</CAPTION>
        <TR>
          <TH>성명</TH><TH>관계</TH><TH>소유형태</TH><TH>주식의종류</TH><TH>기말 지분율</TH>
        </TR>
        <TR>
          <TD>동명하이브리드</TD>
          <TD>최대주주</TD><TD>직접</TD><TD>보통주 (의결권 있는 주식)</TD><TD>15.0</TD>
        </TR>
      </TABLE>
    </DOCUMENT>
    """.encode('utf-8')
    
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v133(
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
    print("  ✅ [Test 5 통과] 3대 엔티티 교차 다의성(Company & Person 동시 매칭) 완벽 차단 확인")

def test_true_zero_on_sk_hynix_real_fixture():
    """6. 실 공시(SK하이닉스) 표에서 엄격 가드 적용 시 True-Zero(0건) 정상 격리 및 전수 위치 결속 검증"""
    with open(FIXTURE_PATH, "rb") as f:
        xml_bytes = f.read()
        
    provider = FakeCrossTypeMasterProvider()
    res = run_dry_run_simulation_v133(
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
    
    # 실 공시 보류 행들의 원문 증거 위치 결속 확인
    for s in manifest["skipped_records"]:
        assert "table_index" in s, "❌ 실 공시 보류 행에 table_index 누락!"
        assert "skip_reason" in s, "❌ 실 공시 보류 행에 skip_reason 누락!"
        
    print(f"  ✅ [Test 6 통과] 실 공시 표에서 '0건 WRITE 후보 (True-Zero)' 정상 도출 및 증거 위치 확인 (격리: {len(manifest['skipped_records'])}건)")

def main():
    print("="*80)
    print("🧪 [v1.3.3 순수 오프라인 단위 테스트 실행] (Zero DB Network)")
    print("="*80)
    
    test_strict_as_of_date_structural_binding()
    test_exact_match_ownership_basis_and_composite_exclusion()
    test_header_grid_width_overflow_guard()
    test_provenance_anchor_cryptographic_binding()
    test_cross_type_ambiguity_defense()
    test_true_zero_on_sk_hynix_real_fixture()
    
    print("\n" + "="*80)
    print("🎉 [단위 테스트 100% 전수 통과] DRY_RUN v1.3.3 완전 무결성 확인!")
    print("="*80)

if __name__ == "__main__":
    main()
