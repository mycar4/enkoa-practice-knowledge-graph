import os
import re
import json
import urllib.request
from typing import Dict, Any, List, Optional
from neo4j import READ_ACCESS

def analyze_financial_graphrag(prompt: str, driver, api_key_input: str = "") -> Dict[str, Any]:
    """
    DART-Trace 원문 증거 기반 Cypher 질의 어시스턴트 (Evidence-Backed Cypher Query Assistant) (100% Evidence-Backed / Zero DB Write)
    - 허용 질의: 5% 대량보유 공시 후보, 313건 주요 자본이벤트(CB/BW/증자/합병), 2D XPath/SHA-256 원문 감사
    - 차단 질의: 실질 지배력 확정, 총수 권력 랭킹, 순환출자망 해석 (가드레일 방어)
    """
    
    # ── [1단계: 인텐트 및 엔티티 분석 (LLM / 규칙 결합)] ──
    prompt_clean = prompt.strip()
    
    # 가드레일 키워드 (지배력 단정 / 순환출자 / 권력 랭킹 질의 즉시 탐지)
    control_keywords = [
        "지배력", "실질 지배", "실질지배", "실세", "누가 지배", "누가지배",
        "순환출자", "출자고리", "권력 랭킹", "권력랭킹", "파워랭킹", "파워 랭킹",
        "지휘권", "그룹 총수", "총수 권력", "지배구조 순위"
    ]
    is_blocked_control = any(kw in prompt_clean for kw in control_keywords)
    
    detected_intent = "GENERAL"
    detected_entities = []
    target_rcept_no = None
    
    # 접수번호(14자리 숫자) 탐지
    rcp_match = re.search(r'\b(20\d{12})\b', prompt_clean)
    if rcp_match:
        target_rcept_no = rcp_match.group(1)
        detected_intent = "EVIDENCE_AUDIT"
        
    if is_blocked_control:
        detected_intent = "BLOCKED_CONTROL"
    elif target_rcept_no:
        detected_intent = "EVIDENCE_AUDIT"
    elif any(kw in prompt_clean for kw in ["XPath", "xpath", "해시", "SHA", "sha", "원문 감사", "파편", "Fragment", "fragment"]):
        detected_intent = "EVIDENCE_AUDIT"
    elif any(kw in prompt_clean for kw in ["CB", "전환사채", "BW", "신주인수권", "유상증자", "증자", "합병", "양수도", "자본이벤트", "자본 이벤트"]):
        detected_intent = "CAPITAL_EVENTS"
    elif any(kw in prompt_clean for kw in ["5%", "대량보유", "보유자", "지분율", "보고자", "주식수", "공시 후보", "추출 후보", "주주"]):
        detected_intent = "EVIDENCE_5PCT"
        
    token_usage_info = None
    llm_prompt_payload = {}
    
    # LLM을 이용한 정밀 엔티티 추출 (API Key가 제공된 경우)
    if api_key_input and api_key_input.startswith("sk-") and detected_intent != "BLOCKED_CONTROL":
        try:
            router_system_prompt = """당신은 금융감독원 DART 공시 지식그래프 엔티티 링커입니다.
사용자 질문에서 '대상 기업명', '보유자/보고자 인물명', '14자리 접수번호'를 추출하여 JSON으로 응답하세요.
반드시 JSON 형식으로만 응답해야 합니다:
{"entities": ["기업명 또는 인물명"], "rcept_no": "14자리 접수번호 또는 null", "intent_hint": "EVIDENCE_5PCT | CAPITAL_EVENTS | EVIDENCE_AUDIT | GENERAL"}
"""
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key_input}"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": router_system_prompt},
                    {"role": "user", "content": prompt_clean}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0
            }
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                res_body = json.loads(resp.read().decode("utf-8"))
                parsed_json = json.loads(res_body["choices"][0]["message"]["content"])
                if parsed_json.get("entities"):
                    detected_entities = [e.strip() for e in parsed_json["entities"] if e.strip()]
                if parsed_json.get("rcept_no"):
                    target_rcept_no = parsed_json["rcept_no"].strip()
                
                usage = res_body.get("usage", {})
                p_tok = usage.get("prompt_tokens", 0)
                c_tok = usage.get("completion_tokens", 0)
                tot_tok = usage.get("total_tokens", 0)
                cost_krw = (p_tok * 0.15 / 1000000 + c_tok * 0.60 / 1000000) * 1400
                token_usage_info = {
                    "prompt": p_tok,
                    "completion": c_tok,
                    "total": tot_tok,
                    "cost_krw": round(cost_krw, 4),
                    "task": "DART 지식그래프 엔티티 링킹"
                }
                llm_prompt_payload = {
                    "system_prompt": router_system_prompt,
                    "user_prompt_with_graph_context": prompt_clean
                }
        except Exception:
            pass

    # 규칙 기반 엔티티 백업 탐색 (Neo4j Company 매칭)
    if not detected_entities and not target_rcept_no and detected_intent != "BLOCKED_CONTROL":
        with driver.session(default_access_mode=READ_ACCESS) as session:
            # 질문 단어 중 DB 상장사명과 일치하는 항목 탐색
            words = [w.strip("?,. '\"") for w in prompt_clean.split() if len(w.strip("?,. '\"")) >= 2]
            for w in words:
                chk = session.run("MATCH (c:DART_Company) WHERE c.name = $w OR c.name CONTAINS $w RETURN c.name AS name LIMIT 1", w=w).single()
                if chk:
                    detected_entities.append(chk["name"])
                    break
            if not detected_entities:
                for w in words:
                    chk2 = session.run("MATCH (c:RawEvidenceCandidate) WHERE c.target_corp_name CONTAINS $w OR c.holder_name = $w RETURN coalesce(c.target_corp_name, c.holder_name) AS name LIMIT 1", w=w).single()
                    if chk2:
                        detected_entities.append(chk2["name"])
                        break

    # ── [2단계: 인텐트별 정밀 Cypher 쿼리 & 데이터 추출] ──
    cypher_executed = ""
    raw_data_result = {}
    raw_facts_text = ""
    
    # -------------------------------------------------------------
    # CASE A: 차단 질의 (실질 지배력 / 순환출자 / 권력 랭킹 가드레일)
    # -------------------------------------------------------------
    if detected_intent == "BLOCKED_CONTROL":
        cypher_executed = "// 🛡️ [거버넌스 가드레일] 지배력 단정 질의 차단 (Zero DB Execution)"
        raw_data_result = {
            "status": "BLOCKED_BY_GOVERNANCE_GUARD",
            "policy": "Zero OWNS_STAKE Invariant",
            "reason": "Entity Resolution & Economic Stake contract pending"
        }
        raw_facts_text = """### 🛡️ [데이터 거버넌스 가드레일 안내]

요청하신 질문은 **'실질 지배력 판정'**, **'총수 권력 랭킹'**, 또는 **'순환출자망 해석'**에 관한 내용입니다.

• **현재 데이터 계층**: 금융감독원 공시 원문에서 1차 추출된 **감사 가능한 원시 증거 후보(`RawEvidenceCandidate`: 23,996건)** 및 **증거 파편(`EvidenceFragment`: 51,551건)** 계층입니다.
• **판정 보류 사유**: `RawEvidenceCandidate`는 보고서 기재 사실의 '추출 후보'이며, `:OWNS_STAKE`는 지배력에 대한 법적·실질적 해석을 수반하므로 임의로 생성하지 않는 **Zero OWNS_STAKE Invariant(오염 0건 원칙)**을 엄격히 준수하고 있습니다.
• **차기 승격 단계**: 실질 지배력 판정은 **엔티티 해소(Entity Resolution v1.1) ➔ 경제적 지분 확정(`:HOLDS_ECONOMIC_STAKE`)** 승인 후 정식 활성화됩니다.

현재 상태에서는 **"확인 불가 (해소 대기 중)"**로 안내해 드리며, 대신 아래와 같은 **원문 사실 기반 질의**를 권장합니다:
- *"파인메딕스 관련 5% 공시에서 보고자와 지분율 후보를 보여줘"*
- *"최근 3년간 LG화학의 CB·유상증자·합병 공시를 정리해줘"*
- *"접수번호 20241231000509 공시의 원문 XPath와 SHA-256 근거를 보여줘"*
"""

    # -------------------------------------------------------------
    # CASE B: 원문 XPath 및 SHA-256 해시 감사 질의 (EVIDENCE_AUDIT)
    # -------------------------------------------------------------
    elif detected_intent == "EVIDENCE_AUDIT":
        rcp = target_rcept_no
        ent = detected_entities[0] if detected_entities else None
        
        if rcp:
            cypher_executed = """
// 🔍 [접수번호 기준 원문 증거 파편 및 2D XPath 역추적 쿼리]
MATCH (c:RawEvidenceCandidate {rcept_no: $rcp})
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
RETURN c.candidate_id AS candidate_id,
       c.rcept_no AS rcept_no,
       c.target_corp_name AS corp_name,
       c.holder_name AS holder_name,
       c.reporter_name AS reporter_name,
       c.stake_ratio AS stake_ratio,
       c.shares_count AS shares_count,
       c.xml_sha256 AS xml_sha256,
       c.xml_rel_path AS xml_rel_path,
       f.role AS role,
       f.xpath AS xpath,
       f.extracted_value AS extracted_value,
       f.raw_inner_hash AS inner_hash
LIMIT 20
            """
            with driver.session(default_access_mode=READ_ACCESS) as s:
                records = [dict(r) for r in s.run(cypher_executed, rcp=rcp)]
        elif ent:
            cypher_executed = """
// 🔍 [기업명 기준 원문 증거 파편 및 2D XPath 감사 쿼리]
MATCH (c:RawEvidenceCandidate)
WHERE c.target_corp_name CONTAINS $ent OR c.holder_name CONTAINS $ent
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
RETURN c.candidate_id AS candidate_id,
       c.rcept_no AS rcept_no,
       c.target_corp_name AS corp_name,
       c.holder_name AS holder_name,
       c.reporter_name AS reporter_name,
       c.stake_ratio AS stake_ratio,
       c.shares_count AS shares_count,
       c.xml_sha256 AS xml_sha256,
       c.xml_rel_path AS xml_rel_path,
       f.role AS role,
       f.xpath AS xpath,
       f.extracted_value AS extracted_value,
       f.raw_inner_hash AS inner_hash
LIMIT 20
            """
            with driver.session(default_access_mode=READ_ACCESS) as s:
                records = [dict(r) for r in s.run(cypher_executed, ent=ent)]
        else:
            records = []

        raw_data_result = records
        if records:
            first = records[0]
            raw_facts_text = f"### 🔍 [원문 증거 감사 리포트] 접수번호 `{first['rcept_no']}` ({first['corp_name']})\n\n"
            raw_facts_text += f"• **공시 대상 회사**: **{first['corp_name']}** (보고자: `{first.get('reporter_name') or first.get('holder_name')}`)\n"
            raw_facts_text += f"• **보고 지분율 / 주식수**: **{first.get('stake_ratio')}%** ({first.get('shares_count'):,}주)\n"
            raw_facts_text += f"• **원문 XML 무결성 해시**: `SHA-256: {first['xml_sha256']}`\n"
            raw_facts_text += f"• **로컬 원문 파일 경로**: `{first.get('xml_rel_path')}`\n"
            raw_facts_text += f"• **DART 전자공시 뷰어**: [원문 바로가기](https://dart.fss.or.kr/dsaf001/main.do?rcpNo={first['rcept_no']})\n\n"
            
            raw_facts_text += "#### 🧬 결속된 2D XPath 증거 파편 (Evidence Fragments):\n"
            seen_frags = set()
            frag_count = 0
            for r in records:
                if r.get('xpath') and r.get('xpath') not in seen_frags:
                    seen_frags.add(r['xpath'])
                    frag_count += 1
                    raw_facts_text += f"{frag_count}. **[{r.get('role', 'FRAGMENT')}]** 추출값: `\"{r.get('extracted_value')}\"`\n"
                    raw_facts_text += f"   • XPath: `{r.get('xpath')}`\n"
                    raw_facts_text += f"   • Inner Hash: `sha256:{r.get('inner_hash')[:16]}...`\n"
        else:
            raw_facts_text = f"⚠️ 접수번호 또는 기업명 관련 원문 증거 파편을 **현재 적재된 공시 데이터에서 확인 불가**합니다."

    # -------------------------------------------------------------
    # CASE C: 주요 자본 이벤트 질의 (CAPITAL_EVENTS)
    # -------------------------------------------------------------
    elif detected_intent == "CAPITAL_EVENTS":
        ent = detected_entities[0] if detected_entities else None
        
        if ent:
            cypher_executed = """
// ⚡ [기업별 주요 자본이벤트(CB·BW·증자·합병) 타임라인 쿼리]
MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
WHERE c.name CONTAINS $ent
RETURN c.name AS corp_name,
       e.event_type AS event_type,
       e.issue_amount AS issue_amount,
       e.conversion_price AS conversion_price,
       e.min_refixing_floor AS refixing_floor,
       e.issue_method AS issue_method,
       e.is_private AS is_private,
       e.decided_on AS decided_on,
       e.received_on AS received_on,
       e.effective_on AS effective_on,
       e.source_rcept_no AS rcept_no,
       e.viewer_url AS viewer_url
ORDER BY e.received_on DESC
LIMIT 10
            """
            with driver.session(default_access_mode=READ_ACCESS) as s:
                events = [dict(r) for r in s.run(cypher_executed, ent=ent)]
        else:
            cypher_executed = """
// ⚡ [전체 최신 주요 자본이벤트(CB·BW·증자·합병) 종합 쿼리]
MATCH (c:DART_Company)-[:ANNOUNCED]->(e:DART_CapitalEvent)
RETURN c.name AS corp_name,
       e.event_type AS event_type,
       e.issue_amount AS issue_amount,
       e.conversion_price AS conversion_price,
       e.min_refixing_floor AS refixing_floor,
       e.issue_method AS issue_method,
       e.is_private AS is_private,
       e.decided_on AS decided_on,
       e.received_on AS received_on,
       e.effective_on AS effective_on,
       e.source_rcept_no AS rcept_no,
       e.viewer_url AS viewer_url
ORDER BY e.received_on DESC
LIMIT 7
            """
            with driver.session(default_access_mode=READ_ACCESS) as s:
                events = [dict(r) for r in s.run(cypher_executed)]

        raw_data_result = events
        if events:
            corp_title = f"**{ent}**" if ent else "주요 상장사"
            raw_facts_text = f"### ⚡ [자본변동 공시 타임라인] {corp_title} 주요 자본이벤트 내역 (총 {len(events)}건)\n\n"
            
            type_names = {
                "CB_ISSUE": "💳 전환사채(CB) 발행",
                "BW_ISSUE": "🎫 신주인수권부사채(BW) 발행",
                "PAID": "📈 유상증자 결정",
                "MERGER": "🤝 회사합병 결정",
                "STOCK_ACQUISITION": "🏢 타법인 주식 및 출자증권 양수"
            }
            
            for ev in events:
                t_label = type_names.get(ev.get('event_type'), ev.get('event_type', '기타 공시'))
                amt_str = f"발행·양수금액: **{int(ev['issue_amount']):,}원**" if ev.get('issue_amount') else "금액: - "
                cv_str = f" / 전환·발행가액: **{int(ev['conversion_price']):,}원**" if ev.get('conversion_price') else ""
                refix_str = f" (최저리픽싱: `{int(ev['refixing_floor']):,}원`)" if ev.get('refixing_floor') else ""
                priv_str = " (사모)" if ev.get('is_private') else (" (공모)" if ev.get('is_private') is False else "")
                method_str = f" [{ev['issue_method']}]" if ev.get('issue_method') else ""
                rcp = ev.get('rcept_no', '')
                url = ev.get('viewer_url', f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}")
                
                raw_facts_text += f"• **[{ev['corp_name']}] {t_label}**{priv_str}{method_str}\n"
                raw_facts_text += f"   - {amt_str}{cv_str}{refix_str}\n"
                raw_facts_text += f"   - 공시접수일: `{str(ev.get('received_on'))}` | 결의일: `{str(ev.get('decided_on'))}` | 효력일: `{str(ev.get('effective_on'))}`\n"
                raw_facts_text += f"   - DART 원문 근거: [[접수번호 {rcp}]]({url})\n\n"
        else:
            raw_facts_text = f"⚠️ **'{ent}'** 관련 자본이벤트(CB·BW·증자·합병)는 **현재 적재된 313건 데이터에서 확인 불가**합니다."

    # -------------------------------------------------------------
    # CASE D: 5% 대량보유 공시 추출 후보 질의 (EVIDENCE_5PCT)
    # -------------------------------------------------------------
    elif detected_intent == "EVIDENCE_5PCT" or detected_entities:
        ent = detected_entities[0] if detected_entities else ""
        
        cypher_executed = """
// 📑 [5% 대량보유 공시 원시 증거 후보 및 파편 결속 쿼리]
MATCH (c:RawEvidenceCandidate)
WHERE ($ent = '' 
       OR c.target_corp_name CONTAINS $ent 
       OR c.holder_name CONTAINS $ent 
       OR c.reporter_name CONTAINS $ent)
OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(f:EvidenceFragment)
RETURN c.candidate_id AS candidate_id,
       c.rcept_no AS rcept_no,
       c.target_corp_name AS corp_name,
       c.target_corp_code AS corp_code,
       c.holder_name AS holder_name,
       c.reporter_name AS reporter_name,
       c.stake_ratio AS stake_ratio,
       c.shares_count AS shares_count,
       c.reporting_obligation_date AS obligation_date,
       c.layout_status AS layout_status,
       c.xml_sha256 AS xml_sha256,
       count(f) AS fragment_count
ORDER BY c.reporting_obligation_date DESC, c.stake_ratio DESC
LIMIT 5
        """
        with driver.session(default_access_mode=READ_ACCESS) as s:
            candidates = [dict(r) for r in s.run(cypher_executed, ent=ent)]

        raw_data_result = candidates
        if candidates:
            corp_title = f"**{ent}**" if ent else "주요 상장사"
            raw_facts_text = f"### 📑 [5% 대량보유 공시 원문 추출 후보] {corp_title} 공시 증거 내역\n\n"
            raw_facts_text += "> ℹ️ **[안내]** 본 내역은 금융감독원 공시 원문에서 1차 추출된 **감사 가능한 원시 증거 후보(`RawEvidenceCandidate`)**이며, 프로덕션 지분 확정 전 단계입니다.\n\n"
            
            for idx, cand in enumerate(candidates, 1):
                rcp = cand.get('rcept_no', '')
                holder = cand.get('holder_name') or cand.get('reporter_name', '미기재')
                stake = cand.get('stake_ratio', 0.0)
                shares = cand.get('shares_count', 0)
                ob_date = cand.get('obligation_date', '-')
                sha = cand.get('xml_sha256', '')
                frag_cnt = cand.get('fragment_count', 0)
                url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp}"
                
                raw_facts_text += f"{idx}. **[{cand['corp_name']}] 보유자: `{holder}`**\n"
                raw_facts_text += f"   • 보고 지분율: **{stake}%** ({shares:,}주)\n"
                raw_facts_text += f"   • 보고의무 발생일: `{ob_date}` | 접수번호: [[{rcp}]]({url})\n"
                raw_facts_text += f"   • 결속 증거 파편: **{frag_cnt}개 (2D XPath)** | 무결성 해시: `SHA-256: {sha[:16]}...`\n"
                raw_facts_text += f"   • 서식 지원 상태: `{cand.get('layout_status')}`\n\n"
        else:
            raw_facts_text = f"⚠️ **'{ent}'** 관련 5% 대량보유 공시 원문 증거는 **현재 적재된 15,000건 공시 데이터에서 확인 불가**합니다."

    # -------------------------------------------------------------
    # CASE E: 일반 질의 (FALLBACK)
    # -------------------------------------------------------------
    else:
        cypher_executed = "// ℹ️ 일반 질문 안내"
        raw_data_result = {"info": "일반 안내"}
        raw_facts_text = f"""🔍 **'{prompt_clean}'**에 대한 DART-Trace 지식그래프 안내:

현재 데이터베이스는 **3,988개 상장사 마스터**, **313건 주요 자본변동 공시**, **23,996건 5% 대량보유 공시 원문 증거**를 보유하고 있습니다.

질문하실 수 있는 대표 예시를 참고해 주세요:
1. **5% 대량보유 공시 증거**: *"파인메딕스 관련 5% 공시에서 보고자와 지분율 후보를 보여줘"*
2. **주요 자본변동 타임라인**: *"LG화학의 CB·BW·유상증자 공시 내역을 알려줘"*
3. **원문 XPath 및 SHA-256 감사**: *"접수번호 20241231000509 공시의 원문 XPath와 해시 근거는?"*
*(※ 특정 인물의 실질 지배력이나 순환출자 권력 판정 질의는 데이터 거버넌스 원칙상 차단됩니다.)*
"""

    return {
        "ans": raw_facts_text,
        "raw_facts_text": raw_facts_text,
        "raw_data": raw_data_result,
        "cypher": cypher_executed.strip(),
        "intent": detected_intent,
        "entities": detected_entities,
        "token_usage_info": token_usage_info,
        "prompt_payload": llm_prompt_payload
    }
