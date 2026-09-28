# test_rag.py
from db import query_knowledge_base, init_db

# Ensure database is initialized
init_db()

# Test keywords matching your uploaded clinical_protocols.txt
test_queries = [
    "knee clicking",
    "chest tightness",
    "thunderclap headache",
    "high fever",
    "chronic lower back pain"
]

print("="*60)
print("🔍 TESTING MEDITRIAGE RAG KNOWLEDGE BASE ENGINE")
print("="*60 + "\n")

for query in test_queries:
    print(f"Query: '{query}'")
    result = query_knowledge_base(query)
    
    if result.get("found"):
        print(f"✅ Match Found!")
        print(f"Guidance:\n{result.get('guidance')}\n")
    else:
        print(f"❌ No Match: {result.get('guidance')}\n")
        
    print("-" * 60)