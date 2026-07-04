"""LegalDoc AI — standalone desktop app.
Hybrid RAG (FAISS + BM25) · fastembed ONNX embeddings · streaming LLM answers."""
import datetime
import os
import threading
import time
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

import customtkinter as ctk
import fitz  # PyMuPDF, for page-image preview
from PIL import Image, ImageTk

from rag_engine import HybridRAGEngine, extract_document, extract_key_facts
from llm_backend import (get_llm_client, stream_answer, stream_summary,
                         audit_clause, risk_score, warm_up,
                         COMPLIANCE_CLAUSES, AUDIT_QUERIES)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

STATUS_COLORS = {"PRESENT": "#2ecc71", "ABSENT": "#e74c3c", "RISK": "#f39c12"}
ACCENT = "#6db3f2"  # text highlights only — widgets use the stock theme

WELCOME = """
LegalDoc AI reads any legal document — contracts, NDAs, judgments, policies — and lets you:

   1.  PREVIEW    See the document pages plus auto-detected dates, amounts and deadlines
   2.  ASK        Chat with the document; answers stream in live with source citations
   3.  SUMMARIZE  One-click structured summary: parties, obligations, dates, risks
   4.  AUDIT      10 standard clauses checked and flagged PRESENT / ABSENT / RISK,
                  rolled into a 0-100 compliance health score
   5.  EXPORT     Generate a client-ready Word report of everything found

Everything runs locally on this machine — documents never leave your computer.

Open a PDF, DOCX or TXT file to begin  (try the samples in the test_docs folder).
"""


class LegalDocApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LegalDoc AI — Legal Document Intelligence")
        self.geometry("1280x800")
        self.minsize(1020, 640)

        self.engine: HybridRAGEngine | None = None
        self.doc_loaded = False
        self.ingesting = False
        self.ask_busy = False
        self.summary_busy = False
        self.audit_busy = False
        self.doc_name = ""
        self.doc_meta = {}
        self.key_facts = {}
        self.last_summary = ""
        self.last_audit = []
        self.chat_log = []  # (question, answer)
        self._page_photos = []  # keep refs so tkinter doesn't GC page images
        self._preview_gen = 0   # invalidates an in-flight render when a new doc opens

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_main()

        self._set_status("Starting AI engine...", spin=True)
        threading.Thread(target=self._init_engine, daemon=True).start()

    # ── Engine warm-up ────────────────────────────────────────────────────
    def _init_engine(self):
        try:
            engine = HybridRAGEngine()
            list(engine.embedder.embed(["warm up"]))  # first call loads the ONNX model
            self.engine = engine
            self.after(0, lambda: self._set_status("Ready — open a document to begin."))
            if "OpenAI" not in self.provider_var.get():
                warm_up(get_llm_client("ollama"), self.model_var.get())
        except Exception as e:
            self.after(0, lambda e=e: self._set_status(f"Engine failed: {e}"))

    # ── Sidebar ───────────────────────────────────────────────────────────
    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=290, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)

        ctk.CTkLabel(side, text="⚖️ LegalDoc AI", font=ctk.CTkFont(size=24, weight="bold")
                     ).pack(padx=22, pady=(26, 2), anchor="w")
        ctk.CTkLabel(side, text="Legal Document Intelligence", text_color="gray55"
                     ).pack(padx=22, pady=(0, 18), anchor="w")

        self.open_btn = ctk.CTkButton(side, text="Open Document…", height=40,
                                      font=ctk.CTkFont(size=14),
                                      command=self.open_document)
        self.open_btn.pack(padx=22, pady=(0, 8), fill="x")
        self.doc_label = ctk.CTkLabel(side, text="No document loaded", text_color="gray55",
                                      wraplength=240, justify="left")
        self.doc_label.pack(padx=22, pady=(0, 6), anchor="w")

        self.progress = ctk.CTkProgressBar(side, height=6)
        self.progress.set(0)
        self.progress.pack(padx=22, pady=(2, 16), fill="x")

        ctk.CTkLabel(side, text="AI MODEL", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray50").pack(padx=22, pady=(2, 4), anchor="w")
        self.provider_var = ctk.StringVar(value="Local (Free)")
        ctk.CTkSegmentedButton(side, values=["Local (Free)", "OpenAI API"],
                               variable=self.provider_var, height=32,
                               command=self._on_provider_change
                               ).pack(padx=22, pady=(0, 8), fill="x")
        self.model_var = ctk.StringVar(value="llama3.2:1b")
        self.model_entry = ctk.CTkEntry(side, textvariable=self.model_var, height=32)
        self.model_entry.pack(padx=22, pady=(0, 8), fill="x")

        self.api_key_var = ctk.StringVar(value="")
        self.api_key_entry = ctk.CTkEntry(side, textvariable=self.api_key_var, show="*",
                                          placeholder_text="OpenAI API key", height=32)

        self.export_btn = ctk.CTkButton(side, text="Export Word Report", height=38,
                                        fg_color="#2d6a4f", hover_color="#1b4332",
                                        font=ctk.CTkFont(size=13),
                                        command=self.export_report, state="disabled")
        self.export_btn.pack(padx=22, pady=(16, 6), fill="x")

        ctk.CTkLabel(side, text="v2.0 · Hybrid RAG Engine", text_color="gray40",
                     font=ctk.CTkFont(size=11)).pack(side="bottom", padx=22, pady=(0, 12), anchor="w")
        self.status_label = ctk.CTkLabel(side, text="", wraplength=240, justify="left",
                                         text_color=ACCENT)
        self.status_label.pack(side="bottom", padx=22, pady=(18, 6), anchor="w")

    def _on_provider_change(self, choice):
        if "OpenAI" in choice:
            self.api_key_entry.pack(padx=22, pady=(0, 8), fill="x", after=self.model_entry)
            if self.model_var.get().startswith("llama"):
                self.model_var.set("gpt-4o-mini")
        else:
            self.api_key_entry.pack_forget()
            if self.model_var.get().startswith("gpt"):
                self.model_var.set("llama3.2:1b")

    def _set_status(self, text, spin=False):
        self.status_label.configure(text=text)

    def _on_bm25_change(self, v):
        kw = int(round(float(v) * 100))
        suffix = "  (default)" if kw == 30 else ""
        self.bm25_label.configure(text=f"{kw}% keyword / {100 - kw}% meaning{suffix}")

    def _on_topk_change(self, v):
        k = int(float(v))
        suffix = "  (default)" if k == 5 else ""
        self.topk_label.configure(text=f"{k}{suffix}")

    # ── Document page preview ─────────────────────────────────────────────
    MAX_PREVIEW_PAGES = 30
    PAGE_WIDTH = 720

    def _on_preview_scroll(self, event):
        self.preview_canvas.yview_scroll(int(-event.delta / 120) * 3, "units")

    def _show_text_preview(self, text):
        self._preview_gen += 1
        self.preview_canvas.grid_forget()
        self.preview_scroll.grid_forget()
        self.preview_box.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("end", text)
        self.preview_box.configure(state="disabled")

    def _show_pdf_preview(self, pdf_bytes):
        self._preview_gen += 1
        gen = self._preview_gen
        self.preview_box.grid_forget()
        self.preview_canvas.delete("all")
        self._page_photos.clear()
        self.preview_canvas.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        self.preview_scroll.grid(row=0, column=1, sticky="ns", pady=4)
        self.preview_canvas.yview_moveto(0)
        threading.Thread(target=self._render_pdf_worker, args=(pdf_bytes, gen),
                         daemon=True).start()

    def _render_pdf_worker(self, pdf_bytes, gen):
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            n = min(doc.page_count, self.MAX_PREVIEW_PAGES)
            xc = self.PAGE_WIDTH // 2 + 20
            y = 16
            for i in range(n):
                if gen != self._preview_gen:
                    return  # a newer document replaced this preview
                page = doc.load_page(i)
                scale = self.PAGE_WIDTH / page.rect.width
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                h = pix.height

                def add(img=img, y=y, i=i, h=h):
                    if gen != self._preview_gen:
                        return
                    photo = ImageTk.PhotoImage(img)
                    self._page_photos.append(photo)
                    self.preview_canvas.create_image(xc, y, image=photo, anchor="n")
                    self.preview_canvas.create_text(
                        xc, y + h + 12, text=f"Page {i + 1} of {doc.page_count}",
                        fill="#8a8a8a", font=("Segoe UI", 9))
                    self.preview_canvas.configure(
                        scrollregion=(0, 0, self.PAGE_WIDTH + 40, y + h + 44))
                self.after(0, add)
                y += h + 44
            if doc.page_count > n:
                def note(y=y):
                    if gen != self._preview_gen:
                        return
                    self.preview_canvas.create_text(
                        xc, y + 8,
                        text=f"Preview shows the first {n} pages — "
                             f"all {doc.page_count} pages are indexed and searchable",
                        fill="#9a9a9a", font=("Segoe UI", 10))
                    self.preview_canvas.configure(
                        scrollregion=(0, 0, self.PAGE_WIDTH + 40, y + 44))
                self.after(0, note)
        except Exception:
            pass  # preview is cosmetic; never crash the app over it

    def _set_progress(self, frac, msg=None):
        self.progress.set(frac)
        if msg:
            self._set_status(msg)

    # ── Main area ─────────────────────────────────────────────────────────
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=(4, 12), pady=8)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(main, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 2))
        self.header = ctk.CTkLabel(header, text="",
                                   font=ctk.CTkFont(size=19, weight="bold"), anchor="w")
        self.header.pack(side="left")
        self.chips = ctk.CTkFrame(header, fg_color="transparent")
        self.chips.pack(side="left", padx=12)

        # Tabs are hidden until a document is loaded; the landing view shows first
        self.tabs = ctk.CTkTabview(main)
        for name in ("Preview", "Ask", "Summary", "Audit"):
            self.tabs.add(name)
        self._build_landing(main)

        # Preview tab — real document pages (PDF) or plain text (DOCX/TXT)
        pv = self.tabs.tab("Preview")
        pv.grid_columnconfigure(0, weight=3)
        pv.grid_columnconfigure(1, weight=1)
        pv.grid_rowconfigure(0, weight=1)

        self.preview_area = ctk.CTkFrame(pv)
        self.preview_area.grid(row=0, column=0, sticky="nsew", padx=(6, 3), pady=6)
        self.preview_area.grid_columnconfigure(0, weight=1)
        self.preview_area.grid_rowconfigure(0, weight=1)

        self.preview_box = ctk.CTkTextbox(self.preview_area, wrap="word",
                                          font=ctk.CTkFont(size=13), fg_color="transparent")
        self.preview_box.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)
        self.preview_box.insert("end", WELCOME)
        self.preview_box.configure(state="disabled")

        self.preview_canvas = tk.Canvas(self.preview_area, bg="#2b2b2b",
                                        highlightthickness=0, bd=0)
        self.preview_scroll = ctk.CTkScrollbar(self.preview_area,
                                               command=self.preview_canvas.yview)
        self.preview_canvas.configure(yscrollcommand=self.preview_scroll.set)
        self.preview_canvas.bind("<Enter>", lambda e: self.preview_canvas.bind_all(
            "<MouseWheel>", self._on_preview_scroll))
        self.preview_canvas.bind("<Leave>", lambda e: self.preview_canvas.unbind_all(
            "<MouseWheel>"))

        self.facts_frame = ctk.CTkScrollableFrame(pv, label_text="Key facts detected")
        self.facts_frame.grid(row=0, column=1, sticky="nsew", padx=(3, 6), pady=6)

        # Ask tab
        qa = self.tabs.tab("Ask")
        qa.grid_columnconfigure(0, weight=1)
        qa.grid_rowconfigure(1, weight=1)

        tune = ctk.CTkFrame(qa, fg_color="transparent")
        tune.grid(row=0, column=0, columnspan=2, sticky="ew", padx=6, pady=(6, 2))
        self.bm25_var = ctk.DoubleVar(value=0.3)
        self.topk_var = ctk.IntVar(value=5)
        ctk.CTkLabel(tune, text="Search mix:", font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(side="left", padx=(12, 8), pady=8)
        ctk.CTkSlider(tune, from_=0.0, to=1.0, number_of_steps=20, variable=self.bm25_var,
                      width=170, command=self._on_bm25_change).pack(side="left", pady=8)
        self.bm25_label = ctk.CTkLabel(tune, text="30% keyword / 70% meaning  (default)",
                                       text_color="gray60")
        self.bm25_label.pack(side="left", padx=(10, 24))
        ctk.CTkLabel(tune, text="Sources:", font=ctk.CTkFont(size=12, weight="bold")
                     ).pack(side="left", padx=(0, 8))
        ctk.CTkSlider(tune, from_=3, to=10, number_of_steps=7, variable=self.topk_var,
                      width=120, command=self._on_topk_change).pack(side="left", pady=8)
        self.topk_label = ctk.CTkLabel(tune, text="5  (default)", text_color="gray60")
        self.topk_label.pack(side="left", padx=(10, 12))

        self.chat_box = ctk.CTkTextbox(qa, wrap="word", font=ctk.CTkFont(size=14))
        self.chat_box.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        self.chat_box.tag_config("you", foreground=ACCENT)
        self.chat_box.tag_config("dim", foreground="#8a8a8a")
        self.chat_box.configure(state="disabled")
        self.qa_entry = ctk.CTkEntry(qa, placeholder_text=
                                     "e.g.  What is the termination notice period?", height=40,
                                     font=ctk.CTkFont(size=14))
        self.qa_entry.grid(row=2, column=0, sticky="ew", padx=(6, 4), pady=(0, 6))
        self.qa_entry.bind("<Return>", lambda e: self.send_question())
        self.send_btn = ctk.CTkButton(qa, text="Ask", width=96, height=40,
                                      font=ctk.CTkFont(size=14),
                                      command=self.send_question)
        self.send_btn.grid(row=2, column=1, padx=(0, 6), pady=(0, 6))

        # Summary tab
        sm = self.tabs.tab("Summary")
        sm.grid_columnconfigure(0, weight=1)
        sm.grid_rowconfigure(1, weight=1)
        self.summary_btn = ctk.CTkButton(sm, text="Generate Summary", height=38,
                                         font=ctk.CTkFont(size=14),
                                         command=self.run_summary)
        self.summary_btn.grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.summary_box = ctk.CTkTextbox(sm, wrap="word", font=ctk.CTkFont(size=14))
        self.summary_box.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self.summary_box.configure(state="disabled")

        # Audit tab
        au = self.tabs.tab("Audit")
        au.grid_columnconfigure(0, weight=1)
        au.grid_rowconfigure(2, weight=1)
        top = ctk.CTkFrame(au, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=6)
        self.audit_btn = ctk.CTkButton(top, text="Run Compliance Audit", height=38,
                                       font=ctk.CTkFont(size=14),
                                       command=self.run_audit)
        self.audit_btn.pack(side="left")
        self.score_label = ctk.CTkLabel(top, text="", font=ctk.CTkFont(size=26, weight="bold"))
        self.score_label.pack(side="right", padx=12)
        self.audit_counts = ctk.CTkLabel(au, text="", font=ctk.CTkFont(size=14, weight="bold"))
        self.audit_counts.grid(row=1, column=0, padx=10, pady=(0, 4), sticky="w")
        self.audit_frame = ctk.CTkScrollableFrame(au, fg_color="transparent")
        self.audit_frame.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))

    # ── Landing view ──────────────────────────────────────────────────────
    def _build_landing(self, parent):
        self.landing = ctk.CTkFrame(parent, fg_color="transparent")
        self.landing.grid(row=1, column=0, sticky="nsew")

        box = ctk.CTkFrame(self.landing, fg_color="transparent")
        box.place(relx=0.5, rely=0.46, anchor="center")

        ctk.CTkLabel(box, text="⚖️", font=ctk.CTkFont(size=52)).pack()
        ctk.CTkLabel(box, text="LegalDoc AI",
                     font=ctk.CTkFont(size=34, weight="bold")).pack(pady=(2, 2))
        ctk.CTkLabel(box, text="Read, question and audit any legal document — privately, on this machine.",
                     text_color="gray60", font=ctk.CTkFont(size=15)).pack(pady=(0, 20))

        cards = ctk.CTkFrame(box, fg_color="transparent")
        cards.pack()
        feats = [
            ("📄", "Preview", "The real pages, plus dates,\namounts and deadlines"),
            ("💬", "Ask", "Chat with the document —\nanswers stream with sources"),
            ("📝", "Summary", "Parties, obligations, dates\nand risks in one click"),
            ("🔍", "Audit", "10 standard clauses checked,\nscored 0–100"),
            ("📤", "Report", "Client-ready Word report\nof everything found"),
        ]
        for i, (ic, t, d) in enumerate(feats):
            card = ctk.CTkFrame(cards, width=200, height=118, corner_radius=12)
            card.grid(row=i // 3, column=i % 3, padx=7, pady=7)
            card.grid_propagate(False)
            ctk.CTkLabel(card, text=f"{ic}  {t}",
                         font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(20, 2))
            ctk.CTkLabel(card, text=d, text_color="gray60",
                         font=ctk.CTkFont(size=12), justify="center").pack()

        ctk.CTkButton(box, text="Open a Document", height=44, width=260,
                      font=ctk.CTkFont(size=15),
                      command=self.open_document).pack(pady=(24, 8))
        ctk.CTkLabel(box, text="PDF · DOCX · TXT      Nothing leaves your computer.",
                     text_color="gray50", font=ctk.CTkFont(size=12)).pack()

    def _show_workspace(self):
        if self.landing.winfo_ismapped():
            self.landing.grid_forget()
            self.tabs.grid(row=1, column=0, sticky="nsew")

    # ── Progress-bar motion & background model warm-up ────────────────────
    def _pulse_start(self):
        """Indeterminate 'working' animation so the app never looks frozen."""
        self.progress.configure(mode="indeterminate")
        self.progress.start()

    def _pulse_stop(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)

    def _warm_model_async(self):
        """Load the local model into RAM ahead of the first Summary/Audit/Ask,
        so those actions respond in ~2-3s instead of ~14s on a cold model."""
        if "OpenAI" in self.provider_var.get():
            return
        model = self.model_var.get().strip()

        def worker():
            try:
                warm_up(get_llm_client("ollama"), model)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    # ── Client ────────────────────────────────────────────────────────────
    def _client_and_model(self):
        model = self.model_var.get().strip()
        if "OpenAI" in self.provider_var.get():
            key = self.api_key_var.get().strip()
            if not key:
                raise ValueError("Enter your OpenAI API key in the sidebar, or switch to Ollama.")
            os.environ["OPENAI_API_KEY"] = key
            return get_llm_client("openai"), model
        return get_llm_client("ollama"), model

    def _require_doc(self, running: bool = False) -> bool:
        if self.ingesting or running:
            return False
        if not self.doc_loaded:
            messagebox.showinfo("LegalDoc AI", "Open a document first — sidebar → Open Document.")
            return False
        return True

    def _fail(self, err):
        msg = str(err)
        if "connect" in msg.lower():
            msg += "\n\nOllama doesn't appear to be running. Start the Ollama app and try again."
        self.ingesting = self.ask_busy = self.summary_busy = self.audit_busy = False
        self.progress.set(0)
        self._set_status("Error — see popup.")
        messagebox.showerror("LegalDoc AI", msg)

    # ── Document loading ──────────────────────────────────────────────────
    def open_document(self):
        if self.ingesting or self.ask_busy or self.summary_busy or self.audit_busy:
            return
        path = filedialog.askopenfilename(
            title="Open legal document",
            filetypes=[("Documents", "*.pdf *.docx *.txt"), ("All files", "*.*")])
        if not path:
            return
        self.ingesting = True
        self.open_btn.configure(state="disabled")
        threading.Thread(target=self._ingest_worker, args=(path,), daemon=True).start()

    def _ingest_worker(self, path):
        try:
            while self.engine is None:
                time.sleep(0.2)
            t0 = time.time()
            with open(path, "rb") as f:
                data = f.read()
            self.after(0, lambda: self._set_progress(0.02, "Extracting text..."))
            meta = extract_document(data, os.path.basename(path))
            if not meta["text"].strip():
                raise ValueError("No text could be extracted from this file. "
                                 "If it is a scanned PDF, it needs OCR first.")
            facts = extract_key_facts(meta["text"])

            def cb(frac, msg):
                self.after(0, lambda: self._set_progress(frac, msg))
            cached = self.engine.ingest(meta["text"],
                                        progress_cb=cb,
                                        cache_key=HybridRAGEngine.cache_key_for(data))
            elapsed = time.time() - t0
            name = os.path.basename(path)

            def done():
                self.ingesting = False
                self.doc_loaded = True
                self.doc_name = name
                self.doc_meta = meta
                self.key_facts = facts
                self.last_summary = ""
                self.last_audit = []
                self.chat_log = []
                self.open_btn.configure(state="normal")
                self.export_btn.configure(state="normal")
                self._show_workspace()
                self.header.configure(text=f"📄 {name}")
                for w in self.chips.winfo_children():
                    w.destroy()
                chip_items = ([f"{meta['pages']} pages"] if meta["pages"] else [])
                chip_items += [f"{meta['words']:,} words",
                               f"{len(self.engine.chunks):,} chunks",
                               f"⚡ cached · {elapsed:.1f}s" if cached
                               else f"indexed in {elapsed:.1f}s"]
                for t in chip_items:
                    ctk.CTkLabel(self.chips, text=f"  {t}  ", corner_radius=9, height=24,
                                 fg_color="#26282c", text_color="#9fa6ad",
                                 font=ctk.CTkFont(size=11)).pack(side="left", padx=4)
                self.doc_label.configure(text=f"✅ {name}", text_color="#2ecc71")
                self._set_status("Document ready. Try the Ask, Summary or Audit tabs.")
                self._warm_model_async()  # preload the model so actions feel instant
                # Preview: real pages for PDFs, plain text for DOCX/TXT
                if name.lower().endswith(".pdf"):
                    self._show_pdf_preview(data)
                else:
                    self._show_text_preview(meta["text"][:60000])
                self.after(1500, lambda: self.progress.set(0))
                # Key facts
                for w in self.facts_frame.winfo_children():
                    w.destroy()
                for cat, items in facts.items():
                    if not items:
                        continue
                    ctk.CTkLabel(self.facts_frame, text=cat.upper(),
                                 font=ctk.CTkFont(size=11, weight="bold"),
                                 text_color="gray50").pack(anchor="w", padx=6, pady=(8, 0))
                    for it in items:
                        ctk.CTkLabel(self.facts_frame, text=f"• {it}", anchor="w",
                                     wraplength=210, justify="left").pack(anchor="w", padx=10)
                # Clear old outputs
                for box in (self.chat_box, self.summary_box):
                    box.configure(state="normal")
                    box.delete("1.0", "end")
                    box.configure(state="disabled")
                for w in self.audit_frame.winfo_children():
                    w.destroy()
                self.score_label.configure(text="")
                self.audit_counts.configure(text="")
                self.tabs.set("Preview")
            self.after(0, done)
        except Exception as e:
            self.after(0, lambda e=e: (self.open_btn.configure(state="normal"), self._fail(e)))

    # ── Streaming helper ──────────────────────────────────────────────────
    def _stream_into(self, box, generator, on_done=None, prefix="", on_first=None):
        """Feed a token generator into a textbox live. on_first() runs once,
        the moment the first token arrives (used to clear a placeholder)."""
        if prefix:
            self.after(0, lambda: self._append(box, prefix))
        buf = []
        collected = []
        seen = [False]
        last_flush = time.time()

        def flush():
            if buf:
                text = "".join(buf)
                buf.clear()
                self.after(0, lambda t=text: self._append(box, t))
        try:
            for delta in generator:
                if not seen[0]:
                    seen[0] = True
                    if on_first:
                        self.after(0, on_first)
                buf.append(delta)
                collected.append(delta)
                if time.time() - last_flush > 0.08:
                    flush()
                    last_flush = time.time()
            flush()
            if on_done:
                self.after(0, lambda: on_done("".join(collected)))
        except Exception as e:
            self.after(0, lambda e=e: self._fail(e))

    def _append(self, box, text, tag=None):
        box.configure(state="normal")
        if tag:
            box.insert("end", text, tag)
        else:
            box.insert("end", text)
        box.see("end")
        box.configure(state="disabled")

    # ── Ask ───────────────────────────────────────────────────────────────
    def send_question(self):
        if not self._require_doc(self.ask_busy):
            return
        query = self.qa_entry.get().strip()
        if not query:
            return
        self.qa_entry.delete(0, "end")
        self.ask_busy = True
        self.send_btn.configure(state="disabled")
        self._append(self.chat_box, f"You  ▸  {query}\n\n", "you")
        self._append(self.chat_box, "AI  ▸  ")
        self._set_status("Searching document + generating answer...")
        threading.Thread(target=self._qa_worker, args=(query,), daemon=True).start()

    def _qa_worker(self, query):
        try:
            t0 = time.time()
            results = self.engine.hybrid_retrieve(
                query, top_k=int(self.topk_var.get()), bm25_weight=float(self.bm25_var.get()))
            t_ret = (time.time() - t0) * 1000
            client, model = self._client_and_model()
            gen = stream_answer(client, model, query, results)

            def finish(full_answer):
                srcs = "\n".join(
                    f"    [{i + 1}]  {r['chunk'][:90].strip()}...   (relevance {r['score']})"
                    for i, r in enumerate(results[:3]))
                self._append(self.chat_box,
                             f"\n\nSources — {len(results)} passages found in {t_ret:.0f} ms:\n"
                             f"{srcs}\n\n{'·' * 80}\n\n", "dim")
                self.chat_log.append((query, full_answer))
                self.ask_busy = False
                self.send_btn.configure(state="normal")
                self._set_status("Ready.")
            self._stream_into(self.chat_box, gen, on_done=finish)
        except Exception as e:
            self.after(0, lambda e=e: (self.send_btn.configure(state="normal"), self._fail(e)))

    # ── Summary ───────────────────────────────────────────────────────────
    def run_summary(self):
        if not self._require_doc(self.summary_busy):
            return
        self.summary_busy = True
        self.summary_btn.configure(state="disabled", text="Generating…")
        self.summary_box.configure(state="normal")
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("end", "Reading the document and writing a summary…")
        self.summary_box.configure(state="disabled")
        self._set_status("Generating summary (streams in live)...")
        self._pulse_start()

        def worker():
            try:
                client, model = self._client_and_model()
                gen = stream_summary(client, model, self.engine.get_all_text())
                self._first_token = True

                def on_delta():
                    if getattr(self, "_first_token", False):
                        self._first_token = False
                        self._pulse_stop()
                        self.summary_box.configure(state="normal")
                        self.summary_box.delete("1.0", "end")
                        self.summary_box.configure(state="disabled")

                def finish(full):
                    self.last_summary = full
                    self.summary_busy = False
                    self._pulse_stop()
                    self.summary_btn.configure(state="normal", text="Generate Summary")
                    self._set_status("Summary complete.")
                self._stream_into(self.summary_box, gen, on_done=finish, on_first=on_delta)
            except Exception as e:
                self.after(0, lambda e=e: (self._pulse_stop(),
                           self.summary_btn.configure(state="normal", text="Generate Summary"),
                           self._fail(e)))
        threading.Thread(target=worker, daemon=True).start()

    # ── Audit ─────────────────────────────────────────────────────────────
    def run_audit(self):
        if not self._require_doc(self.audit_busy):
            return
        self.audit_busy = True
        self.audit_btn.configure(state="disabled", text="Auditing…")
        self._set_status("Auditing 10 standard clauses...")
        self._pulse_start()

        for w in self.audit_frame.winfo_children():
            w.destroy()
        self.score_label.configure(text="")
        self.audit_counts.configure(text="Preparing audit…")

        def add_row(r):
            status = r.get("status", "?")
            c = STATUS_COLORS.get(status, "gray70")
            row = ctk.CTkFrame(self.audit_frame, corner_radius=8)
            row.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(row, text=status, width=94, height=26, corner_radius=13,
                         fg_color=c, text_color="#101010",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=10, pady=10)
            body = ctk.CTkFrame(row, fg_color="transparent")
            body.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
            ctk.CTkLabel(body, text=r.get("clause", "?"), anchor="w",
                         font=ctk.CTkFont(size=14, weight="bold")).pack(fill="x")
            ctk.CTkLabel(body, text=r.get("detail", ""), anchor="w", justify="left",
                         wraplength=780, text_color="gray70").pack(fill="x")

        def worker():
            try:
                client, model = self._client_and_model()
                results = []
                total = len(COMPLIANCE_CLAUSES)
                self._audit_first = True
                for i, clause in enumerate(COMPLIANCE_CLAUSES):
                    self.after(0, lambda i=i, cl=clause: (
                        self.audit_counts.configure(text=f"Checking clause {i + 1} of {total}:  {cl}")))
                    query = AUDIT_QUERIES.get(clause, clause)
                    chunks = self.engine.hybrid_retrieve(query, top_k=3, bm25_weight=0.5)
                    r = audit_clause(client, model, clause, chunks)
                    results.append(r)

                    def show(r=r, i=i):
                        if self._audit_first:
                            self._audit_first = False
                            self._pulse_stop()  # first result in — switch to real progress
                        self.progress.set((i + 1) / total)
                        add_row(r)
                    self.after(0, show)

                score = risk_score(results)

                def done():
                    self.audit_busy = False
                    self.audit_btn.configure(state="normal", text="Run Compliance Audit")
                    self.last_audit = results
                    self.progress.set(1.0)
                    p = sum(1 for r in results if r.get("status") == "PRESENT")
                    a = sum(1 for r in results if r.get("status") == "ABSENT")
                    k = sum(1 for r in results if r.get("status") == "RISK")
                    color = "#2ecc71" if score >= 75 else "#f39c12" if score >= 45 else "#e74c3c"
                    self.score_label.configure(text=f"Health: {score}/100", text_color=color)
                    self.audit_counts.configure(
                        text=f"🟢 Present {p}     🟡 Risk {k}     🔴 Absent {a}")
                    self._set_status("Audit complete.")
                    self.after(1500, lambda: self.progress.set(0))
                self.after(0, done)
            except Exception as e:
                self.after(0, lambda e=e: (self._pulse_stop(),
                           self.audit_btn.configure(state="normal", text="Run Compliance Audit"),
                           self._fail(e)))
        threading.Thread(target=worker, daemon=True).start()

    # ── Export ────────────────────────────────────────────────────────────
    def export_report(self):
        if not self.doc_loaded or self.ingesting:
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".docx", initialfile=f"LegalDocAI_Report_{self.doc_name.rsplit('.',1)[0]}.docx",
            filetypes=[("Word document", "*.docx")])
        if not path:
            return
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
            doc = Document()
            doc.add_heading("LegalDoc AI — Analysis Report", 0)
            doc.add_paragraph(f"Document: {self.doc_name}")
            doc.add_paragraph(f"Generated: {datetime.datetime.now():%d %B %Y, %H:%M}")
            pages = self.doc_meta.get("pages")
            doc.add_paragraph(f"Size: {f'{pages} pages, ' if pages else ''}"
                              f"{self.doc_meta.get('words', 0):,} words")

            doc.add_heading("Key Facts Detected", 1)
            for cat, items in self.key_facts.items():
                if items:
                    doc.add_paragraph(f"{cat}: " + ", ".join(items))

            if self.last_summary:
                doc.add_heading("Document Summary", 1)
                doc.add_paragraph(self.last_summary)

            if self.last_audit:
                doc.add_heading("Compliance Audit", 1)
                doc.add_paragraph(f"Compliance health score: {risk_score(self.last_audit)}/100")
                table = doc.add_table(rows=1, cols=3)
                table.style = "Light Grid Accent 1"
                hdr = table.rows[0].cells
                hdr[0].text, hdr[1].text, hdr[2].text = "Clause", "Status", "Detail"
                for r in self.last_audit:
                    row = table.add_row().cells
                    row[0].text = r.get("clause", "")
                    row[1].text = r.get("status", "")
                    row[2].text = r.get("detail", "")

            if self.chat_log:
                doc.add_heading("Q&A Session", 1)
                for q, a in self.chat_log:
                    doc.add_paragraph(f"Q: {q}", style="Intense Quote")
                    doc.add_paragraph(a)

            doc.save(path)
            self._set_status(f"Report saved: {os.path.basename(path)}")
            messagebox.showinfo("LegalDoc AI", f"Report exported:\n{path}")
        except Exception as e:
            self._fail(e)


if __name__ == "__main__":
    app = LegalDocApp()
    app.mainloop()
