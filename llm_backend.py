import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

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


def get_llm_client(provider: str = "ollama"):
    if provider == "ollama":
        return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


def _is_ollama(client: OpenAI) -> bool:
    return "11434" in str(client.base_url)


def _extra(client: OpenAI) -> dict:
    # keep the model resident in RAM between calls (Ollama only)
    return {"extra_body": {"keep_alive": "30m"}} if _is_ollama(client) else {}


def warm_up(client: OpenAI, model: str):
    """Load the model into memory ahead of the first real question."""
    try:
        client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "hi"}],
            max_tokens=1, **_extra(client))
    except Exception:
        pass  # e.g. Ollama not running yet — first real call will surface it


def _doc_excerpt(full_text: str, head: int = 6000, tail: int = 2000) -> str:
    """Contracts put key terms at the start and signatures/annexures at the end."""
    if len(full_text) <= head + tail:
        return full_text
    return full_text[:head] + "\n[...]\n" + full_text[-tail:]


def _stream(client: OpenAI, model: str, messages: list, temperature=0.2, max_tokens=700):
    response = client.chat.completions.create(
        model=model, messages=messages, temperature=temperature,
        max_tokens=max_tokens, stream=True, **_extra(client))
    for chunk in response:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


def stream_answer(client, model, query: str, context_chunks: list[dict]):
    context = "\n\n---\n\n".join(
        f"[Source {i + 1}]\n{c['chunk']}" for i, c in enumerate(context_chunks))
    return _stream(client, model, [
        {"role": "system", "content": (
            "You are a legal document analysis assistant. Answer based ONLY on the provided "
            "document context. Be direct and concise. Cite sources as [Source N]. "
            "If the context is insufficient, say so.")},
        {"role": "user", "content": f"DOCUMENT CONTEXT:\n{context}\n\nQUESTION: {query}"},
    ])


def stream_summary(client, model, full_text: str):
    return _stream(client, model, [
        {"role": "system", "content": (
            "You are a legal document summarizer. Provide a compact structured summary:\n"
            "DOCUMENT TYPE:\nPARTIES:\nKEY TERMS & OBLIGATIONS:\nIMPORTANT DATES:\n"
            "NOTABLE CLAUSES / RISKS:\nUse short bullet points. No filler.")},
        {"role": "user", "content": f"Summarize this legal document:\n\n{_doc_excerpt(full_text)}"},
    ], max_tokens=800)


AUDIT_QUERIES = {
    "Confidentiality / Non-Disclosure": "confidentiality non-disclosure confidential information secret",
    "Non-Compete": "non-compete competition restraint of trade compete",
    "Intellectual Property (IP) Assignment": "intellectual property IP assignment ownership copyright patent",
    "Limitation of Liability": "limitation of liability liable damages cap",
    "Indemnification": "indemnification indemnify hold harmless",
    "Termination / Exit Clause": "termination terminate notice period exit",
    "Governing Law / Jurisdiction": "governing law jurisdiction courts venue",
    "Data Protection / Privacy": "data protection privacy personal data GDPR",
    "Force Majeure": "force majeure act of god unforeseen events",
    "Dispute Resolution / Arbitration": "dispute resolution arbitration mediation",
}


def audit_clause(client, model, clause: str, context_chunks: list[dict]) -> dict:
    """Check one clause against its most relevant retrieved passages. Fast + grounded."""
    context = "\n---\n".join(c["chunk"] for c in context_chunks)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "You check legal documents for specific clauses. Reply with ONE JSON object only, "
                'no other text: {"status": "PRESENT" or "ABSENT" or "RISK", "detail": "one short sentence"}. '
                "PRESENT = the clause clearly exists in the excerpts. "
                "ABSENT = the excerpts do not contain it. "
                "RISK = it is mentioned but vague, one-sided, or incomplete.")},
            {"role": "user", "content":
                f'Clause to check: "{clause}"\n\nMost relevant excerpts from the document:\n{context}'},
        ],
        temperature=0.1, max_tokens=120, **_extra(client))
    raw = response.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        obj = json.loads(raw)
        status = str(obj.get("status", "")).upper()
        if status not in ("PRESENT", "ABSENT", "RISK"):
            raise ValueError
        return {"clause": clause, "status": status,
                "detail": str(obj.get("detail", ""))[:300]}
    except (json.JSONDecodeError, ValueError):
        return {"clause": clause, "status": "RISK",
                "detail": "Could not assess automatically — review this clause manually."}


def compliance_check(client, model, full_text: str) -> list[dict]:
    clauses = "\n".join(f"- {c}" for c in COMPLIANCE_CLAUSES)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "You are a legal compliance auditor. For each listed clause, check the document "
                "and output a JSON array where each element has:\n"
                '"clause" (the clause name), "status" ("PRESENT", "ABSENT", or "RISK"), '
                '"detail" (one short sentence).\n'
                "Return ONLY the JSON array — no markdown fences, no extra text.")},
            {"role": "user", "content":
                f"Clauses to check:\n{clauses}\n\nDOCUMENT:\n{_doc_excerpt(full_text)}"},
        ],
        temperature=0.1, max_tokens=1200, **_extra(client))
    raw = response.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = raw.find("["), raw.rfind("]")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [{"clause": "Parse Error", "status": "RISK", "detail": raw[:200]}]


FAIRNESS_QUERY = ("termination liability indemnification penalty obligations "
                  "sole discretion exclusive rights waiver unilateral")


def fairness_analysis(client, model, full_text: str, context_chunks: list[dict]) -> dict:
    """Judge how one-sided the contract is. Returns
    {"score": 0-100 (100 = perfectly balanced), "favors": str, "reasons": [str]}."""
    excerpts = "\n---\n".join(c["chunk"] for c in context_chunks)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": (
                "You assess how balanced a contract is between its parties. Reply with ONE "
                "JSON object only, no other text:\n"
                '{"score": <0-100 integer, 100 = perfectly balanced, 0 = totally one-sided>, '
                '"favors": "<party name or role the contract favors, or \'Balanced\'>", '
                '"reasons": ["<short reason>", "<short reason>", "<short reason>"]}\n'
                "Base the score on: who carries liability, who can terminate, penalty asymmetry, "
                "discretionary rights, and waiver clauses.")},
            {"role": "user", "content":
                f"CONTRACT (start):\n{_doc_excerpt(full_text, 4000, 1000)}\n\n"
                f"KEY RISK-RELATED EXCERPTS:\n{excerpts}"},
        ],
        temperature=0.1, max_tokens=250, **_extra(client))
    raw = response.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    try:
        obj = json.loads(raw)
        score = max(0, min(100, int(obj.get("score", 50))))
        reasons = [str(r)[:200] for r in obj.get("reasons", [])][:4]
        return {"score": score, "favors": str(obj.get("favors", "Unclear"))[:80],
                "reasons": reasons}
    except (json.JSONDecodeError, ValueError, TypeError):
        # Small models sometimes break the JSON — retry once on the larger local model
        if _is_ollama(client) and model != "llama3.2":
            return fairness_analysis(client, "llama3.2", full_text, context_chunks)
        return {"score": -1, "favors": "Could not assess",
                "reasons": ["The model response could not be parsed — try again "
                            "or switch to the larger model (llama3.2)."]}


def stream_negotiation(client, model, history: list[dict], user_msg: str,
                       context_chunks: list[dict]):
    """AI plays opposing counsel for the other party, grounded in the contract.
    history = prior [{'role': 'user'|'assistant', 'content': ...}] turns."""
    excerpts = "\n---\n".join(c["chunk"] for c in context_chunks)
    messages = [
        {"role": "system", "content": (
            "You are the OPPOSING COUNSEL in a live contract negotiation. You represent "
            "the party that this contract favors; the user represents the other side. "
            "Respond to each of the user's demands in character: defend the existing terms, "
            "push back with counter-arguments, cite specific clauses from the excerpts when "
            "you can, and concede ground only when the user makes a genuinely strong argument. "
            "Never break character or mention being an AI. Keep replies under 150 words.")},
        *history[-8:],
        {"role": "user", "content":
            f"[Relevant contract excerpts:\n{excerpts}]\n\n{user_msg}"},
    ]
    return _stream(client, model, messages, temperature=0.6, max_tokens=400)


def risk_score(results: list[dict]) -> int:
    if not results:
        return 0
    pts = {"PRESENT": 1.0, "RISK": 0.5, "ABSENT": 0.0}
    total = sum(pts.get(r.get("status", ""), 0) for r in results)
    return round(100 * total / len(results))
