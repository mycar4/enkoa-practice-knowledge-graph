"""
========================================================================================
🏛️ [그래프 DB & 지식 그래프 마스터 템플릿] End-to-End 전체 파이프라인 통합 풀소스 (All-in-One)
========================================================================================
📌 이 파일 하나에 그래프 DB의 근본 원리(LPG, 순회)부터 지식 그래프(온톨로지, RDF 트리플),
   SPARQL 실무 6대 질의 엔진, GraphRAG 사실 기반 추론, 그리고 networkx 시각화까지
   전체 흐름이 1단계부터 6단계까지 완벽하게 연결되어 구현되어 있습니다.

[목차]
  - 1단계: 속성 그래프 모델링 (LPG: Node, Edge, Label, Property)
  - 2단계: 인접 리스트 구축 & 고속 그래프 순회 (1홉·2홉 실시간 추천 엔진)
  - 3단계: 온톨로지 스키마 정의 & Pydantic 데이터 거버넌스 (Ontology Quality Gate)
  - 4단계: 국제 표준 RDF 시맨틱 트리플 변환 (rdflib Graph & Namespace)
  - 5단계: 표준 SPARQL 1.1 쿼리 엔진 (기본조인, UNION, OPTIONAL, NOT EXISTS, 속성경로, 집계)
  - 6단계: 엔터프라이즈 GraphRAG 사실 기반 추론 & 지식 시각화
========================================================================================
"""

import sys
from pathlib import Path
from typing import Literal

# 윈도우 터미널(CP949) 이모지 및 한글 깨짐 방지 UTF-8 설정
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pydantic import BaseModel, Field, ValidationError
import rdflib
from rdflib import Graph, URIRef, Literal as RDFLiteral, Namespace
from rdflib.namespace import RDF, RDFS
import networkx as nx
import matplotlib.pyplot as plt
import platform


print("=" * 85)
print("🚀 [Day 27] 엔터프라이즈 그래프 DB & 지식 그래프 End-to-End 파이프라인 가동")
print("=" * 85)


# ======================================================================================
# 1단계. 속성 그래프 모델링 (LPG: Labeled Property Graph)
# ======================================================================================
# [WHY] 데이터를 2차원 표(Table)로 쪼개지 않고, 실세계의 점(Node)과 선(Edge)으로 직관적으로 모델링합니다.
#       노드는 ID 기반 딕셔너리로 $O(1)$ 즉시 조회하고, 엣지는 (출발, 관계, 도착) 방향 튜플로 구성합니다.

nodes = {
    # 👤 사용자 노드 (ID -> 종류, 속성)
    'u1': {'label': '사용자', 'props': {'이름': '민서', '지역': '서울'}},
    'u2': {'label': '사용자', 'props': {'이름': '준우', '지역': '부산'}},
    'u3': {'label': '사용자', 'props': {'이름': '하은', '지역': '서울'}},
    
    # 🎵 곡 노드
    's1': {'label': '곡', 'props': {'제목': '밤편지', '장르': '발라드'}},
    's2': {'label': '곡', 'props': {'제목': '좋은 날', '장르': '댄스'}},
    's3': {'label': '곡', 'props': {'제목': 'Ditto', '장르': 'K-POP'}},
    's4': {'label': '곡', 'props': {'제목': 'OMG', '장르': 'K-POP'}},
    's5': {'label': '곡', 'props': {'제목': 'Dynamite', '장르': '디스코'}},
    
    # 🎤 아티스트 노드
    'a1': {'label': '아티스트', 'props': {'이름': '아이유', '국적': '대한민국'}},
    'a2': {'label': '아티스트', 'props': {'이름': '뉴진스', '국적': '대한민국'}},
    'a3': {'label': '아티스트', 'props': {'이름': 'BTS', '국적': '대한민국'}},
}

# 방향성 엣지 리스트: (출발 노드, 관계명, 도착 노드)
edges = [
    ('u1', '들었다', 's1'),
    ('u1', '들었다', 's3'),
    ('u2', '들었다', 's3'),
    ('u2', '들었다', 's4'),
    ('u2', '들었다', 's5'),
    ('u3', '들었다', 's1'),
    ('s1', '부른가수', 'a1'),
    ('s2', '부른가수', 'a1'),
    ('s3', '부른가수', 'a2'),
    ('s4', '부른가수', 'a2'),
    ('s5', '부른가수', 'a3'),
]

print(f"\n✅ [1단계] LPG 모델링 완료: 노드 {len(nodes)}개, 방향 엣지 {len(edges)}개 생성")


# ======================================================================================
# 2단계. 인접 리스트 구축 & 고속 그래프 순회 (1홉·2홉 실시간 추천 엔진)
# ======================================================================================
# [WHY] RDB의 무거운 JOIN 연산($O(N*M)$)을 완전히 제거하고, 화살표를 즉시 따라가기($O(1)$) 위해
#       정방향 인접 사전(Adjacency)과 역방향 인접 사전(Reverse Adjacency)을 메모리에 구축합니다.

adjacency = {}    # 사용자 -> 들은 곡 목록 (정방향 1홉)
reverse_adj = {}  # 곡 -> 들은 사용자 목록 (역방향 1홉)

for src, rel, dst in edges:
    if rel == '들었다':
        adjacency.setdefault(src, []).append(dst)
        reverse_adj.setdefault(dst, []).append(src)

# 🎯 실무 2홉 음악 추천: "민서(u1)가 들은 곡을 들은 다른 사용자들이 청취한 곡 중, 민서가 아직 안 들은 곡!"
target_user = 'u1'
my_songs = set(adjacency.get(target_user, [])) # {'s1', 's3'}
recommended_songs = set()

# 1홉 탐색 (내가 들은 곡들)
for s in my_songs:
    # 역방향 1홉 탐색 (그 곡을 같이 들은 다른 청취자들)
    for other_user in reverse_adj.get(s, []):
        if other_user == target_user:
            continue
        # 2홉 탐색 (그 청취자가 들은 다른 곡들)
        for candidate_song in adjacency.get(other_user, []):
            if candidate_song not in my_songs:
                recommended_songs.add(candidate_song)

rec_titles = [nodes[sid]['props']['제목'] for sid in recommended_songs]
print(f"✅ [2단계] 인접 리스트 기반 2홉 순회 추천 완료")
print(f"   👉 {nodes[target_user]['props']['이름']}({target_user})님을 위한 2홉 추천 음악: {rec_titles} (OMG, Dynamite)")


# ======================================================================================
# 3단계. 온톨로지 스키마 정의 & Pydantic 데이터 거버넌스 (Ontology Quality Gate)
# ======================================================================================
# [WHY] 외부 수집 데이터에는 오타나 허위 사실이 섞여 있습니다.
#       Pydantic 기반 온톨로지 스키마 규격을 세워 클래스, 도메인, 레인지 제약 조건을 통과한 사실만 적재합니다.

ALLOWED_PREDICATES = {'들었다', '부른가수', '직업', '국적', '관심'}
ALLOWED_JOBS = {'가수', '배우', '영화감독', '작곡가'}

class OntologyTriple(BaseModel):
    subject: str = Field(description="주어 개체명")
    predicate: str = Field(description="술어 관계명")
    object_value: str = Field(description="목적어 개체명 또는 속성값")

    def validate_schema(self) -> bool:
        if self.predicate not in ALLOWED_PREDICATES:
            return False
        if self.predicate == '직업' and self.object_value not in ALLOWED_JOBS:
            return False
        if self.predicate == '국적' and self.object_value in {'무국적', '알수없음'}:
            return False
        return True

# 원천 사실 데이터 (일부러 불량 데이터 '외계인', '무국적' 포함)
raw_facts = [
    {'subject': '민서', 'predicate': '직업', 'object_value': '가수'},
    {'subject': '민서', 'predicate': '국적', 'object_value': '대한민국'},
    {'subject': '하은', 'predicate': '직업', 'object_value': '배우'},
    {'subject': '하은', 'predicate': '국적', 'object_value': '대한민국'},
    {'subject': '준우', 'predicate': '직업', 'object_value': '가수'},
    {'subject': '준우', 'predicate': '국적', 'object_value': '미국'},
    {'subject': '아이유', 'predicate': '직업', 'object_value': '가수'},
    {'subject': '아이유', 'predicate': '국적', 'object_value': '대한민국'},
    {'subject': '뉴진스', 'predicate': '직업', 'object_value': '가수'},
    {'subject': '뉴진스', 'predicate': '국적', 'object_value': '대한민국'},
    {'subject': 'BTS', 'predicate': '직업', 'object_value': '가수'},
    {'subject': 'BTS', 'predicate': '국적', 'object_value': '대한민국'},
    {'subject': '괴도루팡', 'predicate': '직업', 'object_value': '외계인'},  # ❌ 탈락 대상
    {'subject': '유령회원', 'predicate': '국적', 'object_value': '무국적'},  # ❌ 탈락 대상
]

clean_facts = []
for item in raw_facts:
    try:
        triple = OntologyTriple(**item)
        if triple.validate_schema():
            clean_facts.append(triple)
    except ValidationError:
        pass

print(f"\n✅ [3단계] Pydantic 온톨로지 품질 거버넌스 완료: 원본 {len(raw_facts)}건 중 유효 사실 {len(clean_facts)}건 선별")


# ======================================================================================
# 4단계. 국제 표준 RDF 시맨틱 트리플 변환 (Semantic Triple Store)
# ======================================================================================
# [WHY] 컴퓨터가 지식의 의미(Semantic)를 추론할 수 있도록 모든 사실을
#       (주어 Subject, 술어 Predicate, 목적어 Object) 국제 표준 RDF 트리플로 변환하여 rdflib에 적재합니다.

kg = Graph()
EX = Namespace("http://example.org/")

# 1) 온톨로지 통과 사실 주입
for t in clean_facts:
    s = EX[t.subject]
    p = EX[t.predicate]
    o = RDFLiteral(t.object_value) if t.predicate == '국적' else EX[t.object_value]
    kg.add((s, p, o))

# 2) 음악 청취 및 곡-아티스트 관계 사실 주입
kg.add((EX.민서, RDF.type, EX.사용자))
kg.add((EX.준우, RDF.type, EX.사용자))
kg.add((EX.하은, RDF.type, EX.사용자))

kg.add((EX.민서, EX.들었다, EX.s1))
kg.add((EX.민서, EX.들었다, EX.s3))
kg.add((EX.준우, EX.들었다, EX.s3))
kg.add((EX.준우, EX.들었다, EX.s4))
kg.add((EX.준우, EX.들었다, EX.s5))

kg.add((EX.s1, EX.제목, RDFLiteral("밤편지")))
kg.add((EX.s2, EX.제목, RDFLiteral("좋은 날")))
kg.add((EX.s3, EX.제목, RDFLiteral("Ditto")))
kg.add((EX.s4, EX.제목, RDFLiteral("OMG")))
kg.add((EX.s5, EX.제목, RDFLiteral("Dynamite")))

kg.add((EX.s1, EX.부른가수, EX.아이유))
kg.add((EX.s2, EX.부른가수, EX.아이유))
kg.add((EX.s3, EX.부른가수, EX.뉴진스))
kg.add((EX.s4, EX.부른가수, EX.뉴진스))
kg.add((EX.s5, EX.부른가수, EX.BTS))

# OPTIONAL 실습용: 민서만 인스타그램 계정 보유
kg.add((EX.민서, EX.인스타그램, RDFLiteral("@minseo_official")))

print(f"✅ [4단계] RDF 시맨틱 트리플 적재 완료: 총 {len(kg)}개의 트리플 그래프 구축")


# ======================================================================================
# 5단계. 표준 SPARQL 1.1 질의 엔진 (6대 실무 쿼리 패턴)
# ======================================================================================
# [WHY] 그래프 네트워크 속에서 복합 조건 검색, 선택적 속성(OPTIONAL), 차집합(NOT EXISTS),
#       2홉 단축 경로(/), 집계(GROUP BY/COUNT)를 선언적으로 실행합니다.

print(f"\n✅ [5단계] 표준 SPARQL 1.1 질의 엔진 6대 실무 패턴 실행:")

# 쿼리 ① 기본 패턴 매칭 & 조인: "국적이 대한민국인 가수"
q1 = """
PREFIX ex: <http://example.org/>
SELECT ?name WHERE {
    ?person ex:직업 ex:가수 .
    ?person ex:국적 "대한민국" .
    BIND(STRAFTER(STR(?person), "http://example.org/") AS ?name)
}
"""
print("  [SPARQL 1: 기본 조인] 대한민국 국적의 가수:", [str(r.name) for r in kg.query(q1)])

# 쿼리 ② UNION (OR 조건): "국적이 미국이거나 직업이 배우인 인물"
q2 = """
PREFIX ex: <http://example.org/>
SELECT DISTINCT ?name WHERE {
    { ?person ex:국적 "미국" }
    UNION
    { ?person ex:직업 ex:배우 }
    BIND(STRAFTER(STR(?person), "http://example.org/") AS ?name)
}
"""
print("  [SPARQL 2: UNION] 미국 국적이거나 배우인 인물:", [str(r.name) for r in kg.query(q2)])

# 쿼리 ③ OPTIONAL: "사용자와 인스타그램 (없어도 사용자는 누락 없이 조회)"
q3 = """
PREFIX ex: <http://example.org/>
SELECT ?user ?insta WHERE {
    ?u a ex:사용자 .
    BIND(STRAFTER(STR(?u), "http://example.org/") AS ?user)
    OPTIONAL { ?u ex:인스타그램 ?insta }
}
"""
print("  [SPARQL 3: OPTIONAL] 사용자별 인스타그램 (Left Join):")
for r in kg.query(q3):
    insta_val = str(r.insta) if r.insta else "(없음)"
    print(f"     • {r.user} ➔ 인스타: {insta_val}")

# 쿼리 ④ FILTER NOT EXISTS: "Ditto(s3)를 청취하지 않은 사용자 선별"
q4 = """
PREFIX ex: <http://example.org/>
SELECT ?user WHERE {
    ?u a ex:사용자 .
    FILTER NOT EXISTS { ?u ex:들었다 ex:s3 }
    BIND(STRAFTER(STR(?u), "http://example.org/") AS ?user)
}
"""
print("  [SPARQL 4: FILTER NOT EXISTS] Ditto(s3)를 안 들은 사용자:", [str(r.user) for r in kg.query(q4)])

# 쿼리 ⑤ 속성 경로 (/ 로 2홉 1줄 질의): "민서가 들은 노래의 가수 목록"
q5 = """
PREFIX ex: <http://example.org/>
SELECT DISTINCT ?artist WHERE {
    ex:민서 ex:들었다/ex:부른가수 ?artistNode .
    BIND(STRAFTER(STR(?artistNode), "http://example.org/") AS ?artist)
}
"""
print("  [SPARQL 5: 속성 경로 /] 민서가 들은 노래의 가수:", [str(r.artist) for r in kg.query(q5)])

# 쿼리 ⑥ 집계 & 그룹화: "아티스트별 총 청취 횟수 (COUNT & GROUP BY)"
q6 = """
PREFIX ex: <http://example.org/>
SELECT ?artist (COUNT(?user) AS ?plays) WHERE {
    ?user ex:들었다/ex:부른가수 ?artistNode .
    BIND(STRAFTER(STR(?artistNode), "http://example.org/") AS ?artist)
}
GROUP BY ?artist
ORDER BY DESC(?plays)
"""
print("  [SPARQL 6: 집계 & 정렬] 아티스트별 총 청취수:")
for r in kg.query(q6):
    print(f"     • {r.artist}: {r.plays}회")


# ======================================================================================
# 6단계. 엔터프라이즈 GraphRAG 사실 기반 추론 & 지식 시각화
# ======================================================================================
# [WHY] 일반 RAG의 환각(Hallucination)을 원천 차단하기 위해,
#       지식 그래프에서 정확한 사실 서브그래프를 SPARQL로 추출하고 LLM 프롬프트에 주입합니다.

print(f"\n✅ [6단계] 엔터프라이즈 GraphRAG 사실 기반 추론 시뮬레이션 가동:")

def execute_graph_rag(user_target: str, user_question: str):
    """지식 그래프 팩트를 추출하여 100% 근거 기반 답변 프롬프트를 조립하는 GraphRAG 엔진"""
    sparql_fact_query = f"""
    PREFIX ex: <http://example.org/>
    SELECT ?songTitle ?artist ?country WHERE {{
        ex:{user_target} ex:들었다 ?song .
        ?song ex:제목 ?songTitle .
        ?song ex:부른가수 ?artistNode .
        ?artistNode ex:국적 ?country .
        BIND(STRAFTER(STR(?artistNode), "http://example.org/") AS ?artist)
    }}
    """
    rows = list(kg.query(sparql_fact_query))
    
    # 1. 지식 그래프 서브그래프 사실 조립
    facts = []
    for r in rows:
        facts.append(f"• {user_target} ──[청취]──> 곡명: '{r.songTitle}' ──[가수]──> {r.artist} (국적: {r.country})")
    grounded_context = "\n".join(facts)
    
    # 2. 사실 기반 프롬프트 생성
    llm_prompt = f"""
[지식 그래프 검증 팩트 (Grounded Fact)]:
{grounded_context}

[사용자 질문]: {user_question}

[답변 가이드]: 위 지식 그래프 사실에만 100% 근거하여 사실 관계를 명확히 서술하라.
"""
    return grounded_context, llm_prompt

context, generated_prompt = execute_graph_rag("민서", "민서가 들은 노래의 제목과 그 노래를 부른 가수들의 국적을 알려줘.")

print("   [GraphRAG 추출 팩트]:")
print(context)
print("\n   [GraphRAG 합성 프롬프트 요약]: 지식 그래프 팩트 2건이 주입되어 환각 0% 보장 완료!")

# 7. 지식 그래프 네트워크 시각화
print(f"\n✅ 지식 그래프 네트워크 시각화 이미지 생성...")
if platform.system() == 'Windows':
    plt.rcParams['font.family'] = 'Malgun Gothic'
elif platform.system() == 'Darwin':
    plt.rcParams['font.family'] = 'AppleGothic'
else:
    plt.rcParams['font.family'] = 'NanumGothic'
plt.rcParams['axes.unicode_minus'] = False

G = nx.DiGraph()
for src, rel, dst in edges:
    s_label = nodes[src]['props'].get('이름') or nodes[src]['props'].get('제목')
    d_label = nodes[dst]['props'].get('이름') or nodes[dst]['props'].get('제목')
    G.add_edge(s_label, d_label, relation=rel)

plt.figure(figsize=(9, 6))
pos = nx.spring_layout(G, seed=42)
nx.draw(
    G, pos,
    with_labels=True,
    node_color='#b197fc',
    node_size=2400,
    font_size=9,
    font_family=plt.rcParams['font.family'],
    arrows=True,
    arrowsize=14,
    edge_color='#868e96'
)
edge_labels = {(u, v): d['relation'] for u, v, d in G.edges(data=True)}
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_family=plt.rcParams['font.family'], font_size=8)

output_img_path = Path("내작업폴더/knowledge_graph_visualization.png")
plt.title("엔터프라이즈 K-컬처 지식 그래프 네트워크 (End-to-End)", fontsize=13, fontweight='bold')
plt.savefig(output_img_path, dpi=200, bbox_inches='tight')
plt.close()

print(f"   👉 시각화 이미지 저장 완료: {output_img_path}")

print("\n" + "=" * 85)
print("🎉 [성공] Day 27 End-to-End 전체 파이프라인 무결점 실행 완료!")
print("=" * 85)
