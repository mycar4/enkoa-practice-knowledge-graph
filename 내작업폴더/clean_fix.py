with open('app_dart_trace_dashboard.py', 'rb') as f:
    raw = f.read()

target_broken = '인프라 연결 현'.encode('utf-8') + b'\xed\x99#'
print('Found target_broken:', target_broken in raw)

replacement = '''st.markdown("### 📊 인프라 연결 현황")
    if driver:
        node_res = run_cypher("MATCH (n) WHERE any(l in labels(n) WHERE l STARTS WITH 'DART_' OR l STARTS WITH 'RawEvidence' OR l STARTS WITH 'Evidence') RETURN count(n) AS c")
        rel_res = run_cypher("MATCH ()-[r]->() WHERE type(r) IN ['EVIDENCED_BY', 'ANNOUNCED', 'HOLDS_ECONOMIC_STAKE', 'OWNS_STAKE', 'INVESTED_IN', 'ACQUIRED_STAKE', 'REPRESENTS'] RETURN count(r) AS c")
        node_cnt = node_res[0]['c'] if node_res else 0
        rel_cnt = rel_res[0]['c'] if rel_res else 0
        st.success(f"✅ Neo4j: {node_cnt:,}개 노드 / {rel_cnt:,}건 관계")
    else:
        st.error("❌ Neo4j 데이터베이스 미연결")

# '''.encode('utf-8')

idx = raw.find(b'\xec\x9d\xb8\xed\x94\x84\xeb\x9d\xbc \xec\x97\xb0\xea\xb2\xb0 \xed\x98\x84\xed\x99#')
print('idx:', idx)
if idx != -1:
    start_idx = raw.rfind(b'st.markdown', 0, idx + 20)
    end_idx = raw.find(b'# \xf0\x9f\x8e\xa8', idx)
    print('start_idx:', start_idx, 'end_idx:', end_idx)
    new_raw = raw[:start_idx] + replacement + raw[end_idx:]
    with open('app_dart_trace_dashboard.py', 'wb') as f:
        f.write(new_raw)
    print('Replaced bytes successfully!')
    decoded = new_raw.decode('utf-8')
    print('Decoded full utf-8 successfully, length:', len(decoded))
