import os
import subprocess
import time
import sys

java_home = r"C:\Users\Playdata\.Neo4jDesktop2\Cache\runtime\zulu21.50.19-ca-jre21.0.11-win_x64"
bat_path = r"C:\Users\Playdata\.Neo4jDesktop2\Data\dbmss\dbms-f6479556-481c-4e3f-9f9f-67db19b50c32\bin\neo4j.bat"

env = os.environ.copy()
env["JAVA_HOME"] = java_home
env["PATH"] = f"{java_home}\\bin;{env.get('PATH', '')}"
env["NEO4J_ACCEPT_LICENSE_AGREEMENT"] = "yes"

# Clear store_lock
lock_file = r"C:\Users\Playdata\.Neo4jDesktop2\Data\dbmss\dbms-f6479556-481c-4e3f-9f9f-67db19b50c32\data\databases\store_lock"
if os.path.exists(lock_file):
    try:
        os.remove(lock_file)
        print("Removed stale store_lock")
    except Exception as e:
        print("Could not remove lock:", e)

print("Starting Neo4j DBMS daemon...")
proc = subprocess.Popen([bat_path, "console"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")

while True:
    line = proc.stdout.readline()
    if not line and proc.poll() is not None:
        break
    if line:
        print(line.strip())
        sys.stdout.flush()
