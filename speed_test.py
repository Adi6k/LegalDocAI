"""Test the three new features: fairness analysis, CUAD benchmark, negotiation."""
import time
from rag_engine import HybridRAGEngine, extract_document
from llm_backend import (get_llm_client, fairness_analysis, stream_negotiation,
                         warm_up, FAIRNESS_QUERY)
from cuad_benchmark import benchmark_for, available

if __name__ == "__main__":
    print("=== CUAD BENCHMARK ===")
    print("stats loaded:", available())
    for clause, status in [("Governing Law / Jurisdiction", "ABSENT"),
                           ("Non-Compete", "PRESENT"),
                           ("Limitation of Liability", "PRESENT"),
                           ("Force Majeure", "ABSENT")]:
        print(f"  {clause} [{status}] -> {benchmark_for(clause, status)}")

    with open("test_docs/Google_v_Oracle_2021.pdf", "rb") as f:
        data = f.read()
    meta = extract_document(data, "g.pdf")
    engine = HybridRAGEngine()
    engine.ingest(meta["text"], cache_key=HybridRAGEngine.cache_key_for(data))

    client = get_llm_client("ollama")
    model = "llama3.2:1b"
    warm_up(client, model)

    print("\n=== FAIRNESS ===")
    t0 = time.time()
    chunks = engine.hybrid_retrieve(FAIRNESS_QUERY, top_k=6, bm25_weight=0.4)
    res = fairness_analysis(client, model, meta["text"], chunks)
    print(f"  {time.time()-t0:.1f}s -> score={res['score']} favors={res['favors']}")
    for r in res["reasons"]:
        print(f"    - {r}")

    print("\n=== NEGOTIATION ===")
    t0 = time.time()
    msg = "The liability terms here are unacceptable. My client needs a mutual cap."
    chunks = engine.hybrid_retrieve(msg, top_k=4, bm25_weight=0.4)
    reply = "".join(stream_negotiation(client, model, [], msg, chunks))
    print(f"  {time.time()-t0:.1f}s -> {reply[:400]}")
