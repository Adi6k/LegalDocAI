"""Benchmark: new fastembed engine on the large case PDFs."""
import os
import time
from rag_engine import HybridRAGEngine, extract_document
from llm_backend import get_llm_client, stream_answer

DOCS = {
    "Dobbs_v_Jackson_2022.pdf": "What did the Court hold about Roe v. Wade?",
    "SFFA_v_Harvard_2023.pdf": "What did the Court decide about race-based admissions?",
    "Google_v_Oracle_2021.pdf": "Was Google's copying of the Java API fair use?",
}

engine = HybridRAGEngine()
list(engine.embedder.embed(["warm up"]))
client = get_llm_client("ollama")

for fname, query in DOCS.items():
    with open(os.path.join("test_docs", fname), "rb") as f:
        data = f.read()
    meta = extract_document(data, fname)

    t0 = time.time()
    cached = engine.ingest(meta["text"], cache_key=HybridRAGEngine.cache_key_for(data))
    t_index = time.time() - t0

    t0 = time.time()
    results = engine.hybrid_retrieve(query, top_k=5, bm25_weight=0.3)
    t_retrieve = (time.time() - t0) * 1000

    t0 = time.time()
    answer = "".join(stream_answer(client, "llama3.2", query, results))
    t_llm = time.time() - t0

    print("=" * 80)
    print(f"DOC: {fname}  ({meta['pages']} pages, {len(engine.chunks):,} chunks)")
    print(f"  Index: {t_index:.1f}s{' (CACHE)' if cached else ''} | "
          f"Retrieve: {t_retrieve:.0f}ms | LLM: {t_llm:.1f}s")
    print(f"  Q: {query}")
    print(f"  A: {answer[:300]}")
