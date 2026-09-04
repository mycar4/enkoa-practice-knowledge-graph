from neo4j import GraphDatabase
import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()
d = GraphDatabase.driver(os.getenv("AURA_URI"), auth=(os.getenv("AURA_USER"), os.getenv("AURA_PASSWORD")))
s = d.session()

rec = s.run("MATCH (c:DART_Company) RETURN keys(c) AS k, c LIMIT 1").single()
print("Keys:", rec['k'])
print("Sample Company:", dict(rec['c']))

rec2 = s.run("MATCH (c:DART_Company) WHERE c.name IS NOT NULL OR c.corp_name IS NOT NULL RETURN c.corp_code, c.name, c.corp_name, c.stock_code, c.market LIMIT 5").data()
print("Companies:", rec2)

d.close()
