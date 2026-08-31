from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'test0011'))

with driver.session() as s:
    q1 = """
    MATCH path = (a:DART_Company)-[:OWNS_STAKE*3]->(a)
    RETURN [n in nodes(path) | n.name] AS cycle_nodes,
           [r in relationships(path) | r.stake] AS cycle_stakes
    LIMIT 3
    """
    res1 = s.run(q1).data()
    print("Q1 (length 3):", res1)
    
    q2 = """
    MATCH (a:DART_Company {name: '현대모비스'})-[r1:OWNS_STAKE]->(b:DART_Company)-[r2:OWNS_STAKE]->(c:DART_Company)-[r3:OWNS_STAKE]->(a)
    RETURN a.name, b.name, c.name, r1.stake, r2.stake, r3.stake
    """
    res2 = s.run(q2).data()
    print("Q2 (explicit):", res2)
