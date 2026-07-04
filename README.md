# LegalDoc AI

> A local-first desktop app that reads legal documents (contracts, NDAs, judgments, policies) and lets you chat with them, summarize them, and audit them for standard clauses — all running on-device via Ollama, with optional OpenAI fallback.

## What It Does

- **Preview** — view document pages plus auto-detected dates, amounts, and deadlines
- **Ask** — chat with the document; answers stream in live with `[Source N]` citations back to the retrieved passages
- **Summarize** — one-click structured summary: parties, obligations, dates, risks
- **Audit** — checks 10 standard clauses (confidentiality, non-compete, IP assignment, limitation of liability, indemnification, termination, governing law, data protection, force majeure, dispute resolution) and flags each `PRESENT` / `ABSENT` / `RISK`, rolled into a 0–100 compliance health score
- **Export** — generate a client-ready Word report of everything found

Everything runs locally — documents never leave the machine unless you explicitly switch to the OpenAI provider.

## Architecture

Hybrid RAG engine (`rag_engine.py`):
- **Dense retrieval** — FAISS index over `fastembed` (quantized ONNX) embeddings
- **Sparse retrieval** — BM25 over the same chunks
- Results are fused for higher recall than either method alone
- Index cache keyed by document hash, so re-opening the same file loads in under a second

LLM layer (`llm_backend.py`):
- Talks to a local **Ollama** server by default (OpenAI-compatible API), with a real OpenAI key as a drop-in alternative
- Streams answers/summaries token-by-token
- Structured JSON prompts for clause auditing, with defensive parsing (strips markdown fences, isolates the JSON span) since the model output isn't always clean

UI: desktop app built with `customtkinter` + `tkinter`, PDF/DOCX page previews via PyMuPDF.

## Tech Stack

| Component | Technology |
|---|---|
| Desktop UI | customtkinter, tkinter |
| Dense retrieval | FAISS + fastembed (ONNX) |
| Sparse retrieval | rank_bm25 |
| Chunking | langchain-text-splitters |
| Document parsing | PyMuPDF (PDF), python-docx (DOCX) |
| LLM | Ollama (local) or OpenAI API |
| Language | Python 3.10+ |

## Setup

```bash
pip install -r requirements.txt
```

Run a local model via [Ollama](https://ollama.com), or set `OPENAI_API_KEY` in a `.env` file (see `.env.example`) to use OpenAI instead.

```bash
python main.py
```

Sample documents are in `test_docs/` to try the app immediately.

## Benchmarking

`benchmark.py` / `speed_test.py` measure indexing and query latency across documents, useful for tuning chunk size and cache behavior.
