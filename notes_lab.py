"""
Notes & Data Lab
----------------
* Notes with tags, plain or regular-expression search
* Text tools: extract e-mails / phone numbers from a text file, word frequency, regex pattern lab
* NumPy lab: 1-D / 2-D / 3-D temperature arrays (reshape, slice, index)
* Data lab: open any CSV with Pandas (head, columns, fill / drop missing values, groupby, mean/min/max)
"""
import re
import sqlite3
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

import tkinter as tk
from tkinter import ttk, filedialog

from hub_charts import BarChart, DonutChart
from hub_theme import add_field, card, clear_table, insert_row, make_table, titled_card

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)")
WORD_RE = re.compile(r"[a-z][a-z'-]+")
STOP = {"the", "and", "for", "that", "with", "this", "are", "was", "you", "have", "not", "from", "but", "his",
        "her", "they", "will", "your", "all", "can", "has", "had", "its", "our", "one", "out", "who"}

PATTERN_CASES = {   # the five regular-expression cases from the lab syllabus
    "Lines that start with 'This'": (r"^This", 0),
    "Same, upper or lower case": (r"^this", re.I),
    "Lines with consecutive 'te' (tete...)": (r"(?:te){2,}", 0),
    "Lines with a word starting with s and ending with e": (r"\bs\w*e\b", re.I),
    "Lines with a date like 1.2.26 / 12.10.26": (r"\b\d{1,2}\.\d{1,2}\.\d{2}\b", 0),
}


class NotesError(Exception):
    pass


# ======================= text tools (pure functions) =======================
def extract_contacts(text):
    """Returns (sorted e-mails, sorted phone numbers) found in text."""
    return sorted(set(EMAIL_RE.findall(text))), sorted(set(PHONE_RE.findall(text)))


def word_frequency(text, top=10):
    words = [w for w in WORD_RE.findall(text.lower()) if w not in STOP and len(w) > 2]
    return Counter(words).most_common(top)


def grep_lines(text, pattern, flags=0):
    """[(line number, line)] for lines where the regex matches; raises NotesError for a bad pattern."""
    try:
        rx = re.compile(pattern, flags)
    except re.error as err:
        raise NotesError(f"Invalid pattern: {err}") from None
    return [(i, line) for i, line in enumerate(text.splitlines(), 1) if rx.search(line)]


def numpy_lab(seed=7):
    """Temperature readings as 1-D, 2-D and 3-D NumPy arrays with reshaping, slicing and indexing."""
    rng = np.random.default_rng(seed)
    days = np.round(rng.uniform(24, 38, 7), 1)                                    # 1-D: one city, 7 days
    cities = np.round(rng.uniform(22, 40, (3, 7)), 1)                              # 2-D: 3 cities x 7 days
    weeks = np.round(rng.uniform(20, 42, (2, 3, 7)), 1)                            # 3-D: 2 weeks x 3 cities x 7 days
    names = ["Mumbai", "Pune", "Nagpur"]
    out = ["1-D ARRAY  daily temperatures", f"  {days}   shape={days.shape}",
           f"  hottest day index: {days.argmax()} ({days.max()} C)   mean: {days.mean():.1f} C",
           f"  first three days: {days[:3]}   every 2nd day: {days[::2]}", "",
           "2-D ARRAY  cities x days", str(cities), f"  shape={cities.shape}",
           f"  Pune, day 3 (indexing): {cities[1, 2]}",
           f"  weekend columns (slicing): {cities[:, 5:].tolist()}",
           "  mean per city: " + ", ".join(f"{n} {m:.1f}" for n, m in zip(names, cities.mean(axis=1))), "",
           "3-D ARRAY  weeks x cities x days", f"  shape={weeks.shape}   size={weeks.size}",
           f"  week 2, Mumbai: {weeks[1, 0]}",
           f"  weekly mean per city (axis=2):\n{weeks.mean(axis=2).round(1)}", "",
           "RESHAPE", f"  the 3-D array reshaped to (6, 7):\n{weeks.reshape(6, 7)}",
           f"  flattened length: {weeks.flatten().size}"]
    return "\n".join(out)


def sample_dataframe(seed=3):
    """Offline demo data (like a marks sheet) with a few missing values to clean."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({"student": [f"S{i:02d}" for i in range(1, 25)],
                       "branch": rng.choice(["CSE", "IT", "AIML"], 24),
                       "maths": rng.integers(35, 100, 24).astype(float),
                       "physics": rng.integers(30, 100, 24).astype(float),
                       "java": rng.integers(40, 100, 24).astype(float)})
    for column in ("maths", "physics", "java"):
        df.loc[rng.choice(24, 3, replace=False), column] = np.nan
    return df


# ======================= storage =======================
class NotesDB:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.execute("""CREATE TABLE IF NOT EXISTS notes(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT, tags TEXT, updated TEXT)""")
        self.con.commit()

    def save(self, note_id, title, body, tags):
        title = title.strip()
        if not title:
            raise NotesError("A note needs a title")
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        if note_id is None:
            cur = self.con.execute("INSERT INTO notes(title,body,tags,updated) VALUES (?,?,?,?)", (title, body, tags, stamp))
            note_id = cur.lastrowid
        else:
            self.con.execute("UPDATE notes SET title=?, body=?, tags=?, updated=? WHERE id=?", (title, body, tags, stamp, note_id))
        self.con.commit()
        return note_id

    def delete(self, note_id):
        self.con.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.con.commit()

    def all(self):
        return self.con.execute("SELECT id,title,body,tags,updated FROM notes ORDER BY updated DESC").fetchall()

    def search(self, query, use_regex=False):
        rows = self.all()
        if not query.strip():
            return rows
        if use_regex:
            try:
                rx = re.compile(query, re.I)
            except re.error as err:
                raise NotesError(f"Invalid pattern: {err}") from None
            return [r for r in rows if rx.search(f"{r[1]}\n{r[2] or ''}\n{r[3] or ''}")]
        needle = query.lower()
        return [r for r in rows if needle in f"{r[1]} {r[2] or ''} {r[3] or ''}".lower()]


# ======================= GUI =======================
class NotesPage(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.db = NotesDB(ctx.path("notes.db"))
        self.current_id = None
        self.df = None
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.build_notes_tab()
        self.build_text_tab()
        self.build_numpy_tab()
        self.build_data_tab()
        self.refresh_notes()

    def on_show(self):
        self.refresh_notes()

    def text_widget(self, parent, **kw):
        box = tk.Text(parent, wrap="word", font=("Consolas", 10), **kw)
        self.ctx.theme.recolor(box)
        return box

    def show(self, box, text):
        box.config(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.config(state="disabled")

    # ---------- notes ----------
    def build_notes_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F4DD Notes  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        left = card(tab)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self.v_search, self.v_regex = tk.StringVar(), tk.BooleanVar()
        search = ttk.Entry(left, textvariable=self.v_search, width=30)
        search.grid(row=0, column=0, sticky="ew")
        search.bind("<KeyRelease>", lambda event: self.refresh_notes())
        ttk.Checkbutton(left, text="Regex search", variable=self.v_regex, style="Card.TCheckbutton",
                        command=self.refresh_notes).grid(row=1, column=0, sticky="w", pady=4)
        frame, self.note_tree = make_table(left, [("id", "ID", 0, "w"), ("t", "Title", 180, "w"), ("u", "Updated", 110, "w")], height=16)
        self.note_tree.config(displaycolumns=("t", "u"))
        frame.grid(row=2, column=0, sticky="nsew")
        left.rowconfigure(2, weight=1)
        self.note_tree.bind("<<TreeviewSelect>>", lambda event: self.open_note())
        right = card(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)
        right.rowconfigure(2, weight=1)
        self.v_title, self.v_tags = tk.StringVar(), tk.StringVar()
        add_field(right, 0, "Title", ttk.Entry(right, textvariable=self.v_title))
        add_field(right, 1, "Tags", ttk.Entry(right, textvariable=self.v_tags))
        self.body = self.text_widget(right, height=14)
        self.body.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(6, 6))
        self.counter = ttk.Label(right, text="0 words", style="CardMuted.TLabel")
        self.counter.grid(row=3, column=0, sticky="w")
        self.body.bind("<KeyRelease>", lambda event: self.counter.config(text=f"{len(self.body.get('1.0', 'end').split())} words"))
        buttons = ttk.Frame(right, style="Card.TFrame")
        buttons.grid(row=3, column=1, sticky="e")
        ttk.Button(buttons, text="New", command=self.new_note).pack(side="left", padx=4)
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self.save_note).pack(side="left", padx=4)
        ttk.Button(buttons, text="Delete", style="Danger.TButton", command=self.delete_note).pack(side="left")

    def refresh_notes(self):
        try:
            rows = self.db.search(self.v_search.get(), self.v_regex.get())
        except NotesError as err:
            return self.ctx.toast(str(err), "error")
        clear_table(self.note_tree)
        for nid, title, _body, _tags, updated in rows:
            insert_row(self.note_tree, (nid, title, updated))

    def open_note(self):
        selection = self.note_tree.selection()
        if not selection:
            return
        note_id = self.note_tree.item(selection[0])["values"][0]
        for nid, title, body, tags, _ in self.db.all():
            if nid == note_id:
                self.current_id = nid
                self.v_title.set(title)
                self.v_tags.set(tags or "")
                self.body.delete("1.0", "end")
                self.body.insert("1.0", body or "")
                self.counter.config(text=f"{len((body or '').split())} words")

    def new_note(self):
        self.current_id = None
        self.v_title.set("")
        self.v_tags.set("")
        self.body.delete("1.0", "end")

    def save_note(self):
        try:
            self.current_id = self.db.save(self.current_id, self.v_title.get(), self.body.get("1.0", "end").strip(), self.v_tags.get().strip())
        except NotesError as err:
            return self.ctx.toast(str(err), "error")
        self.ctx.toast("Note saved", "success")
        self.refresh_notes()

    def delete_note(self):
        if self.current_id is not None:
            self.db.delete(self.current_id)
            self.new_note()
            self.refresh_notes()

    # ---------- text tools ----------
    def build_text_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F524 Text tools (regex)  ")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        left = card(tab)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="Paste text or open a file", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.source = self.text_widget(left, height=14)
        self.source.grid(row=1, column=0, sticky="nsew", pady=6)
        row = ttk.Frame(left, style="Card.TFrame")
        row.grid(row=2, column=0, sticky="ew")
        ttk.Button(row, text="Open .txt file", command=self.open_text_file).pack(side="left")
        ttk.Button(row, text="Emails & phones", style="Accent.TButton", command=self.run_contacts).pack(side="left", padx=6)
        ttk.Button(row, text="Word frequency", command=self.run_words).pack(side="left")
        lab = ttk.Frame(left, style="Card.TFrame")
        lab.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.v_case = tk.StringVar(value=list(PATTERN_CASES)[0])
        ttk.Combobox(lab, textvariable=self.v_case, values=list(PATTERN_CASES), state="readonly", width=44).pack(side="left")
        ttk.Button(lab, text="Run", command=self.run_case).pack(side="left", padx=6)
        custom = ttk.Frame(left, style="Card.TFrame")
        custom.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.v_pattern = tk.StringVar()
        ttk.Entry(custom, textvariable=self.v_pattern, width=40).pack(side="left")
        ttk.Button(custom, text="Your own regex", command=self.run_custom).pack(side="left", padx=6)
        right = card(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Result", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.result = self.text_widget(right, height=14)
        self.result.grid(row=1, column=0, sticky="nsew", pady=6)
        self.result.config(state="disabled")

    def open_text_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                content = fh.read()
        except FileNotFoundError:
            return self.ctx.toast("That file no longer exists", "error")
        except UnicodeDecodeError:
            return self.ctx.toast("Please use a UTF-8 text file", "error")
        except OSError as err:
            return self.ctx.toast(str(err), "error")
        self.source.delete("1.0", "end")
        self.source.insert("1.0", content)

    def source_text(self):
        return self.source.get("1.0", "end")

    def run_contacts(self):
        emails, phones = extract_contacts(self.source_text())
        self.show(self.result, f"E-MAILS ({len(emails)})\n" + "\n".join(emails or ["none"]) +
                  f"\n\nPHONE NUMBERS ({len(phones)})\n" + "\n".join(phones or ["none"]))

    def run_words(self):
        freq = word_frequency(self.source_text())
        self.show(self.result, "TOP WORDS\n" + "\n".join(f"{w:<16}{'#' * n} {n}" for w, n in freq) if freq else "No words found")

    def run_case(self):
        pattern, flags = PATTERN_CASES[self.v_case.get()]
        self.report_matches(pattern, flags)

    def run_custom(self):
        self.report_matches(self.v_pattern.get(), re.I)

    def report_matches(self, pattern, flags):
        try:
            hits = grep_lines(self.source_text(), pattern, flags)
        except NotesError as err:
            return self.ctx.toast(str(err), "error")
        self.show(self.result, f"Pattern: {pattern}\n{len(hits)} matching line(s)\n\n" +
                  "\n".join(f"{n:>3}: {line}" for n, line in hits))

    # ---------- numpy lab ----------
    def build_numpy_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F522 NumPy lab  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        ttk.Button(tab, text="Generate temperature arrays", style="Accent.TButton", command=self.run_numpy).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.numpy_out = self.text_widget(tab, height=20)
        self.numpy_out.grid(row=1, column=0, sticky="nsew")
        self.numpy_out.config(state="disabled")

    def run_numpy(self):
        self.show(self.numpy_out, numpy_lab(np.random.randint(1, 1000)))

    # ---------- data lab ----------
    def build_data_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F4CA Data lab (Pandas)  ")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        top = ttk.Frame(tab)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Button(top, text="Open CSV", style="Accent.TButton", command=self.open_csv).pack(side="left")
        ttk.Button(top, text="Use sample data", command=self.load_sample).pack(side="left", padx=6)
        self.data_info = ttk.Label(top, text="No data loaded", style="Muted.TLabel")
        self.data_info.pack(side="left", padx=10)
        ops = ttk.Frame(tab)
        ops.grid(row=1, column=0, sticky="ew", pady=8)
        for text, cmd in (("First 8 rows", self.op_head), ("Columns", self.op_columns), ("Missing values", self.op_missing),
                          ("Fill with mean", self.op_fill), ("Drop missing rows", self.op_drop), ("Describe", self.op_describe)):
            ttk.Button(ops, text=text, command=cmd).pack(side="left", padx=(0, 6))
        group = ttk.Frame(tab)
        group.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.v_group, self.v_value = tk.StringVar(), tk.StringVar()
        ttk.Label(group, text="Group by").pack(side="left")
        self.group_box = ttk.Combobox(group, textvariable=self.v_group, state="readonly", width=14)
        self.group_box.pack(side="left", padx=6)
        ttk.Label(group, text="Column").pack(side="left")
        self.value_box = ttk.Combobox(group, textvariable=self.v_value, state="readonly", width=14)
        self.value_box.pack(side="left", padx=6)
        ttk.Button(group, text="Mean / Min / Max", command=self.op_group).pack(side="left")
        self.data_out = self.text_widget(tab, height=9)
        self.data_out.grid(row=2, column=0, sticky="nsew")
        self.data_out.config(state="disabled")
        charts = ttk.Frame(tab)
        charts.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        charts.columnconfigure((0, 1), weight=1, uniform="dc")
        group_card = titled_card(charts, "CHART", "Average of the chosen column per group", grid=dict(row=0, column=0, sticky="nsew", padx=(0, 8)))
        group_card.columnconfigure(0, weight=1)
        self.group_chart = BarChart(group_card, self.ctx.theme, height=170)
        self.group_chart.grid(row=2, column=0, columnspan=3, sticky="nsew")
        hist_card = titled_card(charts, "DISTRIBUTION", "Histogram of the chosen column", grid=dict(row=0, column=1, sticky="nsew"))
        hist_card.columnconfigure(0, weight=1)
        self.hist_chart = BarChart(hist_card, self.ctx.theme, height=170)
        self.hist_chart.grid(row=2, column=0, columnspan=3, sticky="nsew")

    def set_frame(self, df, label):
        self.df = df
        numeric = list(df.select_dtypes("number").columns)
        self.group_box["values"] = list(df.columns)
        self.value_box["values"] = numeric
        self.v_group.set(df.columns[1] if len(df.columns) > 1 else df.columns[0])
        self.v_value.set(numeric[0] if numeric else "")
        self.data_info.config(text=f"{label}: {len(df)} rows x {len(df.columns)} columns")
        self.op_head()
        self.draw_histogram()
        self.group_chart.set([], [])

    def open_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            df = pd.read_csv(path)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as err:
            return self.ctx.toast(f"Could not read that CSV: {err}", "error")
        self.set_frame(df, path.split("/")[-1].split("\\")[-1])

    def load_sample(self):
        self.set_frame(sample_dataframe(), "Sample marks")

    def need_data(self):
        if self.df is None or self.df.empty:
            self.ctx.toast("Load a CSV or the sample data first", "warning")
            return False
        return True

    def op_head(self):
        if self.need_data():
            self.show(self.data_out, self.df.head(8).to_string())

    def op_columns(self):
        if self.need_data():
            self.show(self.data_out, "\n".join(f"{c:<20}{t}" for c, t in self.df.dtypes.astype(str).items()))

    def op_missing(self):
        if self.need_data():
            self.show(self.data_out, "Missing values per column\n" + self.df.isna().sum().to_string())

    def op_fill(self):
        if self.need_data():
            numeric = self.df.select_dtypes("number").columns
            self.df[numeric] = self.df[numeric].fillna(self.df[numeric].mean())
            self.show(self.data_out, "Missing numbers replaced by each column's mean.\n\n" + self.df.isna().sum().to_string())

    def op_drop(self):
        if self.need_data():
            before = len(self.df)
            self.df = self.df.dropna()
            self.show(self.data_out, f"Dropped {before - len(self.df)} rows with missing values. {len(self.df)} rows remain.")

    def op_describe(self):
        if self.need_data():
            self.show(self.data_out, self.df.describe().round(2).to_string())

    def op_group(self):
        if not self.need_data():
            return
        try:
            table = self.df.groupby(self.v_group.get())[self.v_value.get()].agg(["count", "mean", "min", "max"]).round(2)
        except (KeyError, TypeError, ValueError) as err:
            return self.ctx.toast(f"Pick a group column and a numeric column ({err})", "error")
        self.show(self.data_out, f"{self.v_value.get()} grouped by {self.v_group.get()}\n\n{table.to_string()}")
        self.group_chart.set([str(i)[:10] for i in table.index], [("Mean", [float(v) for v in table["mean"]]),
                                                                  ("Max", [float(v) for v in table["max"]])], fmt="{:,.2f}")
        self.draw_histogram()

    def draw_histogram(self):
        column = self.v_value.get()
        if self.df is None or column not in self.df.columns:
            return self.hist_chart.set([], [])
        values = self.df[column].dropna()
        if values.empty or not np.issubdtype(values.dtype, np.number):
            return self.hist_chart.set([], [])
        counts, edges = np.histogram(values, bins=min(10, max(4, int(np.sqrt(len(values))))))
        self.hist_chart.set([f"{e:.3g}" for e in edges[:-1]], [("Rows", [int(c) for c in counts])], fmt="{:g} rows")
