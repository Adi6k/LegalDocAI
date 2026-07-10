# -*- coding: utf-8 -*-
"""Third pass: demo slide (16) text, flowchart slide (15) title/body clear."""
import re, os

SLIDES = r"C:\Users\aditm\Desktop\LegalDocAI\ppt2_unpacked\ppt\slides"


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def run(text, sz=1800, bold=False, italic=False, color=None):
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    fill = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>' if color else '<a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
    return (f'<a:r><a:rPr lang="en-US" altLang="en-US" sz="{sz}"{b}{i} dirty="0">{fill}'
            '<a:latin typeface="Times New Roman" panose="02020603050405020304" pitchFamily="18" charset="0"/>'
            '<a:cs typeface="Times New Roman" panose="02020603050405020304" pitchFamily="18" charset="0"/></a:rPr>'
            f'<a:t>{esc(text)}</a:t></a:r>')


def parah(runs, bullet=True, lvl=0):
    if bullet:
        bu = '<a:buFont typeface="Arial" panose="020B0604020202020204" pitchFamily="34" charset="0"/><a:buChar char="&#8226;"/>'
        marL = 285750 if lvl == 0 else 742950
        indent = -274638
    else:
        bu = "<a:buNone/>"
        marL = 0 if lvl == 0 else 457200 * lvl
        indent = 0
    ppr = (f'<a:pPr marL="{marL}" lvl="{lvl}" indent="{indent}" eaLnBrk="0" fontAlgn="base" hangingPunct="0">'
           '<a:lnSpc><a:spcPct val="100000"/></a:lnSpc><a:spcBef><a:spcPct val="0"/></a:spcBef>'
           '<a:spcAft><a:spcPct val="0"/></a:spcAft>' + bu + '</a:pPr>')
    return f"<a:p>{ppr}{''.join(runs)}</a:p>"


def blank(sz=700):
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


# ---- Slide 16: Demo (three test PDFs, short summary + Ask question) ----
BLUE = "1F4E79"
paras16 = [
    parah([run("Three real Supreme Court cases were used to test the app. "
               "Below is a short summary of each and the exact question typed into the ", sz=1700),
           run("Ask", sz=1700, bold=True, italic=True),
           run(" tab.", sz=1700)], bullet=False),
    blank(500),
    parah([run("1. Google v. Oracle (62 pages) ", sz=1800, bold=True, color=BLUE),
           run("– a case about copying computer code.", sz=1800)]),
    parah([run("Ask: ", sz=1700, bold=True),
           run("“Was Google's copying of the Java API fair use?”", sz=1700, italic=True)], lvl=1),
    blank(400),
    parah([run("2. Dobbs v. Jackson (213 pages) ", sz=1800, bold=True, color=BLUE),
           run("– a case about abortion rights.", sz=1800)]),
    parah([run("Ask: ", sz=1700, bold=True),
           run("“What did the Court hold about Roe v. Wade?”", sz=1700, italic=True)], lvl=1),
    blank(400),
    parah([run("3. SFFA v. Harvard (237 pages) ", sz=1800, bold=True, color=BLUE),
           run("– a case about race in college admissions.", sz=1800)]),
    parah([run("Ask: ", sz=1700, bold=True),
           run("“What did the Court decide about race-based admissions?”", sz=1700, italic=True)], lvl=1),
    blank(400),
    parah([run("In every case the app gave the correct answer and showed the passages it used as ", sz=1600, italic=True),
           run("Sources", sz=1600, bold=True, italic=True),
           run(".", sz=1600, italic=True)], bullet=False),
]
xml = load(16)
xml = set_title(xml, "Demo: Test Documents & Sample Questions")
xml = set_body(xml, paras16)
save(16, xml)
print("slide 16 done")

# ---- Slide 15: Flowchart – set title, clear body (image added separately) ----
xml = load(15)
xml = set_title(xml, "System Architecture (Block Diagram)")
xml = set_body(xml, [blank(400)])
save(15, xml)
print("slide 15 title/body done")
