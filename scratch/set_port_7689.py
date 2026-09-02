# -*- coding: utf-8 -*-
from pathlib import Path

# 1. Day_Practice neo4j.conf 업데이트 (포트 7689 / HTTP 7476)
conf_path = Path(r"C:\Users\Playdata\.Neo4jDesktop2\Data\dbmss\dbms-b33bdfbf-5daa-4da3-9178-86a8faedb9d9\conf\neo4j.conf")
if conf_path.exists():
    lines = conf_path.read_text(encoding="utf-8").splitlines()
    filtered_lines = [l for l in lines if not l.startswith("server.bolt.") and not l.startswith("server.http.") and not l.startswith("# ── Dual-Instance")]
    
    config_to_append = [
        "",
        "# ── Dual-Instance Port Configuration for Day_Practice ─────────",
        "server.bolt.listen_address=:7689",
        "server.bolt.advertised_address=:7689",
        "server.http.listen_address=:7476",
        "server.http.advertised_address=:7476"
    ]
    
    conf_path.write_text("\n".join(filtered_lines + config_to_append), encoding="utf-8")
    print("✅ Day_Practice DBMS neo4j.conf를 포트 7689/7476으로 안전하게 재설정 완료!")

# 2. Day 33 실습 폴더의 .env도 7689로 동기화
env_path = Path("내작업폴더/day33_GDS_투영_중심성/.env")
env_path.write_text(
    "# ── Day 33 실습 전용 Neo4j 인스턴스 (포트 7689) ──────────────────\n"
    "NEO4J_URI=bolt://localhost:7689\n"
    "NEO4J_USER=neo4j\n"
    "NEO4J_PASSWORD=test0011\n",
    encoding="utf-8"
)
print("✅ 내작업폴더/day33_GDS_투영_중심성/.env 동기화 완료 (7689)!")
