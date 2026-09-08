import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv('.env')
uri = os.getenv('AURA_URI')
user = os.getenv('AURA_USER')
pwd = os.getenv('AURA_PASSWORD')
driver = GraphDatabase.driver(uri, auth=(user, pwd))
with driver.session() as s:
    res = s.run('MATCH (c:DART_Company) WHERE c.name = "삼성전자" RETURN c.name as name, c.corp_code as corp_code, c.stock_code as stock_code').data()
    print('Result:', res)
driver.close()
