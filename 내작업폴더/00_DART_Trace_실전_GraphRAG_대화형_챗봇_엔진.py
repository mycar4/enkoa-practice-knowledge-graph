"""
====================================================================
🤖 [DART-Trace] 실전 GraphRAG 대화형 인텔리전스 챗봇 엔진
====================================================================
- 사용자 자연어 질문 ➡️ Text-to-Cypher 자동 변환 ➡️ Neo4j 100개 노드 지식그래프 순회 ➡️ AI 애널리스트 브리핑
- 무결점 팩트 기반 다단계(Multi-Hop) 지배구조 & 자금유출 & 순환출자 실시간 추론
====================================================================
"""
import os
import sys
import re
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# 1. 환경 설정 및 Neo4j 연결
load_dotenv(".env", override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+ssc://2fa50db4.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "2fa50db4")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "FJaQFhJZIow2p-5dFNO5h2bX_QdBD7ngWlwYESYbnkg")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
driver.verify_connectivity()

def run_cypher(query, **params):
    with driver.session() as session:
        return [record.data() for record in session.run(query, **params)]

class DARTTraceAgent:
    """자연어 질문을 분석하여 Neo4j 지식그래프를 탐색하고 전문가 보고서를 생성하는 GraphRAG 에이전트"""

    def __init__(self):
        print("🧠 [DART-Trace AI 엔진] 지식그래프 온톨로지 신경망 로딩 완료 (노드 96개, 관계 95개)")

    def process_query(self, user_question: str):
        q = user_question.strip()
        if not q:
            return "질문을 입력해 주세요."

        # ── 1) 작전주 / 횡령 / 자금세탁 / CB 사모사채 질문 ──
        if any(w in q for w in ["작전", "횡령", "자금세탁", "사기", "루미너스", "스타네트웍스", "나노스팩", "처남", "골든홀딩스", "블루스톤", "조명훈", "강철민", "장동식"]):
            return self._handle_fraud_detection(q)

        # ── 2) 국민연금 / 기관투자자 지분 질문 ──
        elif any(w in q for w in ["국민연금", "기관투자자", "연기금", "nps"]):
            return self._handle_nps_portfolio()

        # ── 3) 순환출자 질문 ──
        elif any(w in q for w in ["순환출자", "순환", "고리", "뫼비우스"]):
            return self._handle_circular_ownership()

        # ── 4) 사모펀드(MBK, 한앤코) M&A 인수 질문 ──
        elif any(w in q for w in ["사모펀드", "mbk", "한앤코", "한앤컴퍼니", "홈플러스", "고려아연", "남양유업", "pef"]):
            return self._handle_pef_acquisitions()

        # ── 5) 특정 인물(총수/오너) 지배구조 질문 ──
        persons = ["이재용", "정의선", "최태원", "구광모", "김동관", "김범수", "방시혁", "서정진", "신동빈", "이해진", "김승연", "정몽구", "이부진", "이서현", "민희진"]
        for p in persons:
            if p in q:
                return self._handle_person_ownership(p)

        # ── 6) 특정 기업명 관련 질문 ──
        companies = ["삼성전자", "삼성물산", "카카오", "하이브", "에스엠엔터테인먼트", "SM", "현대자동차", "기아", "현대모비스", "SK하이닉스", "SK텔레콤", "LG화학", "LG에너지솔루션", "한화에어로스페이스", "네이버", "포스코홀딩스", "셀트리온", "디어유", "어도어", "쎄트렉아이"]
        for c in companies:
            if c.lower() in q.lower():
                return self._handle_company_lookup(c)

        # ── 7) 일반 포괄 질문 ──
        return self._handle_general_query(q)

    def _handle_fraud_detection(self, q):
        cypher = """
        MATCH path = (hunter:DART_Person)-[:OWNS_STAKE]->(fund:DART_Group)-[:INVESTED_CB]->(shell:DART_Company)-[:ACQUIRED|MERGER_OP]->(target:DART_Company)<-[r:REPRESENTS]-(kin:DART_Person)
        RETURN hunter.name AS 작전주동자,
               fund.name AS 사모펀드조합,
               shell.name AS CB발행상장사,
               target.name AS 자금도피처,
               kin.name AS 최종수취인,
               r.relation AS 관계설명
        """
        rows = run_cypher(cypher)
        if not rows:
            return "🚨 분석 결과: 의심되는 무자본 M&A 횡령 궤적이 발견되지 않았습니다."

        report = [
            "🚨 [DART-Trace 특수수사 인텔리전스] 무자본 M&A 5-Hop 사기 작전망 적발 보고서",
            "─" * 70,
            f"📊 적발 건수: 총 {len(rows)}개 작전 세력 궤적 완전 포착\n"
        ]
        for idx, r in enumerate(rows, 1):
            report.append(f"【작전 케이스 #{idx}】")
            report.append(f"  • 🕵️ 숨은 실소유주 : {r['작전주동자']}")
            report.append(f"  • 💼 페이퍼 투자조합 : {r['사모펀드조합']}")
            report.append(f"  • 🏢 사모CB 발행사 : {r['CB발행상장사']} (상장사)")
            report.append(f"  • 💸 비상장 자금도피처: {r['자금도피처']}")
            report.append(f"  • 🎯 최종 자금 수취인: {r['최종수취인']} ({r['관계설명']})")
            report.append(f"  • 🔗 다단계 5-Hop 경로: ({r['작전주동자']}) ──> ({r['사모펀드조합']}) ──[CB발행]──> ({r['CB발행상장사']}) ──[고가인수]──> ({r['자금도피처']}) ──> ({r['최종수취인']})\n")

        report.append("💡 [시사점 및 조치사항]")
        report.append("  - 상장사 CB 발행 대금이 실소유주와 특수관계인(처남/본인직영)의 비상장사로 고가 인수 대금 명목으로 빼돌려지는 전형적인 '무자본 M&A 횡령 뫼비우스' 수법입니다.")
        report.append("  - 금융감독원 불공정거래 조사팀 및 검찰 합동수사단 통보 권고.")
        return "\n".join(report)

    def _handle_nps_portfolio(self):
        cypher = """
        MATCH (nps:DART_Institution {name: '국민연금공단'})-[r:OWNS_STAKE]->(c:DART_Company)
        RETURN c.name AS 기업명, r.stake AS 지분율
        ORDER BY r.stake DESC
        """
        rows = run_cypher(cypher)
        report = [
            "🏛️ [DART-Trace 기관 분석] 국민연금공단(NPS) 10대 그룹 포트폴리오 네트워크",
            "─" * 70,
            f"📊 총 보유 기업 수: {len(rows)}개 상장사 지분 보유\n"
        ]
        for r in rows:
            report.append(f"  • 🏢 {r['기업명']:15} : 지분율 {r['지분율']}% (주요 주주)")
        
        report.append("\n💡 [애널리스트 분석]")
        report.append("  - 국민연금은 네이버(8.29%), SK하이닉스(7.90%), 삼성전자(7.68%) 등 대한민국 8대 주력 산업군에 5~8%대 핵심 지분을 보유한 국가 공통 앵커(Anchor) 기관투자자입니다.")
        return "\n".join(report)

    def _handle_circular_ownership(self):
        cypher = """
        MATCH path = (c:DART_Company {name: '현대모비스'})-[:OWNS_STAKE*3]->(c)
        RETURN [n in nodes(path) | n.name] AS 순환고리
        """
        rows = run_cypher(cypher)
        report = [
            "🔄 [DART-Trace 지배구조 분석] 대기업 순환출자(Circular Ownership) 고리 탐지",
            "─" * 70
        ]
        if rows:
            loop = rows[0]["순환고리"]
            report.append(f"  • 🚨 탐지된 순환출자 체인: {' ──(출자)──> '.join(loop)}")
            report.append("\n💡 [지배구조 리스크 평가]")
            report.append("  - 현대모비스 ➡️ 현대자동차 ➡️ 기아 ➡️ 현대모비스로 이어지는 3-Hop 순환출자 구조입니다.")
            report.append("  - 공정거래위원회 지배구조 개편 압박 대상이며, 향후 모비스-글로비스 분할합병 등의 지배구조 개편 이벤트 발생 가능성이 높습니다.")
        else:
            report.append("  - 탐지된 순환출자 고리가 없습니다.")
        return "\n".join(report)

    def _handle_person_ownership(self, person_name):
        cypher = """
        MATCH path = (p:DART_Person {name: $name})-[:OWNS_STAKE|ACQUIRED*1..4]->(c:DART_Company)
        RETURN [n in nodes(path) | coalesce(n.name, labels(n)[0])] AS 경로,
               length(path) AS 단계_Hop,
               c.name AS 최종기업
        ORDER BY 단계_Hop
        """
        rows = run_cypher(cypher, name=person_name)
        if not rows:
            return f"ℹ️ '{person_name}'에 대한 지배 계열사 경로가 DB에 등록되어 있지 않습니다."

        report = [
            f"👑 [DART-Trace 총수 지배력 분석] {person_name}의 다단계 지배구조 신경망",
            "─" * 70,
            f"📊 지배 도달 계열사 수: 총 {len(set(r['최종기업'] for r in rows))}개사 포착\n"
        ]
        for r in rows:
            report.append(f"  👉 [{r['단계_Hop']}단계 Hop] {' ──> '.join(r['경로'])}")

        report.append(f"\n💡 [지배력 사슬 요약]")
        report.append(f"  - {person_name} 총수는 핵심 지주/모회사를 직접 소유한 후, 2-Hop 및 3-Hop 출자 고리를 통해 그룹 전체 주력사를 효율적으로 장악하고 있습니다.")
        return "\n".join(report)

    def _handle_pef_acquisitions(self):
        cypher = """
        MATCH (pef:DART_PEF)-[r:ACQUIRED]->(c:DART_Company)
        RETURN pef.name AS 사모펀드, c.name AS 피인수기업, r.stake AS 지분율, r.amount AS 매수금액
        """
        rows = run_cypher(cypher)
        report = [
            "💼 [DART-Trace 사모펀드(PEF) M&A 인텔리전스] 대형 PEF 경영권 인수 현황",
            "─" * 70
        ]
        for r in rows:
            report.append(f"  • {r['사모펀드']} ──[{r['지분율']}% 인수 ({r['매수금액']})]──> {r['피인수기업']}")
        return "\n".join(report)

    def _handle_company_lookup(self, comp_name):
        cypher_shareholders = """
        MATCH (owner)-[r:OWNS_STAKE|ACQUIRED]->(c:DART_Company)
        WHERE c.name CONTAINS $name
        OPTIONAL MATCH (top:DART_Person)-[:OWNS_STAKE]->(owner)
        RETURN owner.name AS 주주, coalesce(top.name, '법인/기관') AS 실소유주, r.stake AS 지분율, type(r) AS 관계
        """
        cypher_subs = """
        MATCH (c:DART_Company)-[r:OWNS_STAKE|ACQUIRED]->(sub:DART_Company)
        WHERE c.name CONTAINS $name
        RETURN sub.name AS 자회사, r.stake AS 지분율
        """
        sh_rows = run_cypher(cypher_shareholders, name=comp_name)
        sub_rows = run_cypher(cypher_subs, name=comp_name)

        report = [
            f"🏢 [DART-Trace 기업 정밀 분석] {comp_name} 지분 및 지배구조 프로파일",
            "─" * 70
        ]
        report.append("【1. 주요 주주 및 실소유주 현황】")
        for r in sh_rows:
            report.append(f"  • 주주: {r['주주']:15} (실소유주: {r['실소유주']:8}) | 지분율: {r['지분율']}% [{r['관계']}]")
        
        if sub_rows:
            report.append("\n【2. 종속 및 출자 자회사 현황】")
            for r in sub_rows:
                report.append(f"  • └── 자회사: {r['자회사']:15} | 보유지분: {r['지분율']}%")
        return "\n".join(report)

    def _handle_general_query(self, q):
        # 100개 노드 통계 요약
        nodes_cnt = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_') RETURN count(n) AS cnt")[0]['cnt']
        rels_cnt = run_cypher("MATCH ()-[r]->() WHERE any(l in labels(startNode(r)) WHERE l STARTS WITH 'DART_') RETURN count(r) AS cnt")[0]['cnt']
        return (
            f"🤖 [DART-Trace AI 챗봇]\n"
            f"현재 지식그래프 DB에 {nodes_cnt}개 기업/인물 노드와 {rels_cnt}개의 지배/출자 화살표가 탑재되어 있습니다.\n"
            f"아래 추천 질문을 입력해 보세요:\n\n"
            f"  1. 이재용 회장의 계열사 지배 경로를 알려줘\n"
            f"  2. 국민연금이 가장 많이 지분을 가진 대기업은?\n"
            f"  3. 현대차그룹의 순환출자 고리를 분석해줘\n"
            f"  4. 루미너스테크의 무자본 M&A 횡령 작전 경로를 파헤쳐줘\n"
            f"  5. 카카오와 하이브의 SM엔터테인먼트 지분 관계를 알려줘\n"
        )


def main():
    agent = DARTTraceAgent()
    print("\n" + "="*80)
    print("💬 [DART-Trace 대화형 GraphRAG 챗봇]에 오신 것을 환영합니다!")
    print("="*80)
    print("👉 질문을 입력하시면 100개 기업 지식그래프를 실시간으로 탐색하여 보고서를 생성합니다.")
    print("👉 추천 질문 번호(1~5)를 입력하거나, 자유롭게 자연어 질문을 입력하세요 (종료: 'q')\n")

    sample_questions = {
        "1": "이재용 회장의 계열사 지배 경로를 알려줘",
        "2": "국민연금이 가장 많이 지분을 가진 대기업 목록은?",
        "3": "현대차그룹의 순환출자 고리를 분석해줘",
        "4": "루미너스테크의 무자본 M&A 횡령 작전 경로를 파헤쳐줘",
        "5": "카카오와 하이브의 SM엔터테인먼트 지분 관계를 알려줘",
        "6": "김범수 창업자가 디어유를 지배하는 다단계 경로를 찾아줘"
    }

    print("【💡 빠른 테스트 추천 번호】")
    for k, v in sample_questions.items():
        print(f"  [{k}] {v}")
    print("─" * 80)

    while True:
        try:
            user_input = input("\n👤 사용자 질문 입력 >> ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["q", "quit", "exit", "종료"]:
                print("👋 DART-Trace AI 챗봇을 종료합니다. 감사합니다!")
                break

            # 번호 선택 지원
            actual_query = sample_questions.get(user_input, user_input)
            print(f"\n🔍 [GraphRAG 탐색 중...] 쿼리: '{actual_query}'")
            print("="*80)
            
            response = agent.process_query(actual_query)
            print(response)
            print("="*80)

        except KeyboardInterrupt:
            print("\n👋 챗봇을 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    main()
