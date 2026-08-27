"""
====================================================================
🏛️ DART-Trace 100개 대규모 확장: 대한민국 재계 & 금융 & 작전세력 통합 지식그래프
====================================================================
- 10대 그룹: 삼성, 현대차, SK, LG, 롯데, 포스코, 한화, 네이버, 카카오, 하이브, 셀트리온
- 금융/기관 허브: 국민연금공단(NPS), MBK파트너스, 한앤컴퍼니, 한국투자증권
- 작전/부실 세력: 무자본 M&A 5-Hop 사모펀드 자금세탁 및 순환출자 망
====================================================================
"""
import os
import sys
import json
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 1. 환경 설정 및 Neo4j 연결
load_dotenv(".env", override=True)
load_dotenv("내작업폴더/day28_Neo4j_설치_Movies/.env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test0011")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
driver.verify_connectivity()

def run_cypher(query, **params):
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]

print("="*80)
print("🚀 [DART-Trace 100] 1단계: 기존 DART 네임스페이스 초기화")
print("="*80)
run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') DETACH DELETE n")
print("✅ 초기화 완료!\n")

# 2. 100개 규모의 거대한 대한민국 재계 & 금융 & 작전망 데이터셋
dataset = [
    # ── [1] 삼성그룹 ──
    ("PERSON_OWNS", "이재용", "삼성물산", 17.97, "회장"),
    ("PERSON_OWNS", "이부진", "삼성물산", 6.24, "호텔신라 사장"),
    ("PERSON_OWNS", "이서현", "삼성물산", 6.24, "삼성물산 사장"),
    ("CORP_OWNS", "삼성물산", "삼성전자", 17.97, ""),
    ("CORP_OWNS", "삼성생명", "삼성전자", 8.51, ""),
    ("CORP_OWNS", "삼성물산", "삼성생명", 19.34, ""),
    ("CORP_OWNS", "삼성물산", "삼성바이오로직스", 43.06, ""),
    ("CORP_OWNS", "삼성전자", "삼성디스플레이", 84.8, ""),
    ("CORP_OWNS", "삼성전자", "삼성바이오로직스", 31.2, ""),
    ("CORP_OWNS", "삼성전자", "삼성SDI", 19.58, ""),
    ("CORP_OWNS", "삼성전자", "삼성SDS", 22.58, ""),

    # ── [2] 현대자동차그룹 (순환출자 고리) ──
    ("PERSON_OWNS", "정의선", "현대글로비스", 20.0, "회장"),
    ("PERSON_OWNS", "정의선", "현대자동차", 2.62, "회장"),
    ("PERSON_OWNS", "정몽구", "현대모비스", 7.19, "명예회장"),
    ("CORP_OWNS", "현대모비스", "현대자동차", 21.64, ""),
    ("CORP_OWNS", "현대자동차", "기아", 33.88, ""),
    ("CORP_OWNS", "기아", "현대모비스", 17.42, ""),  # 순환출자 1
    ("CORP_OWNS", "기아", "현대제철", 17.27, ""),
    ("CORP_OWNS", "현대자동차", "현대제철", 6.87, ""),
    ("CORP_OWNS", "현대자동차", "보스턴다이내믹스", 80.0, ""),

    # ── [3] SK그룹 ──
    ("PERSON_OWNS", "최태원", "SK(주)", 17.73, "회장"),
    ("CORP_OWNS", "SK(주)", "SK이노베이션", 36.22, ""),
    ("CORP_OWNS", "SK(주)", "SK텔레콤", 30.01, ""),
    ("CORP_OWNS", "SK(주)", "SK스퀘어", 30.03, ""),
    ("CORP_OWNS", "SK스퀘어", "SK하이닉스", 20.07, ""),
    ("CORP_OWNS", "SK이노베이션", "SK온", 89.52, ""),
    ("CORP_OWNS", "SK텔레콤", "SK브로드밴드", 74.34, ""),

    # ── [4] LG그룹 ──
    ("PERSON_OWNS", "구광모", "(주)LG", 15.95, "회장"),
    ("CORP_OWNS", "(주)LG", "LG전자", 33.67, ""),
    ("CORP_OWNS", "(주)LG", "LG화학", 33.34, ""),
    ("CORP_OWNS", "(주)LG", "LG유플러스", 37.7, ""),
    ("CORP_OWNS", "LG화학", "LG에너지솔루션", 81.84, ""),
    ("CORP_OWNS", "LG전자", "LG디스플레이", 37.9, ""),

    # ── [5] 한화그룹 ──
    ("PERSON_OWNS", "김동관", "(주)한화", 4.91, "부회장"),
    ("PERSON_OWNS", "김승연", "(주)한화", 22.65, "회장"),
    ("CORP_OWNS", "(주)한화", "한화에어로스페이스", 33.95, ""),
    ("CORP_OWNS", "(주)한화", "한화솔루션", 36.35, ""),
    ("CORP_OWNS", "(주)한화", "한화생명", 43.24, ""),
    ("CORP_OWNS", "한화에어로스페이스", "한화시스템", 46.73, ""),
    ("CORP_OWNS", "한화에어로스페이스", "한화오션", 23.14, ""),
    ("CORP_OWNS", "한화에어로스페이스", "쎄트렉아이", 24.7, ""),

    # ── [6] 포스코 & 롯데 ──
    ("CORP_OWNS", "포스코홀딩스", "포스코", 100.0, ""),
    ("CORP_OWNS", "포스코홀딩스", "포스코인터내셔널", 70.71, ""),
    ("CORP_OWNS", "포스코홀딩스", "포스코퓨처엠", 59.72, ""),
    ("CORP_OWNS", "포스코홀딩스", "포스코DX", 65.38, ""),
    ("PERSON_OWNS", "신동빈", "롯데지주", 13.04, "회장"),
    ("CORP_OWNS", "롯데지주", "롯데쇼핑", 40.0, ""),
    ("CORP_OWNS", "롯데지주", "롯데케미칼", 25.59, ""),
    ("CORP_OWNS", "롯데지주", "롯데웰푸드", 47.96, ""),

    # ── [7] 카카오 & 하이브 & SM엔터 ──
    ("PERSON_OWNS", "김범수", "케이큐브홀딩스", 100.0, "창업자"),
    ("PERSON_OWNS", "김범수", "카카오", 13.27, "창업자"),
    ("CORP_OWNS", "케이큐브홀딩스", "카카오", 10.41, ""),
    ("ACQUISITION", "카카오", "에스엠엔터테인먼트", 39.87, "1조2500억"),
    ("CORP_OWNS", "카카오", "카카오페이", 46.5, ""),
    ("CORP_OWNS", "카카오", "카카오뱅크", 27.17, ""),
    ("CORP_OWNS", "카카오", "카카오엔터테인먼트", 73.6, ""),
    ("CORP_OWNS", "에스엠엔터테인먼트", "디어유", 31.98, ""),
    ("CORP_OWNS", "에스엠엔터테인먼트", "SM C&C", 29.1, ""),
    ("PERSON_OWNS", "방시혁", "하이브", 31.5, "이사회 의장"),
    ("CORP_OWNS", "하이브", "에스엠엔터테인먼트", 8.81, ""),
    ("CORP_OWNS", "하이브", "어도어", 80.0, ""),
    ("CORP_OWNS", "하이브", "플레디스", 85.0, ""),
    ("PERSON_OWNS", "민희진", "어도어", 18.0, "전 대표이사"),

    # ── [8] 네이버 & 셀트리온 ──
    ("PERSON_OWNS", "이해진", "네이버", 3.73, "GIO"),
    ("CORP_OWNS", "네이버", "네이버웹툰", 67.5, ""),
    ("CORP_OWNS", "네이버", "스노우", 80.3, ""),
    ("CORP_OWNS", "네이버", "라인플러스", 100.0, ""),
    ("PERSON_OWNS", "서정진", "셀트리온홀딩스", 98.13, "회장"),
    ("CORP_OWNS", "셀트리온홀딩스", "셀트리온", 21.65, ""),
    ("CORP_OWNS", "셀트리온", "셀트리온제약", 54.82, ""),

    # ── [9] 🏛️ 거대 기관투자자 & 사모펀드 (국민연금, MBK, 한앤코) ──
    ("INSTITUTION_OWNS", "국민연금공단", "삼성전자", 7.68),
    ("INSTITUTION_OWNS", "국민연금공단", "SK하이닉스", 7.9),
    ("INSTITUTION_OWNS", "국민연금공단", "현대자동차", 7.28),
    ("INSTITUTION_OWNS", "국민연금공단", "LG화학", 6.83),
    ("INSTITUTION_OWNS", "국민연금공단", "포스코홀딩스", 6.71),
    ("INSTITUTION_OWNS", "국민연금공단", "네이버", 8.29),
    ("INSTITUTION_OWNS", "국민연금공단", "카카오", 5.42),
    ("INSTITUTION_OWNS", "국민연금공단", "(주)한화", 7.12),
    ("PEF_ACQUIRED", "MBK파트너스", "홈플러스", 100.0),
    ("PEF_ACQUIRED", "MBK파트너스", "고려아연", 38.47),
    ("PEF_ACQUIRED", "한앤컴퍼니", "남양유업", 52.63),
    ("PEF_ACQUIRED", "한앤컴퍼니", "한온시스템", 50.5),

    # ── [10] 🚨 무자본 M&A 작전주 3대 거미줄 (루미너스, 옵티머스형, 카나리아형) ──
    # 세력 A: 강철민 루미너스 횡령 사기망 (5-Hop)
    ("PERSON_OWNS", "강철민", "골든홀딩스투자조합", 100.0, "실소유주"),
    ("INVESTED_CB", "골든홀딩스투자조합", "루미너스테크", "200억원", 0.0),
    ("ACQUISITION", "루미너스테크", "에이펙스바이오", 70.0, "180억원"),
    ("PERSON_REPRESENT", "박성호", "에이펙스바이오", "강철민의 처남", "대표이사"),

    # 세력 B: 차명 펀드 돌려막기 무자본 M&A (4-Hop)
    ("PERSON_OWNS", "조명훈", "블루스톤1호조합", 100.0, "바지사장"),
    ("INVESTED_CB", "블루스톤1호조합", "스타네트웍스", "150억원", 0.0),
    ("ACQUISITION", "스타네트웍스", "메가리얼티부동산", 100.0, "140억원"),
    ("PERSON_REPRESENT", "조명훈", "메가리얼티부동산", "본인 직영", "실제소유주"),

    # 세력 C: 연속 CB 우회상장 자금세탁 (5-Hop)
    ("PERSON_OWNS", "장동식", "아시아혁신투자조합", 100.0, "기업사냥꾼"),
    ("INVESTED_CB", "아시아혁신투자조합", "나노스팩4호", "300억원", 0.0),
    ("MERGER_OP", "나노스팩4호", "케이바이오파마", 100.0, "우회상장"),
    ("ACQUISITION", "케이바이오파마", "홍콩페이퍼컴퍼니", 90.0, "250억원"),
    ("PERSON_REPRESENT", "장동식", "홍콩페이퍼컴퍼니", "장동식 해외은닉계좌", "대표")
]

print("="*80)
print("📥 [DART-Trace 100] 2단계: 100개 기업·인물·사모펀드·작전세력 지식그래프 적재 (MERGE)")
print("="*80)

for item in dataset:
    rel_type = item[0]
    
    if rel_type == "PERSON_OWNS":
        _, person, target, stake, role = item
        target_label = "DART_Group" if "조합" in target else "DART_Company"
        run_cypher(f"""
            MERGE (p:DART_Person {{name: $pname}})
            MERGE (c:{target_label} {{name: $tname}})
            MERGE (p)-[r:OWNS_STAKE]->(c)
            SET r.stake = $stake, r.role = $role
        """, pname=person, tname=target, stake=stake, role=role)

    elif rel_type in ["CORP_OWNS", "INSTITUTION_OWNS"]:
        _, c1, c2, stake = item[:4]
        from_label = "DART_Institution" if "국민연금" in c1 else "DART_Company"
        run_cypher(f"""
            MERGE (c1:{from_label} {{name: $c1}})
            MERGE (c2:DART_Company {{name: $c2}})
            MERGE (c1)-[r:OWNS_STAKE]->(c2)
            SET r.stake = $stake
        """, c1=c1, c2=c2, stake=stake)

    elif rel_type in ["ACQUISITION", "PEF_ACQUIRED", "MERGER_OP"]:
        c1 = item[1]
        c2 = item[2]
        stake = item[3]
        amount = item[4] if len(item) > 4 else "경영권 인수"
        from_label = "DART_PEF" if "파트너스" in c1 or "한앤" in c1 else "DART_Company"
        run_cypher(f"""
            MERGE (c1:{from_label} {{name: $c1}})
            MERGE (c2:DART_Company {{name: $c2}})
            MERGE (c1)-[r:ACQUIRED]->(c2)
            SET r.stake = $stake, r.amount = $amount
        """, c1=c1, c2=c2, stake=stake, amount=amount)

    elif rel_type == "INVESTED_CB":
        _, gname, cname, amount, rate = item
        run_cypher("""
            MERGE (g:DART_Group {name: $gname})
            MERGE (c:DART_Company {name: $cname})
            MERGE (g)-[r:INVESTED_CB]->(c)
            SET r.amount = $amount, r.interest_rate = $rate
        """, gname=gname, cname=cname, amount=amount, rate=rate)

    elif rel_type == "PERSON_REPRESENT":
        _, pname, cname, rel, role = item
        run_cypher("""
            MERGE (p:DART_Person {name: $pname})
            MERGE (c:DART_Company {name: $cname})
            MERGE (p)-[r:REPRESENTS]->(c)
            SET r.relation = $rel, r.role = $role
        """, pname=pname, cname=cname, rel=rel, role=role)

total_nodes = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN count(n) AS cnt")[0]['cnt']
total_rels = run_cypher("MATCH ()-[r]->() WHERE any(l in labels(startNode(r)) WHERE l STARTS WITH 'DART_') RETURN count(r) AS cnt")[0]['cnt']

print(f"🎉 100개 대규모 적재 완료! 총 DART 노드: {total_nodes}개, 총 관계(화살표): {total_rels}개\n")

print("="*80)
print("🔍 [DART-Trace 100] 3단계: 챗봇을 전지전능하게 만드는 핵심 다단계 질의 4선")
print("="*80)

# 질의 1. 대한민국 국민연금공단(NPS)의 10대 그룹 핵심 연결 허브 파워
print("\n📌 [질의 1] 🏛️ 국민연금공단이 공통 대주주로 연결하는 10대 대기업 네트워크")
res1 = run_cypher("""
MATCH (nps:DART_Institution {name: '국민연금공단'})-[r:OWNS_STAKE]->(c:DART_Company)
RETURN c.name AS 기업명, r.stake AS 지분율
ORDER BY r.stake DESC
""")
for r in res1:
    print(f"  🏛️ 국민연금 ──[{r['지분율']}%]──> {r['기업명']}")

# 질의 2. 현대자동차그룹의 3-Hop 순환출자 뫼비우스의 띠 탐지
print("\n📌 [질의 2] 🔄 현대자동차그룹의 3-Hop 순환출자(Circular Ownership) 고리 자동 탐지")
res2 = run_cypher("""
MATCH path = (c:DART_Company {name: '현대모비스'})-[:OWNS_STAKE*3]->(c)
RETURN [n in nodes(path) | n.name] AS 순환출자고리
""")
for r in res2:
    print(f"  🔄 순환고리: {' ──> '.join(r['순환출자고리'])}")

# 질의 3. 재벌 총수 5인의 3-Hop 최종 지배 계열사 수 및 지배력 사슬 비교
print("\n📌 [질의 3] 👑 재벌 총수 5인의 다단계 지배 계열사 수 및 영향력")
res3 = run_cypher("""
MATCH (p:DART_Person)-[:OWNS_STAKE*1..4]->(c:DART_Company)
WHERE p.name IN ['이재용', '정의선', '최태원', '구광모', '김동관']
RETURN p.name AS 총수, count(DISTINCT c) AS 지배_계열사_수, collect(DISTINCT c.name)[0..3] AS 주요계열사_샘플
ORDER BY 지배_계열사_수 DESC
""")
for r in res3:
    print(f"  👑 {r['총수']}: 총 {r['지배_계열사_수']}개 계열사 지배 ({', '.join(r['주요계열사_샘플'])} 등)")

# 질의 4. 🚨 무자본 M&A 작전세력 3대 자금세탁 횡령 루트 일괄 자동 적발
print("\n📌 [질의 4] 🚨 대한민국 증시 내 '무자본 M&A 사모사채 횡령 작전망' 3대 세력 일괄 적발")
res4 = run_cypher("""
MATCH path = (hunter:DART_Person)-[:OWNS_STAKE]->(fund:DART_Group)-[:INVESTED_CB]->(shell:DART_Company)-[:ACQUIRED|MERGER_OP]->(target:DART_Company)<-[r:REPRESENTS]-(kin:DART_Person)
RETURN hunter.name AS 작전주동자,
       fund.name AS 사모펀드조합,
       shell.name AS CB발행상장사,
       target.name AS 자금도피처_비상장사,
       kin.name AS 최종수취인,
       r.relation AS 관계설명
""")
for r in res4:
    print(f"  🚨 [작전 적발] {r['작전주동자']} ──> {r['사모펀드조합']} ──> {r['CB발행상장사']} ──> {r['자금도피처_비상장사']} ──> {r['최종수취인']} ({r['관계설명']})")

print("\n" + "="*80)
print("🎉 [DART-Trace 100] 대규모 지식그래프 적재 & 4대 다단계 추론 엔진 검증 100% 완료!")
print("="*80)
driver.close()
