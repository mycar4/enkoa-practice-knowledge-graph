import os
from dotenv import load_dotenv

load_dotenv(".env", override=True)
for k, v in sorted(os.environ.items()):
    if any(term in k.upper() for term in ["NEO4J", "AURA", "DART", "QDRANT", "OPENAI"]):
        masked = v[:5] + "..." + v[-4:] if v and len(v) > 10 else ("***" if v else "EMPTY")
        print(f"{k} = {masked}")
