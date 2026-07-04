from rag_engine import HybridRAGEngine
from llm_backend import get_llm_client, ask_question

text = """CONSULTING AGREEMENT. This agreement is between Acme Corp and John Doe.
Confidentiality: The consultant shall not disclose any proprietary information.
Termination: Either party may terminate with 30 days written notice.
Governing Law: This agreement is governed by the laws of Karnataka, India.
Payment: The consultant will be paid Rs 50,000 per month."""

eng = HybridRAGEngine()
eng.ingest(text)
res = eng.hybrid_retrieve("What is the termination notice period?", top_k=3)
print("RETRIEVAL OK:", len(res), "chunks, top score:", res[0]["score"])

client = get_llm_client("ollama")
ans = ask_question(client, "llama3.2", "What is the termination notice period?", res)
print("LLM OK:", ans[:300])
