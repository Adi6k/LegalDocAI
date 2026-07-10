# -*- coding: utf-8 -*-
"""Fix slide6 (Methodology): move real content into the large 'Rectangle 1'
shape, clear the small leftover idx=1 box. Clear both text shapes on slide15
(flowchart slide) since its content is the image."""
import re, os

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


def replace_named_shape_body(xml, shape_name, paras):
    """Replace txBody content of the <p:sp> whose cNvPr name matches shape_name."""
    body = "".join(paras)
    pattern = re.compile(
        r'(<p:sp>(?:(?!</p:sp>).)*?name="' + re.escape(shape_name) + r'".*?<p:txBody>)(.*?)(</p:txBody>)',
        re.S)
    def repl(m):
        return m.group(1) + '<a:bodyPr vert="horz" wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720" numCol="1" anchor="t" anchorCtr="0" compatLnSpc="1"><a:normAutofit/></a:bodyPr><a:lstStyle/>' + body + m.group(3)
    new_xml, n = pattern.subn(repl, xml, count=1)
    if n == 0:
        raise ValueError(f"shape '{shape_name}' not found")
    return new_xml


def clear_ph_idx1_body(xml):
    def repl(m):
        block = m.group(0)
        return re.sub(r"(<a:lstStyle/>).*?(</p:txBody>)", r"\1" + blank() + r"\2", block, count=1, flags=re.S)
    return re.sub(r'<p:sp>(?:(?!</p:sp>).)*?<p:ph idx="1"/>.*?</p:sp>', repl, xml, count=1, flags=re.S)


methodology_paras = [
    para("Approach: Hybrid Retrieval-Augmented Generation (RAG) running fully offline.", sz=2000, bold=True),
    blank(),
    para("Data: user's PDF/DOCX/TXT documents; benchmark uses the CUAD contract dataset.", sz=2000),
    para("Preprocessing: text is extracted and split into 512-word overlapping chunks.", sz=2000),
    para("Search: FAISS (by meaning) + BM25 (by exact words), blended by a tunable weight.", sz=2000),
    para("Model: Llama 3.2 (local, free) or GPT-4o-mini (optional cloud).", sz=2000),
    para("Evaluation: indexing time, search speed, and answer correctness (see next slides).", sz=2000),
]

# --- slide 6: put real content in "Rectangle 1", clear the small idx=1 box ---
xml = load(6)
xml = replace_named_shape_body(xml, "Rectangle 1", methodology_paras)
xml = clear_ph_idx1_body(xml)
save(6, xml)
print("slide6 fixed")

# --- slide 15: clear BOTH text shapes (title + image only) ---
xml = load(15)
xml = replace_named_shape_body(xml, "Rectangle 1", [blank()])
xml = clear_ph_idx1_body(xml)
save(15, xml)
print("slide15 fixed")
