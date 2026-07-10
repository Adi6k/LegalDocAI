# -*- coding: utf-8 -*-
"""Fix real visual bugs found in QA: title overlap on slide1, wrap=none causing
text overflow on slides 2/11/12, title clipping on slides 7/11/15/16 (long
2-line titles), and title/body overlap on slide6."""
import re, os

SLIDES = r"C:\Users\aditm\Desktop\LegalDocAI\ppt2_unpacked\ppt\slides"


def load(n):
    with open(os.path.join(SLIDES, f"slide{n}.xml"), encoding="utf-8") as f:
        return f.read()


def save(n, xml):
    with open(os.path.join(SLIDES, f"slide{n}.xml"), "w", encoding="utf-8") as f:
        f.write(xml)


# --- Fix 1: slide1 title too long -> overlaps logo. Shorten + shrink font ---
xml = load(1)
xml = xml.replace(
    "LegalDoc AI: A Private, Offline AI Assistant for Reading and Auditing Legal Documents",
    "LegalDoc AI: Offline Legal Assistant")
# shrink only the title run's font size (first 3 occurrences of sz="3600" belong
# to the title run + its two following <a:br> runs); leave Course lines at 3600.
xml = xml.replace(
    '<a:rPr lang="en-IN" sz="3600" b="1" dirty="0"/>\n              <a:t>LegalDoc AI: Offline Legal Assistant</a:t>',
    '<a:rPr lang="en-IN" sz="2800" b="1" dirty="0"/>\n              <a:t>LegalDoc AI: Offline Legal Assistant</a:t>')
xml = xml.replace(
    '<a:br>\n              <a:rPr lang="en-IN" sz="3600" b="1" dirty="0"/>\n            </a:br>\n            <a:br>\n              <a:rPr lang="en-IN" sz="3600" b="1" dirty="0"/>\n            </a:br>\n            <a:r>\n              <a:rPr lang="en-IN" sz="3600" b="1" dirty="0"/>\n              <a:t>Course:',
    '<a:br>\n              <a:rPr lang="en-IN" sz="2800" b="1" dirty="0"/>\n            </a:br>\n            <a:br>\n              <a:rPr lang="en-IN" sz="2800" b="1" dirty="0"/>\n            </a:br>\n            <a:r>\n              <a:rPr lang="en-IN" sz="3600" b="1" dirty="0"/>\n              <a:t>Course:', 1)
save(1, xml)
print("slide1 fixed")

# --- Fix 2: wrap="none" -> wrap="square" so long bullets wrap instead of overflow ---
for n in (2, 11, 12):
    xml = load(n)
    xml = xml.replace('wrap="none"', 'wrap="square"')
    save(n, xml)
    print(f"slide{n} wrap fixed")

# --- Fix 3: slide6 Rectangle-1 (real methodology content) starts too high,
#     overlapping the title box bottom edge (title ends ~699173 EMU).
xml = load(6)
xml = xml.replace('<a:off x="1147072" y="514507"/>\n            <a:ext cx="10074206" cy="7017306"/>',
                  '<a:off x="1147072" y="900000"/>\n            <a:ext cx="10074206" cy="5600000"/>')
save(6, xml)
print("slide6 spacing fixed")

# --- Fix 4: long 2-line titles clip at the top of the slide. Shorten to
#     single-line versions (title box is only ~0.7in tall, single-line by design).
title_fixes = {
    7: ("Hardware &amp; Software Requirements", "Hardware &amp; Software"),
    11: ("Applications &amp; Future Enhancements", "Applications &amp; Future Work"),
    15: ("System Architecture (Block Diagram)", "System Architecture"),
    16: ("Demo: Test Documents &amp; Sample Questions", "Demo &amp; Sample Questions"),
}
for n, (old, new) in title_fixes.items():
    xml = load(n)
    if old not in xml:
        print(f"WARNING: title text not found verbatim in slide{n}, trying unescaped")
        old2 = old.replace("&amp;", "&")
        new2 = new.replace("&amp;", "&")
        if old2 in xml:
            xml = xml.replace(old2, new2)
        else:
            raise ValueError(f"could not find title in slide{n}")
    else:
        xml = xml.replace(old, new)
    save(n, xml)
    print(f"slide{n} title shortened")
