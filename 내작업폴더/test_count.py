import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv(".env")
uri = os.getenv("AURA_URI")
user = os.getenv("AURA_USER")
pwd = os.getenv("AURA_PASSWORD")
driver = GraphDatabase.driver(uri, auth=(user, pwd))
with driver.session() as s:
    kp = s.run("MATCH (c:DART_Company {market: 'KOSPI'}) WHERE c.stock_code IS NOT NULL RETURN count(c) as cnt").single()["cnt"]
    kq = s.run("MATCH (c:DART_Company {market: 'KOSDAQ'}) WHERE c.stock_code IS NOT NULL RETURN count(c) as cnt").single()["cnt"]
    print(f"✅ KOSPI: {kp}개사, KOSDAQ: {kq}개사")
driver.close()
