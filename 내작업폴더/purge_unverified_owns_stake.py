import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv(".env", override=True)
uri = os.getenv("AURA_URI") or os.getenv("NEO4J_URI")
user = os.getenv("AURA_USER") or os.getenv("NEO4J_USER")
pwd = os.getenv("AURA_PASSWORD") or os.getenv("NEO4J_PASSWORD")

print("=" * 80)
print("🛡️ [DART-Trace] 프로덕션 DB 긴급 정화 및 롤백 트랜잭션 시작")
print(f"📡 접속 타겟: {uri}")
print("=" * 80)

driver = GraphDatabase.driver(uri, auth=(user, pwd))

def purge_unverified_data(tx):
    # 1. 삭제 전 상태 기록
    pre_owns = tx.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
    pre_holds = tx.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
    pre_persons = tx.run("MATCH (p:DART_Person) RETURN count(p) AS c").single()["c"]
    print(f"📊 [정화 전 실측] OWNS_STAKE: {pre_owns}건 | HOLDS_ECONOMIC_STAKE: {pre_holds}건 | DART_Person: {pre_persons}명")

    # 2. 미검증 OWNS_STAKE 삭제
    del_owns_res = tx.run("MATCH ()-[r:OWNS_STAKE]->() DELETE r RETURN count(r) AS c")
    
    # 3. 고립된 DART_Person 노드 삭제
    del_person_res = tx.run("MATCH (p:DART_Person) WHERE NOT (p)--() DELETE p RETURN count(p) AS c")

    # 4. 삭제 후 상태 감사 (Zero-Tolerance Verification)
    post_owns = tx.run("MATCH ()-[r:OWNS_STAKE]->() RETURN count(r) AS c").single()["c"]
    post_holds = tx.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]
    post_persons = tx.run("MATCH (p:DART_Person) RETURN count(p) AS c").single()["c"]

    print(f"📊 [정화 후 실측] OWNS_STAKE: {post_owns}건 | HOLDS_ECONOMIC_STAKE: {post_holds}건 | DART_Person: {post_persons}명")

    if post_owns != 0:
        raise RuntimeError(f"❌ [정화 실패] OWNS_STAKE가 아직 {post_owns}건 남아있습니다! 즉시 롤백합니다.")
    if post_holds != 19:
        raise RuntimeError(f"❌ [무결성 훼손] 정규 승격 지분 HOLDS_ECONOMIC_STAKE 수치가 19건에서 {post_holds}건으로 변동되었습니다! 즉시 롤백합니다.")
    
    print("✅ [사후 감사 통과] OWNS_STAKE = 0건 확인, HOLDS_ECONOMIC_STAKE = 19건 불변 확인!")
    return True

with driver.session() as session:
    try:
        session.execute_write(purge_unverified_data)
        print("🎉 프로덕션 DB 트랜잭션 커밋 완료: 오염 데이터 100% 완전 정화!")
    except Exception as e:
        print(f"🚨 트랜잭션 롤백 실행: {e}")
        sys.exit(1)

driver.close()
