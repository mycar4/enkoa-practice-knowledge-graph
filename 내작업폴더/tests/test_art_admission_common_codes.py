# -*- coding: utf-8 -*-
"""
[공통코드 관리 화면 회귀 테스트] - 2026-09-24 신규 기능

왜 이 파일이 필요한가:
  계열태그(department_tag) 10개가 파이썬 튜플로 하드코딩돼 있어서 태그 하나
  추가/변경에도 배포가 필요했다. Neo4j(:CommonCode)로 옮겨 배포 없이 관리
  화면(fo/admin-common-codes.html)에서 CRUD 가능하게 했다.

  이 전환에서 반드시 지켜야 할 것:
  1) 기존 list_standard_department_tags()/set_department_tag()의 동작이
     (호출부 입장에서) 전혀 안 바뀌어야 한다 - 이 둘을 쓰는 KG 뷰어/profile.html
     "계열로 찾기" 등 기존 기능이 조용히 깨지면 안 된다.
  2) 실제 학과에 이미 붙어 사용 중인 태그는 삭제가 막혀야 한다 - 안 그러면
     운영 데이터의 분류가 고아 참조로 깨진다.

  테스트는 실제 프로덕션과 같은 Neo4j Aura 인스턴스에 붙는다(이 프로젝트의
  다른 테스트와 동일한 방식) - 별도 격리된 카테고리(_TEST_CATEGORY)를 써서
  실제 department_tag 데이터를 건드리지 않고, 테스트 종료 시 스스로 정리한다.
"""
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.art_admission_service import ArtAdmissionService  # noqa: E402

_SERVICE = None
_TEST_CATEGORY = "_test_regression_category"


def _svc() -> ArtAdmissionService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = ArtAdmissionService()
    return _SERVICE


def _cleanup_test_category():
    svc = _svc()
    for c in svc.list_common_codes(_TEST_CATEGORY):
        svc.delete_common_code(_TEST_CATEGORY, c["code"])


def test_common_code_crud_roundtrip():
    """생성 -> 중복생성 거부 -> 수정 -> 존재하지 않는 코드 수정 거부 -> 삭제
    -> 삭제 후 목록에서 사라짐, 전 과정이 실제로 동작해야 한다."""
    svc = _svc()
    _cleanup_test_category()
    try:
        created = svc.create_common_code(_TEST_CATEGORY, "foo", "Foo Label")
        assert created["code"] == "foo" and created["label"] == "Foo Label" and created["active"] is True

        codes = {c["code"]: c for c in svc.list_common_codes(_TEST_CATEGORY)}
        assert "foo" in codes, "생성한 코드가 목록 조회에 안 보입니다"

        try:
            svc.create_common_code(_TEST_CATEGORY, "foo", "중복")
            assert False, "중복 코드 생성이 거부되지 않았습니다"
        except ValueError:
            pass

        updated = svc.update_common_code(_TEST_CATEGORY, "foo", label="Foo Updated", sort_order=5, active=False)
        assert updated["label"] == "Foo Updated" and updated["sort_order"] == 5 and updated["active"] is False

        try:
            svc.update_common_code(_TEST_CATEGORY, "존재안함", label="x")
            assert False, "존재하지 않는 코드 수정이 거부되지 않았습니다"
        except ValueError:
            pass

        svc.delete_common_code(_TEST_CATEGORY, "foo")
        codes_after = {c["code"] for c in svc.list_common_codes(_TEST_CATEGORY)}
        assert "foo" not in codes_after, "삭제한 코드가 여전히 목록에 남아있습니다"

        try:
            svc.delete_common_code(_TEST_CATEGORY, "foo")
            assert False, "이미 삭제된 코드를 다시 삭제해도 에러가 안 났습니다"
        except ValueError:
            pass
    finally:
        _cleanup_test_category()


def test_department_tag_delete_blocked_when_in_use():
    """실제로 학과에 붙어 사용 중인 계열태그는 삭제가 거부돼야 한다(고아 참조 방지).

    회귀 대상: department_tag 카테고리에만 걸리는 "사용 중이면 삭제 거부" 로직이
    빠지면, 관리 화면에서 실수로 태그를 지웠을 때 이미 그 태그가 붙은 학과들의
    standard_tag 값이 코드 목록에 없는 고아 값으로 남는다.
    """
    svc = _svc()
    existing_tags = svc.list_common_codes("department_tag")
    assert existing_tags, "테스트 전제 실패: department_tag가 시드되어 있지 않습니다(seed_common_codes_if_empty 먼저 실행 필요)"
    in_use_tag = existing_tags[0]["code"]
    try:
        svc.delete_common_code("department_tag", in_use_tag)
        assert False, f"사용 중인 태그 '{in_use_tag}' 삭제가 차단되지 않았습니다"
    except ValueError as e:
        assert "사용 중" in str(e), f"삭제 거부 사유가 예상과 다릅니다: {e}"
    # 실제로 삭제 시도했으니 여전히 목록에 남아있는지(부작용 없음) 확인
    after = {c["code"] for c in svc.list_common_codes("department_tag")}
    assert in_use_tag in after, "차단됐어야 할 삭제가 실제로는 일부 반영됐습니다"


def test_list_standard_department_tags_matches_common_code_list():
    """기존 list_standard_department_tags()가 새 CommonCode 저장소를 정확히
    반영해야 한다 - 이 함수를 쓰는 기존 화면(profile.html 계열로 찾기, kg.html
    태그 필터)이 전환 후에도 동일하게 동작해야 하므로."""
    svc = _svc()
    from_legacy_fn = svc.list_standard_department_tags()
    from_common_code = [c["code"] for c in svc.list_common_codes("department_tag") if c.get("active") is not False]
    assert from_legacy_fn == from_common_code, (
        f"list_standard_department_tags()가 CommonCode 저장소와 어긋납니다: "
        f"{from_legacy_fn} vs {from_common_code}"
    )


if __name__ == "__main__":
    for fn in (
        test_common_code_crud_roundtrip,
        test_department_tag_delete_blocked_when_in_use,
        test_list_standard_department_tags_matches_common_code_list,
    ):
        fn()
        print(f"PASS: {fn.__name__}")
    print("\n공통코드 관리 회귀 테스트 전체 통과")
