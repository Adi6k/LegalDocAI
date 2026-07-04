"""Hybrid RAG engine: fastembed (ONNX, quantized) + FAISS dense + BM25 sparse fusion.
Index caching: re-opening the same document loads in under a second."""
import hashlib
import io
import os
import pickle
import re

import numpy as np
import faiss
from fastembed import TextEmbedding
from rank_bm25 import BM25Okapi
from langchain_text_splitters import RecursiveCharacterTextSplitter
import fitz  # PyMuPDF
from docx import Document as DocxDocument

_BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(_BASE, ".index_cache")
MODEL_DIR = os.path.join(_BASE, ".model_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

COMPLIANCE_CLAUSES = [
    "Confidentiality / Non-Disclosure",
    "Non-Compete",
    "Intellectual Property (IP) Assignment",
    "Limitation of Liability",
    "Indemnification",
    "Termination / Exit Clause",
    "Governing Law / Jurisdiction",
    "Data Protection / Privacy",
    "Force Majeure",
    "Dispute Resolution / Arbitration",
]


# ── Document extraction ──────────────────────────────────────────────────
def extract_document(file_bytes: bytes, filename: str) -> dict:
    """Returns {'text', 'pages', 'words'} for PDF/DOCX/TXT."""
    ext = filename.lower().rsplit(".", 1)[-1]
    pages = None
    if ext == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = doc.page_count
        text = "\n".join(page.get_text() for page in doc)
    elif ext in ("docx", "doc"):
        doc = DocxDocument(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif ext == "txt":
        text = file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: .{ext}")
    return {"text": text, "pages": pages, "words": len(text.split())}


# ── Quick entity extraction (regex, instant) ─────────────────────────────
def extract_key_facts(text: str) -> dict:
    sample = text[:80000]
    dates = re.findall(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
        sample)
    amounts = re.findall(r"(?:₹|Rs\.?|INR|\$|USD|EUR|£)\s?[\d,]+(?:\.\d+)?(?:\s?(?:lakh|crore|million|billion|k|M))?",
                         sample)
    durations = re.findall(r"\b\d+\s+(?:days?|months?|years?|weeks?)\b", sample, re.IGNORECASE)
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", sample)
    dedup = lambda xs, n: list(dict.fromkeys(xs))[:n]
    return {
        "Dates": dedup(dates, 8),
        "Monetary amounts": dedup(amounts, 8),
        "Time periods": dedup(durations, 8),
        "Email addresses": dedup(emails, 5),
    }


# ── Hybrid engine ─────────────────────────────────────────────────────────
class HybridRAGEngine:
    def __init__(self, embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        # ONNX runtime — MiniLM is ~3x faster than BGE-small on CPU with minimal
        # quality loss, and the BM25 side of the hybrid search covers exact terms
        self.model_name = embedding_model
        # Prefer a fully-downloaded local copy; the HF hub cache can end up
        # incomplete on Windows (symlink permissions), which crashes on load
        local_dir = os.path.join(MODEL_DIR, f"fast-{embedding_model.split('/')[-1]}")
        if os.path.exists(os.path.join(local_dir, "model.onnx")):
            self.embedder = TextEmbedding(embedding_model, specific_model_path=local_dir)
        else:
            self.embedder = TextEmbedding(embedding_model, cache_dir=MODEL_DIR)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=64,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        self.chunks: list[str] = []
        self.bm25: BM25Okapi | None = None
        self.faiss_index: faiss.IndexFlatIP | None = None

    def ingest(self, text: str, progress_cb=None, cache_key: str | None = None) -> bool:
        """Index a document. progress_cb(fraction, message) is called during work.
        Returns True if loaded from cache."""
        model_tag = re.sub(r"\W+", "_", self.model_name)
        cache_path = (os.path.join(CACHE_DIR, f"{cache_key}-{model_tag}.pkl")
                      if cache_key else None)

        if cache_path and os.path.exists(cache_path):
            if progress_cb:
                progress_cb(0.5, "Loading cached index...")
            with open(cache_path, "rb") as f:
                cached = pickle.load(f)
            self.chunks = cached["chunks"]
            embeddings = cached["embeddings"]
            self._build_indexes(embeddings, progress_cb)
            if progress_cb:
                progress_cb(1.0, "Loaded from cache")
            return True

        if progress_cb:
            progress_cb(0.02, "Splitting into chunks...")
        self.chunks = self.splitter.split_text(text)

        # Embed in batches so we can report real progress
        all_embs = []
        batch = 96
        total = len(self.chunks)
        for i in range(0, total, batch):
            part = self.chunks[i:i + batch]
            all_embs.extend(self.embedder.embed(part, batch_size=batch))
            if progress_cb:
                frac = 0.05 + 0.85 * min(1.0, (i + batch) / total)
                progress_cb(frac, f"Embedding chunks  {min(i + batch, total)}/{total}")
        embeddings = np.array(all_embs, dtype=np.float32)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.clip(norms, 1e-9, None)

        self._build_indexes(embeddings, progress_cb)

        if cache_path:
            with open(cache_path, "wb") as f:
                pickle.dump({"chunks": self.chunks, "embeddings": embeddings}, f)
        if progress_cb:
            progress_cb(1.0, "Index ready")
        return False

    def _build_indexes(self, embeddings: np.ndarray, progress_cb=None):
        if progress_cb:
            progress_cb(0.92, "Building FAISS + BM25 indexes...")
        self.faiss_index = faiss.IndexFlatIP(embeddings.shape[1])
        self.faiss_index.add(embeddings)
        self.bm25 = BM25Okapi([c.lower().split() for c in self.chunks])

    @staticmethod
    def cache_key_for(file_bytes: bytes) -> str:
        return hashlib.md5(file_bytes).hexdigest()

    # ── Retrieval ────────────────────────────────────────────────────────
    def _dense_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        q = np.array(list(self.embedder.query_embed(query)), dtype=np.float32)
        q = q / np.clip(np.linalg.norm(q, axis=1, keepdims=True), 1e-9, None)
        scores, indices = self.faiss_index.search(q, top_k)
        return [(int(i), float(s)) for i, s in zip(indices[0], scores[0]) if i >= 0]

    def _bm25_search(self, query: str, top_k: int) -> list[tuple[int, float]]:
        scores = self.bm25.get_scores(query.lower().split())
        top = np.argsort(scores)[::-1][:top_k]
        return [(int(i), float(scores[i])) for i in top if scores[i] > 0]

    def hybrid_retrieve(self, query: str, top_k: int = 5, bm25_weight: float = 0.3) -> list[dict]:
        if not self.chunks:
            return []
        dense = self._dense_search(query, top_k * 2)
        sparse = self._bm25_search(query, top_k * 2)
        d_max = max((s for _, s in dense), default=1.0) or 1.0
        s_max = max((s for _, s in sparse), default=1.0) or 1.0
        combined: dict[int, float] = {}
        for i, s in dense:
            combined[i] = (1 - bm25_weight) * (s / d_max)
        for i, s in sparse:
            combined[i] = combined.get(i, 0) + bm25_weight * (s / s_max)
        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [{"chunk": self.chunks[i], "score": round(s, 4), "index": i} for i, s in ranked]

    def get_all_text(self) -> str:
        return "\n".join(self.chunks)
