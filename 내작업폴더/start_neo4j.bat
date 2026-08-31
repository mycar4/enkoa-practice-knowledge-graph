@echo off
set "JAVA_HOME=C:\Users\Playdata\.Neo4jDesktop2\Cache\runtime\zulu21.50.19-ca-jre21.0.11-win_x64"
set "PATH=%JAVA_HOME%\bin;%PATH%"
set "NEO4J_ACCEPT_LICENSE_AGREEMENT=yes"
"C:\Users\Playdata\.Neo4jDesktop2\Data\dbmss\dbms-f6479556-481c-4e3f-9f9f-67db19b50c32\bin\neo4j.bat" console
