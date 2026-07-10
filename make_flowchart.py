"""Simple, plain-language flowchart of how LegalDoc AI works, for the PBL report."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

W, H = 13.5, 8.6
fig, ax = plt.subplots(figsize=(W, H), dpi=200)
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")

BLUE, BLUE_L = "#2f6ad0", "#eaf1fc"
GREEN, GREEN_L = "#2d6a4f", "#e8f5ee"
AMBER, AMBER_L = "#b8860b", "#fdf3e0"
GRAY = "#444444"


def box(x, y, w, h, text, fc, ec, fs=12):
    FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.12",
                    linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=2).__class__
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08,rounding_size=0.12",
                        linewidth=1.6, edgecolor=ec, facecolor=fc, zorder=2)
    ax.add_patch(b)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
             fontsize=fs, color="#111111", zorder=3, linespacing=1.4)
    return {"x": x, "y": y, "w": w, "h": h}


def anchor(b, side):
    if side == "right":
        return (b["x"] + b["w"], b["y"] + b["h"] / 2)
    if side == "left":
        return (b["x"], b["y"] + b["h"] / 2)
    if side == "top":
        return (b["x"] + b["w"] / 2, b["y"] + b["h"])
    if side == "bottom":
        return (b["x"] + b["w"] / 2, b["y"])


def arrow(b1, side1, b2, side2, color=GRAY):
    p1, p2 = anchor(b1, side1), anchor(b2, side2)
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=16,
                                  linewidth=1.6, color=color, zorder=1,
                                  shrinkA=0, shrinkB=0))


ax.text(W / 2, H - 0.35, "How LegalDoc AI Reads and Answers Questions About a Document",
        ha="center", va="center", fontsize=15, weight="bold", color="#111111")

TOP = H - 2.05
b_upload = box(0.4, TOP, 2.7, 1.1, "1. Upload Document\n(PDF / Word / Text)", BLUE_L, BLUE)
b_split = box(3.6, TOP, 2.7, 1.1, "2. Read the Text &\nSplit into Small Chunks", BLUE_L, BLUE)
arrow(b_upload, "right", b_split, "left")

b_meaning = box(7.35, TOP + 0.35, 2.9, 0.85, "3a. Search by MEANING\n(understands the idea)", GREEN_L, GREEN, fs=10.5)
b_exact = box(7.35, TOP - 0.75, 2.9, 0.85, "3b. Search by EXACT WORDS\n(catches precise legal terms)", GREEN_L, GREEN, fs=10.5)
arrow(b_split, "right", b_meaning, "left")
arrow(b_split, "right", b_exact, "left")

b_combine = box(10.6, TOP, 2.5, 1.1, "4. Combine Both\nResults Together", BLUE_L, BLUE, fs=11)
arrow(b_meaning, "right", b_combine, "left")
arrow(b_exact, "right", b_combine, "left")

ROW2 = TOP - 1.6
b_top = box(10.6, ROW2, 2.5, 1.0, "5. Keep Only the Most\nRelevant Passages", AMBER_L, AMBER, fs=10.5)
arrow(b_combine, "bottom", b_top, "top")

b_llm = box(7.35, ROW2, 2.9, 1.0, "6. Send Passages + Your\nQuestion to the AI Model", AMBER_L, AMBER, fs=10.5)
arrow(b_top, "left", b_llm, "right")

b_answer = box(3.6, ROW2, 2.7, 1.0, "7. AI Writes an Answer,\nStreamed Live", BLUE_L, BLUE, fs=11)
arrow(b_llm, "left", b_answer, "right")

b_src = box(0.4, ROW2, 2.7, 1.0, "8. The Passages Used\nAre Shown as “Sources”", GREEN_L, GREEN, fs=10.5)
arrow(b_answer, "left", b_src, "right")

label_y = ROW2 - 0.75
ax.text(W / 2, label_y, "The same search-and-answer engine also powers:",
        ha="center", va="center", fontsize=11.5, weight="bold", color="#333333")

outs = [
    ("Summary\nOne-click document\noverview", BLUE_L, BLUE),
    ("Compliance Audit\n10 clauses checked,\nbenchmarked vs. 510\nreal contracts (CUAD)", GREEN_L, GREEN),
    ("Fairness Analysis\nHow balanced is\nthe contract, and\nwho does it favor?", AMBER_L, AMBER),
    ("Negotiation Practice\nAI plays opposing\ncounsel so you can\nrehearse", BLUE_L, BLUE),
]
ow, gap = 2.9, 0.35
total = ow * 4 + gap * 3
sx = (W - total) / 2
OUT_Y = label_y - 1.75
out_boxes = []
for i, (label, fc, ec) in enumerate(outs):
    bx = sx + i * (ow + gap)
    b = box(bx, OUT_Y, ow, 1.4, label, fc, ec, fs=10)
    out_boxes.append(b)

for b in out_boxes:
    top = anchor(b, "top")
    start = (top[0], label_y - 0.2)
    ax.add_patch(FancyArrowPatch(start, top, arrowstyle="-|>", mutation_scale=14,
                                  linewidth=1.4, color=GRAY, zorder=1, shrinkA=0, shrinkB=0))

ax.set_ylim(OUT_Y - 0.3, H)
plt.tight_layout()
plt.savefig(r"C:\Users\aditm\Desktop\LegalDocAI\flowchart.png", facecolor="white", bbox_inches="tight")
print("saved")
