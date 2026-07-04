import time
from rag_engine import HybridRAGEngine, extract_document
from llm_backend import (get_llm_client, audit_clause, warm_up,
                         COMPLIANCE_CLAUSES, AUDIT_QUERIES)

if __name__ == "__main__":
    with open("test_docs/Google_v_Oracle_2021.pdf", "rb") as f:
        data = f.read()
    meta = extract_document(data, "g.pdf")
    engine = HybridRAGEngine()
    engine.ingest(meta["text"], cache_key=HybridRAGEngine.cache_key_for(data))

    client = get_llm_client("ollama")
    model = "llama3.2:1b"
    warm_up(client, model)

    t0 = time.time()
    for clause in COMPLIANCE_CLAUSES:
        t1 = time.time()
        chunks = engine.hybrid_retrieve(AUDIT_QUERIES[clause], top_k=3, bm25_weight=0.5)
        r = audit_clause(client, model, clause, chunks)
        print(f"  {time.time()-t1:4.1f}s  {r['status']:8}  {clause}")
    print(f"TOTAL AUDIT: {time.time()-t0:.1f}s")
