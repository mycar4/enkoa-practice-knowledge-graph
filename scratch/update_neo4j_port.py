# -*- coding: utf-8 -*-
from pathlib import Path

conf_path = Path(r"C:\Users\Playdata\.Neo4jDesktop2\Data\dbmss\dbms-b33bdfbf-5daa-4da3-9178-86a8faedb9d9\conf\neo4j.conf")
if conf_path.exists():
    content = conf_path.read_text(encoding="utf-8")
    if "server.bolt.listen_address=:7688" not in content:
        config_to_append = (
            "\n\n# ── Dual-Instance Port Configuration for Day_Practice ─────────\n"
            "server.bolt.listen_address=:7688\n"
            "server.bolt.advertised_address=:7688\n"
            "server.http.listen_address=:7475\n"
            "server.http.advertised_address=:7475\n"
        )
        conf_path.write_text(content + config_to_append, encoding="utf-8")
        print("✅ Day_Practice DBMS neo4j.conf 포트 7688 설정 추가 완료!")
    else:
        print("✅ 이미 포트 7688 설정이 되어 있습니다.")
else:
    print(f"❌ 설정 파일을 찾을 수 없습니다: {conf_path}")
