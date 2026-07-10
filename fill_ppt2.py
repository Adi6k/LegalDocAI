# -*- coding: utf-8 -*-
"""Second pass: title slide, methodology, performance, references."""
import re, os
import importlib.util
spec = importlib.util.spec_from_file_location("f1", r"C:\Users\aditm\Desktop\LegalDocAI\fill_ppt.py")

SLIDES = r"C:\Users\aditm\Desktop\LegalDocAI\ppt2_unpacked\ppt\slides"


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def para(text, sz=2000, bold=False, bullet=True, lvl=0, italic=False):
    if bullet:
        bu = '<a:buFont typeface="Arial" panose="020B0604020202020204" pitchFamily="34" charset="0"/><a:buChar char="&#8226;"/>'
        marL = 285750 if lvl == 0 else 742950
        indent = -274638
    else:
        bu = "<a:buNone/>"
        marL = 0
        indent = 0
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    rpr = (f'<a:rPr lang="en-US" altLang="en-US" sz="{sz}"{b}{i} dirty="0"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
           '<a:latin typeface="Times New Roman" panose="02020603050405020304" pitchFamily="18" charset="0"/>'
           '<a:cs typeface="Times New Roman" panose="02020603050405020304" pitchFamily="18" charset="0"/></a:rPr>')
    ppr = (f'<a:pPr marL="{marL}" lvl="{lvl}" indent="{indent}" eaLnBrk="0" fontAlgn="base" hangingPunct="0">'
           '<a:lnSpc><a:spcPct val="100000"/></a:lnSpc><a:spcBef><a:spcPct val="0"/></a:spcBef>'
           '<a:spcAft><a:spcPct val="0"/></a:spcAft>' + bu + '</a:pPr>')
    return f"<a:p>{ppr}<a:r>{rpr}<a:t>{esc(text)}</a:t></a:r></a:p>"


def blank(sz=800):
    return f'<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr lang="en-US" sz="{sz}" dirty="0"/></a:p>'


def load(n):
    with open(os.path.join(SLIDES, f"slide{n}.xml"), encoding="utf-8") as f:
        return f.read()


def save(n, xml):
    with open(os.path.join(SLIDES, f"slide{n}.xml"), "w", encoding="utf-8") as f:
        f.write(xml)


def set_title(xml, title):
    def repl(m):
        block = m.group(0)
        newtx = (f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US" dirty="0"/>'
                 f'<a:t>{esc(title)}</a:t></a:r></a:p></p:txBody>')
        return re.sub(r"<p:txBody>.*?</p:txBody>", newtx, block, count=1, flags=re.S)
    return re.sub(r'<p:sp>(?:(?!</p:sp>).)*?<p:ph type="title"/>.*?</p:sp>', repl, xml, count=1, flags=re.S)


def set_body(xml, paras):
    body = "".join(paras)
    def repl(m):
        block = m.group(0)
        return re.sub(r"(<a:lstStyle/>).*?(</p:txBody>)", r"\1" + body + r"\2", block, count=1, flags=re.S)
    return re.sub(r'<p:sp>(?:(?!</p:sp>).)*?<p:ph idx="1"/>.*?</p:sp>', repl, xml, count=1, flags=re.S)


# Slide 6: Methodology (concise; flowchart is on its own next slide)
xml = load(6)
xml = set_title(xml, "Methodology / Proposed System")
xml = set_body(xml, [
    para("Approach: Hybrid Retrieval-Augmented Generation (RAG) running fully offline.", sz=2000, bold=True),
    blank(),
    para("Data: user's PDF/DOCX/TXT documents; benchmark uses the CUAD contract dataset.", sz=2000),
    para("Preprocessing: text is extracted and split into 512-word overlapping chunks.", sz=2000),
    para("Search: FAISS (by meaning) + BM25 (by exact words), blended by a tunable weight.", sz=2000),
    para("Model: Llama 3.2 (local, free) or GPT-4o-mini (optional cloud).", sz=2000),
    para("Evaluation: indexing time, search speed, and answer correctness (see next slides).", sz=2000),
])
save(6, xml)
print("slide 6 done")

# Slide 10: Performance (text summary; benchmark numbers)
xml = load(10)
xml = set_title(xml, "Performance Analysis")
xml = set_body(xml, [
    para("Tested on three full Supreme Court cases (62 to 237 pages).", sz=2000, bold=True),
    blank(),
    para("First-time indexing: 6.6 s (62 pages) to 26.6 s (237 pages) on a normal CPU.", sz=2000),
    para("Re-opening a saved document: about 0.1 second (from cache).", sz=2000),
    para("Search speed: 25 to 36 milliseconds per question.", sz=2000),
    para("All test questions answered correctly, with sources cited.", sz=2000),
    para("Faster model choice (MiniLM) cut indexing time by about 3 times.", sz=2000),
])
save(10, xml)
print("slide 10 done")

# Slide 13: References
xml = load(13)
xml = set_title(xml, "References")
xml = set_body(xml, [
    para("D. Hendrycks et al., “CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review,” NeurIPS, 2021.", sz=1600, bullet=True),
    para("P. Lewis et al., “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks,” NeurIPS, 2020.", sz=1600, bullet=True),
    para("S. Robertson and H. Zaragoza, “The Probabilistic Relevance Framework: BM25 and Beyond,” FnTIR, 2009.", sz=1600, bullet=True),
    para("J. Johnson, M. Douze, H. Jégou, “Billion-Scale Similarity Search with GPUs,” IEEE Trans. Big Data, 2021.", sz=1600, bullet=True),
    para("W. Wang et al., “MiniLM: Deep Self-Attention Distillation for Task-Agnostic Compression,” NeurIPS, 2020.", sz=1600, bullet=True),
    para("Supreme Court of the United States, opinions retrieved from supremecourt.gov.", sz=1600, bullet=True),
])
save(13, xml)
print("slide 13 done")

# Slide 1: title slide (ctrTitle + subtitle)
xml = load(1)
xml = xml.replace("Title of the Lab-Based Project",
                  esc("LegalDoc AI: A Private, Offline AI Assistant for Reading and Auditing Legal Documents"))
save(1, xml)
print("slide 1 done")
