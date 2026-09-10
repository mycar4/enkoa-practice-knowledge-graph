"""부록의 공개 Wikidata 조회 도구. 요청 실패를 후보 없음으로 처리하지 않습니다."""
import requests

API_URL = "https://www.wikidata.org/w/api.php"
HEADERS = {"User-Agent": "EntityLinkingLesson/1.0 (educational Wikidata lookup)"}


def get_json(params):
    """공개 API의 JSON을 반환하며 HTTP 또는 API 에러는 알립니다."""
    response = requests.get(API_URL, params={**params, "format": "json"},
                            headers=HEADERS, timeout=30)
    if response.status_code == 429:
        raise RuntimeError("Wikidata 요청이 몰렸습니다. 잠시 뒤 다시 실행하세요.")
    response.raise_for_status()
    result = response.json()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def search_candidates(terms):
    """이름과 별칭마다 최대 5개 후보를 찾고 Q-ID 중복을 제거합니다."""
    found = {}
    for term in terms:
        result = get_json({"action": "wbsearchentities", "search": term,
                           "language": "ko", "uselang": "ko", "limit": 5})
        for item in result["search"]:
            found[item["id"]] = item
    return found


def get_entities(ids):
    """후보들의 이름·설명·속성을 조회합니다. 빈 후보는 요청하지 않습니다."""
    if not ids:
        return {}
    return get_json({"action": "wbgetentities", "ids": "|".join(ids),
                     "props": "labels|descriptions|claims", "languages": "ko|en|mul"})["entities"]


def claim_values(entity, property_id):
    """실제 값이 있는 속성만 읽습니다. 폐기된 진술은 제외합니다."""
    values = []
    for claim in entity.get("claims", {}).get(property_id, []):
        if claim.get("rank") == "deprecated":
            continue
        value = claim["mainsnak"].get("datavalue")
        if value is not None:
            values.append(value["value"])
    return values


def text_of(entity, field):
    """한국어, 영어, 언어 공통 표기 순으로 표시할 문자열을 찾습니다."""
    for language in ["ko", "en", "mul"]:
        if language in entity.get(field, {}):
            return entity[field][language]["value"]
    return "정보 없음"


def candidate_rows(ids):
    """Q-ID를 이름·타입·설명·공식 사이트가 있는 비교 행으로 바꿉니다."""
    entities = get_entities(ids)
    type_ids = set()
    for entity in entities.values():
        for value in claim_values(entity, "P31"):
            type_ids.add(value["id"])
    type_entities = get_entities(sorted(type_ids))
    rows = []
    for qid, entity in entities.items():
        type_names = []
        for value in claim_values(entity, "P31"):
            type_names.append(text_of(type_entities[value["id"]], "labels"))
        rows.append({"qid": qid, "name": text_of(entity, "labels"),
                     "type": ", ".join(type_names) or "정보 없음",
                     "description": text_of(entity, "descriptions"),
                     "websites": claim_values(entity, "P856")})
    return rows
