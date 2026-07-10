# -*- coding: utf-8 -*-
"""Fill the AIML template slides with LegalDoc AI content, keeping template styling."""
import re
import os

SLIDES = r"C:\Users\aditm\Desktop\LegalDocAI\ppt2_unpacked\ppt\slides"

A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def para(text, sz=2000, bold=False, bullet=True, lvl=0, italic=False, color=None):
    """Build one <a:p> matching the template's Times New Roman style."""
    marL = 0 if lvl == 0 else 457200 * lvl
    indent = -274638 if bullet else 0
    if bullet:
        bu = '<a:buFont typeface="Arial" panose="020B0604020202020204" pitchFamily="34" charset="0"/><a:buChar char="&#8226;"/>'
        marL = 285750 if lvl == 0 else 742950
    else:
        bu = "<a:buNone/>"
        marL = 0 if lvl == 0 else 457200 * lvl
        indent = 0
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    fill = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>' if color else '<a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
    rpr = (f'<a:rPr lang="en-US" altLang="en-US" sz="{sz}"{b}{i} dirty="0">{fill}'
           '<a:latin typeface="Times New Roman" panose="02020603050405020304" pitchFamily="18" charset="0"/>'
           '<a:cs typeface="Times New Roman" panose="02020603050405020304" pitchFamily="18" charset="0"/></a:rPr>')
    ppr = (f'<a:pPr marL="{marL}" lvl="{lvl}" indent="{indent}" eaLnBrk="0" fontAlgn="base" hangingPunct="0">'
           '<a:lnSpc><a:spcPct val="100000"/></a:lnSpc>'
           '<a:spcBef><a:spcPct val="0"/></a:spcBef>'
           '<a:spcAft><a:spcPct val="0"/></a:spcAft>' + bu + '</a:pPr>')
    return f"<a:p>{ppr}<a:r>{rpr}<a:t>{esc(text)}</a:t></a:r></a:p>"


def blank(sz=800):
    return (f'<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr lang="en-US" sz="{sz}" dirty="0"/></a:p>')


def set_title(xml, title):
    # Title placeholder is the <p:sp> whose nvPr contains <p:ph type="title"/>
    def repl(m):
        block = m.group(0)
        # replace the txBody content's runs with a single run
        newtx = (f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" dirty="0"/>'
                 f'<a:t>{esc(title)}</a:t></a:r></a:p></p:txBody>')
        block = re.sub(r"<p:txBody>.*?</p:txBody>", newtx, block, count=1, flags=re.S)
        return block
    return re.sub(r'<p:sp>(?:(?!</p:sp>).)*?<p:ph type="title"/>.*?</p:sp>', repl, xml, count=1, flags=re.S)


def set_body(xml, paras):
    """Replace the body placeholder (<p:ph idx="1"/>) txBody paragraphs."""
    body = "".join(paras)

    def repl(m):
        block = m.group(0)
        newtx = re.sub(r"(<a:lstStyle/>).*?(</p:txBody>)", r"\1" + body + r"\2",
                       block, count=1, flags=re.S)
        return newtx
    return re.sub(r'<p:sp>(?:(?!</p:sp>).)*?<p:ph idx="1"/>.*?</p:sp>', repl, xml, count=1, flags=re.S)


def load(n):
    with open(os.path.join(SLIDES, f"slide{n}.xml"), encoding="utf-8") as f:
        return f.read()


def save(n, xml):
    with open(os.path.join(SLIDES, f"slide{n}.xml"), "w", encoding="utf-8") as f:
        f.write(xml)


# ---- Slide content definitions (title, [paras]) --------------------------
def P(*a, **k):
    return para(*a, **k)


content = {}

# Slide 2: Introduction
content[2] = ("Introduction", [
    P("Project: LegalDoc AI – an app that reads legal documents and answers questions about them, running fully on your own computer.", sz=2000, bold=True),
    blank(),
    P("Legal documents (contracts, NDAs, court judgments) are long and hard to read.", sz=2000),
    P("Existing AI tools are cloud-based, costly, and send private documents to outside servers.", sz=2000),
    P("Our tool is free, private, and works offline – useful to students, small businesses, and individuals.", sz=2000),
    P("Supports SDG 16 (access to justice) by making legal documents easy to understand.", sz=2000),
])

# Slide 3: Application Domain
content[3] = ("Application Domain", [
    P("Domain: Legal Technology (LegalTech) and Natural Language Processing.", sz=2000, bold=True),
    blank(),
    P("Target users:", sz=2000, bold=True),
    P("Law students studying real cases", sz=2000, lvl=1),
    P("Solo lawyers and small businesses", sz=2000, lvl=1),
    P("Anyone signing a contract, NDA, or lease", sz=2000, lvl=1),
    blank(),
    P("Practical use: read, question, summarize, and audit any legal document privately.", sz=2000),
])

# Slide 4: Literature Review
content[4] = ("Literature Review / Related Work", [
    P("Lewis et al. (2020) – Retrieval-Augmented Generation (RAG): grounds AI answers in retrieved text to reduce made-up answers.", sz=1800),
    P("Robertson & Zaragoza (2009) – BM25: a keyword search method, strong for exact terms.", sz=1800),
    P("Wang et al. (2020) – MiniLM: a small, fast model to turn text into searchable vectors.", sz=1800),
    P("Johnson et al. (2021) – FAISS: a fast library for searching by meaning.", sz=1800),
    P("Hendrycks et al. (2021) – CUAD: 510 real contracts labelled by legal experts; used as our benchmark.", sz=1800),
    blank(),
    P("Gap: most tools use only one search method and run on the cloud. We combine two search methods and run offline.", sz=1800, italic=True),
])

# Slide 5: Problem Statement
content[5] = ("Problem Statement", [
    P("How can a person quickly and privately understand a long legal document without a lawyer?", sz=2000, bold=True),
    blank(),
    P("Manual reading is slow and easy to get wrong.", sz=2000),
    P("Cloud AI tools risk privacy, cost money, and hide how they find answers.", sz=2000),
    P("Simple keyword search misses meaning; pure meaning search misses exact legal terms.", sz=2000),
    blank(),
    P("Goal: a private, offline, low-cost tool that answers questions with evidence you can check.", sz=2000, italic=True),
])

# Slide 7: Hardware & Software
content[7] = ("Hardware & Software Requirements", [
    P("Hardware:", sz=2000, bold=True),
    P("Standard laptop/desktop CPU (no GPU needed)", sz=2000, lvl=1),
    P("8 GB RAM, a few GB storage for models", sz=2000, lvl=1),
    blank(),
    P("Software:", sz=2000, bold=True),
    P("Windows / Python 3.13", sz=2000, lvl=1),
    P("Libraries: fastembed, FAISS, rank-bm25, PyMuPDF, CustomTkinter", sz=2000, lvl=1),
    P("Ollama with Llama 3.2 (local, free) or OpenAI GPT-4o-mini (optional)", sz=2000, lvl=1),
])

# Slide 8: Implementation Overview
content[8] = ("Implementation Overview", [
    P("A standalone desktop app – no browser, no internet needed.", sz=2000, bold=True),
    blank(),
    P("Five features in one window:", sz=2000, bold=True),
    P("Preview – view the real document pages and key facts", sz=2000, lvl=1),
    P("Ask – chat with the document; answers show sources", sz=2000, lvl=1),
    P("Summary – one-click overview", sz=2000, lvl=1),
    P("Audit – 10 clauses checked, scored 0–100", sz=2000, lvl=1),
    P("Negotiate – practise against an AI opposing lawyer", sz=2000, lvl=1),
])

# Slide 9: System Implementation
content[9] = ("System Implementation", [
    P("Read & split: the document text is broken into small overlapping pieces.", sz=2000),
    P("Two searches: one by meaning (FAISS) and one by exact words (BM25), run together.", sz=2000),
    P("Combine: both results are blended into one ranked list of the best passages.", sz=2000),
    P("Answer: the best passages plus your question go to the AI, which writes a cited answer live.", sz=2000),
    P("Cache: once read, a document re-opens in under a second.", sz=2000),
])

# Slide 11: Applications & Future
content[11] = ("Applications & Future Enhancements", [
    P("Applications:", sz=2000, bold=True),
    P("Law firms, small businesses, students, compliance teams", sz=2000, lvl=1),
    P("Reviewing contracts, NDAs, policies, and judgments privately", sz=2000, lvl=1),
    blank(),
    P("Future work:", sz=2000, bold=True),
    P("Support for Indian legal documents and languages (Hindi, Kannada)", sz=2000, lvl=1),
    P("Compare multiple contracts at once", sz=2000, lvl=1),
    P("Browser extension for in-page review", sz=2000, lvl=1),
])

# Slide 12: Conclusion
content[12] = ("Conclusion", [
    P("Built a working, private, offline tool that reads and answers questions about legal documents.", sz=2000),
    P("Hybrid search (meaning + exact words) gives accurate, checkable answers with sources.", sz=2000),
    P("Tested on three real Supreme Court cases (62–237 pages) with correct answers.", sz=2000),
    P("Audit is benchmarked against 510 real contracts (CUAD), not just AI opinion.", sz=2000),
    P("Supports SDG 16 by making legal understanding accessible to everyone.", sz=2000),
])

for n, (title, paras) in content.items():
    xml = load(n)
    xml = set_title(xml, title)
    xml = set_body(xml, paras)
    save(n, xml)
    print(f"filled slide {n}")

print("done")
