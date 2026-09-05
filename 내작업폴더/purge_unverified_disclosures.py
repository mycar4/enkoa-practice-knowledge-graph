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
print("🛡️ [DART-Trace] 2차 긴급 정화: 미검증 DART_Disclosure(30,527건) 및 신규 CB(19건) 롤백 트랜잭션")
print(f"📡 접속 타겟: {uri}")
print("=" * 80)

driver = GraphDatabase.driver(uri, auth=(user, pwd))

def purge_unverified_disclosures_and_cbs(tx):
    # 1. 삭제 전 상태 기록
    pre_disc = tx.run("MATCH (d:DART_Disclosure) RETURN count(d) AS c").single()["c"]
    pre_filed = tx.run("MATCH ()-[r:FILED]->() RETURN count(r) AS c").single()["c"]
    pre_cb_total = tx.run("MATCH (e:DART_CapitalEvent) RETURN count(e) AS c").single()["c"]
    pre_cb_new = tx.run("MATCH (e:DART_CapitalEvent) WHERE e.event_id STARTS WITH 'CB_' RETURN count(e) AS c").single()["c"]
    pre_cb_valid = tx.run("MATCH (e:DART_CapitalEvent) WHERE e.embedding_512 IS NOT NULL RETURN count(e) AS c").single()["c"]
    
    print(f"📊 [정화 전 실측]")
    print(f"  • DART_Disclosure: {pre_disc:,}건 / FILED 관계: {pre_filed:,}건")
    print(f"  • DART_CapitalEvent 전체: {pre_cb_total:,}건 (정상 임베딩 보유: {pre_cb_valid:,}건, 미검증 신규: {pre_cb_new:,}건)")

    # 2. 미검증 DART_Disclosure 및 FILED 관계 전량 삭제
    tx.run("MATCH (d:DART_Disclosure) DETACH DELETE d")

    # 3. 미검증 신규 19건 DART_CapitalEvent 및 연결된 ANNOUNCED 관계 삭제
    tx.run("MATCH (e:DART_CapitalEvent) WHERE e.event_id STARTS WITH 'CB_' DETACH DELETE e")

    # 4. 사후 감사 (Zero-Tolerance Verification)
    post_disc = tx.run("MATCH (d:DART_Disclosure) RETURN count(d) AS c").single()["c"]
    post_filed = tx.run("MATCH ()-[r:FILED]->() RETURN count(r) AS c").single()["c"]
    post_cb_total = tx.run("MATCH (e:DART_CapitalEvent) RETURN count(e) AS c").single()["c"]
    post_cb_valid = tx.run("MATCH (e:DART_CapitalEvent) WHERE e.embedding_512 IS NOT NULL RETURN count(e) AS c").single()["c"]
    post_holds = tx.run("MATCH ()-[r:HOLDS_ECONOMIC_STAKE]->() RETURN count(r) AS c").single()["c"]

    print(f"\n📊 [정화 후 실측]")
    print(f"  • DART_Disclosure: {post_disc:,}건 / FILED 관계: {post_filed:,}건")
    print(f"  • DART_CapitalEvent: {post_cb_total:,}건 (기존 정상 데이터 100% 보존)")
    print(f"  • HOLDS_ECONOMIC_STAKE: {post_holds:,}건 (불변)")

    if post_disc != 0 or post_filed != 0:
        raise RuntimeError(f"❌ [감사 실패] DART_Disclosure 또는 FILED가 아직 남아있습니다! 롤백합니다.")
    if post_cb_total != 313 or post_cb_valid != 313:
        raise RuntimeError(f"❌ [감사 실패] 기존 정상 자본이벤트(313건)가 훼손되었습니다 (현재: {post_cb_total}건)! 즉시 롤백합니다.")
    if post_holds != 19:
        raise RuntimeError(f"❌ [감사 실패] HOLDS_ECONOMIC_STAKE 수치가 19건에서 {post_holds}건으로 변동되었습니다! 즉시 롤백합니다.")

    print("\n✅ [사후 감사 100% 통과] 미검증 데이터 완벽 롤백, 기존 313건 벡터 인덱싱 정상 이벤트 온전히 복원!")
    return True

with driver.session() as session:
    try:
        session.execute_write(purge_unverified_disclosures_and_cbs)
        print("🎉 프로덕션 DB 2차 정화 트랜잭션 안전 커밋 완료!")
    except Exception as e:
        print(f"🚨 트랜잭션 롤백 실행: {e}")
        sys.exit(1)

driver.close()
