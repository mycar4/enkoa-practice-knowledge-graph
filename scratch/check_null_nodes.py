# -*- coding: utf-8 -*-
import os, sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(".env", override=True)
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")))

with driver.session() as s:
    orgs = s.run("MATCH (o:DART_Organization) WHERE o.org_id IS NULL RETURN o.name AS name, labels(o) AS labels").data()
    print("org_id 누락 노드:")
    for o in orgs:
        print(f"  • {o['name']} ({o['labels']})")
        
    persons = s.run("MATCH (p:DART_Person) WHERE p.global_person_id IS NULL RETURN p.name AS name, labels(p) AS labels").data()
    print("global_person_id 누락 노드:")
    for p in persons:
        print(f"  • {p['name']} ({p['labels']})")
