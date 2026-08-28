# 수도권 전철 그래프를 CSV 두 개로 적재합니다. 노트북이 이 파일을 실행해 load(run_cypher) 를 부릅니다.
# 자료 출처: OpenStreetMap contributors (ODbL). 갱신은 scripts/_build_day30_subway_data.py 로 합니다.
#
# 만드는 것
#   (:Station {name, lines})            역. lines 는 그 역을 지나는 노선 이름 **목록**(문자열 아님)
#   (:Station)-[:NEXT_TO {line, km}]->(:Station)   이웃한 두 역. 저장은 한 방향, 조회는 -[:NEXT_TO]-
#     km 은 두 역 좌표 사이의 **직선거리**다(실제 선로 길이가 아니다). OSM 에 영업거리가 없어 좌표로 계산했다.
import csv
from pathlib import Path

# 현재 파일 위치를 기준으로 data 폴더 경로를 절대 경로로 안전하게 탐색
DATA_DIR = Path(__file__).resolve().parent


def _rows(filename):
    """CSV 한 장을 dict 목록으로 읽는다."""
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load(run_cypher, chunk=60):
    """CSV 를 읽어 역과 구간을 만든다. 만든 개수를 (역, 구간) 으로 돌려준다.

    한 줄씩 보내면 왕복이 1400번이라 느리다. 그래서 CREATE 절을 chunk 개씩 한 문장으로 묶어 보낸다.
    값은 문자열에 이어 붙이지 않고 전부 $자리표시자로 넘긴다(따옴표가 든 이름이 있어도 안전하다).
    """
    stations, edges = _rows("seoul_subway_stations.csv"), _rows("seoul_subway_edges.csv")

    # 1) 역 노드. 이름과 노선 목록만 담는다(좌표는 이 단원에서 쓰지 않는다).
    #    lines 는 **목록**으로 넣는다. 문자열로 이어 붙이면 '1호선' 을 찾을 때 '인천1호선' 까지 걸린다
    #    (실측: 문자열이면 CONTAINS '1호선' 이 134역, 목록이면 '1호선' IN n.lines 가 정확히 102역)
    for i in range(0, len(stations), chunk):
        part = stations[i:i + chunk]
        clauses = ", ".join(f"(:Station {{name: $n{j}, lines: $l{j}}})" for j in range(len(part)))
        params = {}
        for j, row in enumerate(part):
            params[f"n{j}"], params[f"l{j}"] = row["name"], row["lines"].split("|")
        run_cypher("CREATE " + clauses, **params)

    # 2) 구간 관계. 양 끝 역을 이름으로 찾아 잇는다.
    #    한 문장에 MATCH 를 여러 개 쓰면 곱집합이 되므로, 짝마다 따로 찾아 잇는다
    for i in range(0, len(edges), chunk):
        part = edges[i:i + chunk]
        for j, row in enumerate(part):
            run_cypher(
                "MATCH (a:Station {name: $a}), (b:Station {name: $b}) "
                "CREATE (a)-[:NEXT_TO {line: $line, km: $km}]->(b)",
                a=row["from"], b=row["to"], line=row["line"],
                # CSV 는 전부 문자열이라 숫자로 바꿔 넣는다. 그래야 Cypher 에서 더하고 견줄 수 있다
                km=float(row["km"]) if row.get("km") else None)

    return len(stations), len(edges)
