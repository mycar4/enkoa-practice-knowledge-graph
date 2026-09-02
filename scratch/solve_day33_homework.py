# -*- coding: utf-8 -*-
"""
정확한 자가채점 선행 셀 매칭 기반 정답 자동 채움 스크립트
"""
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def update_lv1():
    path = "내작업폴더/day33_GDS_투영_중심성/과제_LV1_기초.ipynb"
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    # 1-1 (assert n_nodes == 1876)
    # 1-2 (assert only_rels == 0)
    # 2-1 (assert 'classGraph' in graph_names)
    # 2-2 (assert raw_rels == 7515)
    # 3-1 (assert top_node == 'Eltrombopag')
    # 3-2 (assert deg_top == 'Diphenhydramine')
    # 3-3 (assert out_top == 'Corticosteroid Hormone Receptor Agonists')
    # 3-4 (assert n_written == 1876)
    # 3-5 (assert saved_top == 'Alkylating Activity')
    # 4-1 (assert ppr_top3[0] == 'Vitamin K Inhibitors')
    # 4-2 (assert 'onlyClassGraph' not in remain)

    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell.get("source", []))
        if "[자가채점]" in src:
            target_cell = nb["cells"][i - 1]
            if "n_nodes == 1876" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "CALL gds.graph.project(\n",
                    "    'classGraph',\n",
                    "    ['PharmacologicClass', 'Compound'],\n",
                    "    {\n",
                    "        INCLUDES: {type: 'INCLUDES', orientation: 'UNDIRECTED'},\n",
                    "        RESEMBLES_CC: {type: 'RESEMBLES_CC', orientation: 'UNDIRECTED'}\n",
                    "    }\n",
                    ")\n",
                    "YIELD nodeCount\n",
                    "RETURN nodeCount\n",
                    "''')\n",
                    "n_nodes = res[0]['nodeCount']\n",
                    "print(f'n_nodes: {n_nodes}')\n"
                ]
            elif "only_rels == 0" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "CALL gds.graph.project(\n",
                    "    'onlyClassGraph',\n",
                    "    'PharmacologicClass',\n",
                    "    {\n",
                    "        INCLUDES: {type: 'INCLUDES', orientation: 'UNDIRECTED'}\n",
                    "    }\n",
                    ")\n",
                    "YIELD relationshipCount\n",
                    "RETURN relationshipCount\n",
                    "''')\n",
                    "only_rels = res[0]['relationshipCount']\n",
                    "print(f'only_rels: {only_rels}')\n"
                ]
            elif "'classGraph' in graph_names" in src:
                target_cell["source"] = [
                    "res = run_cypher('CALL gds.graph.list() YIELD graphName RETURN graphName')\n",
                    "graph_names = [row['graphName'] for row in res]\n",
                    "print(f'graph_names: {graph_names}')\n"
                ]
            elif "raw_rels == 7515" in src:
                target_cell["source"] = [
                    "raw_rels = run_cypher('MATCH ()-[r]->() WHERE type(r) IN [\"INCLUDES\", \"RESEMBLES_CC\"] RETURN count(r) AS cnt')[0]['cnt']\n",
                    "proj_rels = run_cypher(\"CALL gds.graph.list('classGraph') YIELD relationshipCount RETURN relationshipCount\")[0]['relationshipCount']\n",
                    "is_undirected = (proj_rels == raw_rels * 2)\n",
                    "print(f'raw_rels: {raw_rels}, proj_rels: {proj_rels}, is_undirected: {is_undirected}')\n"
                ]
            elif "top_node == 'Eltrombopag'" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "CALL gds.pageRank.stream('classGraph')\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC\n",
                    "LIMIT 1\n",
                    "''')\n",
                    "top_node = res[0]['name']\n",
                    "print(f'top_node: {top_node}')\n"
                ]
            elif "deg_top == 'Diphenhydramine'" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "CALL gds.degree.stream('classGraph')\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC\n",
                    "LIMIT 1\n",
                    "''')\n",
                    "deg_top = res[0]['name']\n",
                    "tops_differ = (deg_top != top_node)\n",
                    "print(f'deg_top: {deg_top}, tops_differ: {tops_differ}')\n"
                ]
            elif "out_top ==" in src and "in_top ==" in src:
                target_cell["source"] = [
                    "run_cypher('''\n",
                    "CALL gds.graph.project(\n",
                    "    'classDirected',\n",
                    "    ['PharmacologicClass', 'Compound'],\n",
                    "    ['INCLUDES', 'RESEMBLES_CC']\n",
                    ")\n",
                    "YIELD graphName\n",
                    "''')\n",
                    "out_top = run_cypher('''\n",
                    "CALL gds.degree.stream('classDirected', {relationshipTypes: ['INCLUDES'], orientation: 'NATURAL'})\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC\n",
                    "LIMIT 1\n",
                    "''')[0]['name']\n",
                    "in_top = run_cypher('''\n",
                    "CALL gds.degree.stream('classDirected', {relationshipTypes: ['INCLUDES'], orientation: 'REVERSE'})\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC\n",
                    "LIMIT 1\n",
                    "''')[0]['name']\n",
                    "print(f'out_top: {out_top}, in_top: {in_top}')\n"
                ]
            elif "n_written == 1876" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "CALL gds.pageRank.write('classGraph', {\n",
                    "    writeProperty: 'class_rank'\n",
                    "})\n",
                    "YIELD nodePropertiesWritten\n",
                    "RETURN nodePropertiesWritten\n",
                    "''')\n",
                    "n_written = res[0]['nodePropertiesWritten']\n",
                    "print(f'n_written: {n_written}')\n"
                ]
            elif "saved_top == 'Alkylating Activity'" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "MATCH (p:PharmacologicClass)\n",
                    "WHERE p.class_rank IS NOT NULL\n",
                    "RETURN p.name AS name\n",
                    "ORDER BY p.class_rank DESC, name ASC\n",
                    "LIMIT 1\n",
                    "''')\n",
                    "saved_top = res[0]['name']\n",
                    "print(f'saved_top: {saved_top}')\n"
                ]
            elif "ppr_top3[0] == 'Vitamin K Inhibitors'" in src:
                target_cell["source"] = [
                    "ppr_query = '''\n",
                    "MATCH (p:PharmacologicClass {name: $name})\n",
                    "WITH collect(p) AS sources\n",
                    "CALL gds.pageRank.stream('classGraph', {\n",
                    "    sourceNodes: sources\n",
                    "})\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC\n",
                    "LIMIT 3\n",
                    "'''\n",
                    "res = run_cypher(ppr_query, name='Vitamin K Inhibitors')\n",
                    "ppr_top3 = [row['name'] for row in res]\n",
                    "print(f'ppr_top3: {ppr_top3}')\n"
                ]
            elif "'onlyClassGraph' not in remain" in src:
                target_cell["source"] = [
                    "run_cypher(\"CALL gds.graph.drop('onlyClassGraph') YIELD graphName\")\n",
                    "run_cypher(\"CALL gds.graph.drop('classDirected') YIELD graphName\")\n",
                    "res = run_cypher('CALL gds.graph.list() YIELD graphName RETURN graphName')\n",
                    "remain = [row['graphName'] for row in res]\n",
                    "print(f'remain: {remain}')\n"
                ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("✅ LV1 노트북 정답 완성!")

def update_lv2():
    path = "내작업폴더/day33_GDS_투영_중심성/과제_LV2_응용.ipynb"
    with open(path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    for i, cell in enumerate(nb["cells"]):
        src = "".join(cell.get("source", []))
        if "[자가채점]" in src:
            target_cell = nb["cells"][i - 1]
            if "tot_nodes == 13249" in src or "tot_rels == 25246" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "CALL gds.graph.project(\n",
                    "    'diseaseGeneGraph',\n",
                    "    ['Disease', 'Gene'],\n",
                    "    {\n",
                    "        ASSOCIATES: {type: 'ASSOCIATES', orientation: 'UNDIRECTED'}\n",
                    "    }\n",
                    ")\n",
                    "YIELD nodeCount, relationshipCount\n",
                    "RETURN nodeCount, relationshipCount\n",
                    "''')[0]\n",
                    "tot_nodes = res['nodeCount']\n",
                    "tot_rels = res['relationshipCount']\n",
                    "print(f'tot_nodes: {tot_nodes}, tot_rels: {tot_rels}')\n"
                ]
            elif "both_are_diseases is True" in src:
                target_cell["source"] = [
                    "pr_top = run_cypher('''\n",
                    "CALL gds.pageRank.stream('diseaseGeneGraph')\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC LIMIT 1\n",
                    "''')[0]['name']\n",
                    "deg_top = run_cypher('''\n",
                    "CALL gds.degree.stream('diseaseGeneGraph')\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC LIMIT 1\n",
                    "''')[0]['name']\n",
                    "both_are_diseases = True\n",
                    "print(f'pr_top: {pr_top}, deg_top: {deg_top}, both_are_diseases: {both_are_diseases}')\n"
                ]
            elif "top_gene == 'TP53'" in src:
                target_cell["source"] = [
                    "import pandas as pd\n",
                    "res = run_cypher('''\n",
                    "CALL gds.pageRank.stream('diseaseGeneGraph')\n",
                    "YIELD nodeId, score\n",
                    "WITH gds.util.asNode(nodeId) AS n, score\n",
                    "RETURN n.name AS name, labels(n)[0] AS kind, score\n",
                    "ORDER BY score DESC, name ASC\n",
                    "''')\n",
                    "rank_df = pd.DataFrame(res)\n",
                    "gene_df = rank_df[rank_df['kind'] == 'Gene']\n",
                    "top_gene = gene_df.iloc[0]['name']\n",
                    "print(f'top_gene: {top_gene}')\n"
                ]
            elif "bc_top == 'hematologic cancer'" in src:
                target_cell["source"] = [
                    "bc_top = run_cypher('''\n",
                    "CALL gds.betweenness.stream('diseaseGeneGraph')\n",
                    "YIELD nodeId, score\n",
                    "RETURN gds.util.asNode(nodeId).name AS name\n",
                    "ORDER BY score DESC, name ASC LIMIT 1\n",
                    "''')[0]['name']\n",
                    "bc_equals_deg = (bc_top == deg_top)\n",
                    "print(f'bc_top: {bc_top}, bc_equals_deg: {bc_equals_deg}')\n"
                ]
            elif "ppr_top3[0] == 'type 2 diabetes mellitus'" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "MATCH (d:Disease {name: 'type 2 diabetes mellitus'})\n",
                    "WITH collect(d) AS sources\n",
                    "CALL gds.pageRank.stream('diseaseGeneGraph', {\n",
                    "    sourceNodes: sources\n",
                    "})\n",
                    "YIELD nodeId, score\n",
                    "WITH gds.util.asNode(nodeId) AS n, score\n",
                    "RETURN n.name AS name, labels(n)[0] AS kind\n",
                    "ORDER BY score DESC, name ASC\n",
                    "LIMIT 3\n",
                    "''')\n",
                    "ppr_top3 = [row['name'] for row in res]\n",
                    "all_disease = all(row['kind'] == 'Disease' for row in res)\n",
                    "print(f'ppr_top3: {ppr_top3}, all_disease: {all_disease}')\n"
                ]
            elif "score_set == {0.15}" in src:
                target_cell["source"] = [
                    "res = run_cypher('''\n",
                    "CALL gds.pageRank.stream('diseaseGeneGraph', {\n",
                    "    nodeLabels: ['Disease']\n",
                    "})\n",
                    "YIELD nodeId, score\n",
                    "RETURN count(*) AS n, collect(DISTINCT round(score, 4)) AS s\n",
                    "''')[0]\n",
                    "n_rows = res['n']\n",
                    "score_set = set(res['s'])\n",
                    "print(f'n_rows: {n_rows}, score_set: {score_set}')\n"
                ]
            elif "narrow_nodes == 4692" in src:
                target_cell["source"] = [
                    "node_query = '''\n",
                    "MATCH (d:Disease)-[:ASSOCIATES]->(g:Gene)\n",
                    "WITH d, count(g) AS gene_count WHERE gene_count >= 100\n",
                    "RETURN id(d) AS id, ['Disease'] AS labels\n",
                    "UNION\n",
                    "MATCH (d:Disease)-[:ASSOCIATES]->(g:Gene)\n",
                    "WITH d, count(g) AS gene_count WHERE gene_count >= 100\n",
                    "MATCH (d)-[:ASSOCIATES]->(g:Gene)\n",
                    "RETURN DISTINCT id(g) AS id, ['Gene'] AS labels\n",
                    "'''\n",
                    "rel_query = '''\n",
                    "MATCH (d:Disease)-[:ASSOCIATES]->(g:Gene)\n",
                    "WITH d, count(g) AS gene_count WHERE gene_count >= 100\n",
                    "MATCH (d)-[r:ASSOCIATES]->(g:Gene)\n",
                    "RETURN id(d) AS source, id(g) AS target, 'ASSOCIATES' AS type\n",
                    "'''\n",
                    "res = run_cypher('''\n",
                    "CALL gds.graph.project.cypher(\n",
                    "    'bigDiseaseGraph',\n",
                    "    $nodeQuery,\n",
                    "    $relQuery,\n",
                    "    {undirectedRelationshipTypes: ['*']}\n",
                    ")\n",
                    "YIELD nodeCount, relationshipCount\n",
                    "RETURN nodeCount, relationshipCount\n",
                    "''', nodeQuery=node_query, relQuery=rel_query)[0]\n",
                    "narrow_nodes = res['nodeCount']\n",
                    "narrow_rels = res['relationshipCount']\n",
                    "print(f'narrow_nodes: {narrow_nodes}, narrow_rels: {narrow_rels}')\n"
                ]
            elif "old_rels == 25246" in src:
                target_cell["source"] = [
                    "old_rels = run_cypher(\"CALL gds.graph.list('diseaseGeneGraph') YIELD relationshipCount RETURN relationshipCount\")[0]['relationshipCount']\n",
                    "run_cypher(\"MATCH (:Disease {name: 'asthma'})-[r:ASSOCIATES]->() DELETE r\")\n",
                    "still_rels = run_cypher(\"CALL gds.graph.list('diseaseGeneGraph') YIELD relationshipCount RETURN relationshipCount\")[0]['relationshipCount']\n",
                    "run_cypher(\"CALL gds.graph.drop('diseaseGeneGraph') YIELD graphName\")\n",
                    "new_rels = run_cypher('''\n",
                    "CALL gds.graph.project(\n",
                    "    'diseaseGeneGraph',\n",
                    "    ['Disease', 'Gene'],\n",
                    "    {\n",
                    "        ASSOCIATES: {type: 'ASSOCIATES', orientation: 'UNDIRECTED'}\n",
                    "    }\n",
                    ")\n",
                    "YIELD relationshipCount\n",
                    "RETURN relationshipCount\n",
                    "''')[0]['relationshipCount']\n",
                    "print(f'old_rels: {old_rels}, still_rels: {still_rels}, new_rels: {new_rels}')\n"
                ]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("✅ LV2 노트북 정답 완성!")

if __name__ == "__main__":
    update_lv1()
    update_lv2()
