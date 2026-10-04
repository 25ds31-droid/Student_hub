"""
Best-Book Finder
----------------
Type a topic -> the app searches Open Library and Google Books over the internet, merges the
results, and ranks them with a transparent score:

    score = 45% quality   (Bayesian average of star ratings, so 5 stars from 1 reader is not trusted)
          + 30% relevance (how well title/subjects match your topic)
          + 25% popularity (readers who shelved it + number of editions, log-scaled)

* Searching runs on a background thread so the window never freezes
* Results are cached in SQLite, so a repeated search also works offline
* "My library" is a reading list managed with a Python dictionary (add / update / search by ID / show all)
"""
import csv
import json
import math
import queue
import re
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime

import numpy as np
import pandas as pd

import tkinter as tk
from tkinter import ttk, filedialog

from hub_theme import add_field, card, clear_table, insert_row, make_table

OL_URL = "https://openlibrary.org/search.json"
GB_URL = "https://www.googleapis.com/books/v1/volumes"
USER_AGENT = "StudentHub/1.0 (college mini project)"
OL_FIELDS = ("key,title,author_name,first_publish_year,edition_count,ratings_average,ratings_count,"
             "want_to_read_count,number_of_pages_median,subject")
STOP_WORDS = {"the", "a", "an", "of", "and", "for", "in", "to", "book", "books", "best", "on", "with", "about"}
STATUSES = ["Want to read", "Reading", "Finished"]

# Offline suggestions (title, author) - shown only when there is no internet and no cached search
CURATED = {
    ("python",): [("Fluent Python", "Luciano Ramalho"), ("Python Crash Course", "Eric Matthes"),
                  ("Automate the Boring Stuff with Python", "Al Sweigart")],
    ("java",): [("Effective Java", "Joshua Bloch"), ("Java: The Complete Reference", "Herbert Schildt")],
    ("c", "programming"): [("The C Programming Language", "Brian Kernighan, Dennis Ritchie")],
    ("algorithm", "algorithms", "data structures"): [("Introduction to Algorithms", "Cormen, Leiserson, Rivest, Stein"),
                                                      ("Algorithms", "Robert Sedgewick, Kevin Wayne")],
    ("database", "sql", "dbms"): [("Database System Concepts", "Silberschatz, Korth, Sudarshan"),
                                  ("Fundamentals of Database Systems", "Elmasri, Navathe")],
    ("discrete", "mathematics"): [("Discrete Mathematics and Its Applications", "Kenneth Rosen")],
    ("machine", "learning", "ai"): [("Pattern Recognition and Machine Learning", "Christopher Bishop"),
                                    ("Hands-On Machine Learning", "Aurelien Geron")],
    ("physics",): [("Concepts of Physics", "H. C. Verma"), ("University Physics", "Young, Freedman")],
}


class BookSearchError(Exception):
    """Raised when no source could be reached."""


# ======================= OOP: a book =======================
class Book:
    def __init__(self, title, authors=None, year=None, rating=None, votes=0, want=0, editions=0,
                 pages=None, subjects=None, link="", source=""):
        self.title = title.strip()
        self.authors = list(authors or [])
        self.year, self.rating, self.votes = year, rating, int(votes or 0)
        self.want, self.editions, self.pages = int(want or 0), int(editions or 0), pages
        self.subjects, self.link = list(subjects or []), link
        self.sources = {source} if source else set()
        self.score = 0.0
        self.parts = {}

    @property
    def author_text(self):
        return ", ".join(self.authors[:3]) or "Unknown author"

    def key(self):
        main = re.split(r"[:(,]", self.title)[0]
        surname = (self.authors[0].split()[-1] if self.authors else "")
        return re.sub(r"[^a-z0-9]+", " ", f"{main} {surname}".lower()).strip()

    def merge(self, other):
        """Combine two records of the same book: rating weighted by votes, best of every other field."""
        total = self.votes + other.votes
        if total:
            mine = (self.rating or 0) * self.votes
            theirs = (other.rating or 0) * other.votes
            self.rating = (mine + theirs) / total
        elif self.rating is None:
            self.rating = other.rating
        self.votes = total
        self.want, self.editions = max(self.want, other.want), max(self.editions, other.editions)
        self.year = self.year or other.year
        self.pages = self.pages or other.pages
        self.link = self.link or other.link
        self.authors = self.authors or other.authors
        self.subjects = list(dict.fromkeys(self.subjects + other.subjects))
        self.sources |= other.sources

    def to_dict(self):
        return {k: (sorted(v) if isinstance(v, set) else v) for k, v in self.__dict__.items()
                if k not in ("score", "parts")}

    @classmethod
    def from_dict(cls, d):
        book = cls(d["title"], d["authors"], d["year"], d["rating"], d["votes"], d["want"], d["editions"],
                   d["pages"], d["subjects"], d["link"])
        book.sources = set(d.get("sources", []))
        return book


# ======================= fetching and parsing =======================
def fetch_json(url, params, timeout=12):
    request = urllib.request.Request(url + "?" + urllib.parse.urlencode(params), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as err:       # URLError covers HTTP errors too
        raise BookSearchError(str(getattr(err, "reason", err))) from None


def parse_openlibrary(payload):
    books = []
    for doc in payload.get("docs", []):
        if not doc.get("title"):
            continue
        books.append(Book(doc["title"], doc.get("author_name"), doc.get("first_publish_year"),
                          doc.get("ratings_average"), doc.get("ratings_count"), doc.get("want_to_read_count"),
                          doc.get("edition_count"), doc.get("number_of_pages_median"),
                          (doc.get("subject") or [])[:12], "https://openlibrary.org" + doc.get("key", ""),
                          "Open Library"))
    return books


def parse_google(payload):
    books = []
    for item in payload.get("items", []):
        info = item.get("volumeInfo", {})
        if not info.get("title"):
            continue
        year = None
        m = re.match(r"\d{4}", info.get("publishedDate", ""))
        if m:
            year = int(m.group(0))
        books.append(Book(info["title"], info.get("authors"), year, info.get("averageRating"),
                          info.get("ratingsCount"), 0, 0, info.get("pageCount"), info.get("categories"),
                          info.get("infoLink", ""), "Google Books"))
    return books


def search_books(topic, source="Both", english_only=True):
    """Returns (books, notes). Raises BookSearchError only if every source failed."""
    books, notes, errors = [], [], []
    if source in ("Both", "Open Library"):
        query = topic + (" language:eng" if english_only else "")
        try:
            books += parse_openlibrary(fetch_json(OL_URL, {"q": query, "limit": 40, "fields": OL_FIELDS}))
            notes.append("Open Library")
        except BookSearchError as err:
            errors.append(f"Open Library: {err}")
    if source in ("Both", "Google Books"):
        params = {"q": topic, "maxResults": 40, "printType": "books", "orderBy": "relevance"}
        if english_only:
            params["langRestrict"] = "en"
        try:
            books += parse_google(fetch_json(GB_URL, params))
            notes.append("Google Books")
        except BookSearchError as err:
            errors.append(f"Google Books: {err}")
    if not notes:
        raise BookSearchError("; ".join(errors) or "no source selected")
    return books, notes


def merge_books(books):
    merged = {}
    for book in books:
        if book.key() in merged:
            merged[book.key()].merge(book)
        else:
            merged[book.key()] = book
    return list(merged.values())


# ======================= ranking =======================
def topic_tokens(topic):
    return [t for t in re.findall(r"[a-z0-9+#]+", topic.lower()) if t not in STOP_WORDS]


def relevance(book, topic):
    tokens = topic_tokens(topic)
    if not tokens:
        return 0.5
    title = book.title.lower()
    subjects = " ".join(book.subjects).lower()
    in_title = sum(bool(re.search(rf"\b{re.escape(t)}", title)) for t in tokens)
    in_subjects = sum(bool(re.search(rf"\b{re.escape(t)}", subjects)) for t in tokens)
    return min(1.0, (2 * in_title + in_subjects) / (2 * len(tokens)))


def rank_books(books, topic, min_votes=10):
    """Score and sort. Returns a list of Book (best first)."""
    if not books:
        return []
    rated = [b.rating for b in books if b.rating and b.votes]
    prior = float(np.mean(rated)) if rated else 3.8                       # C: average rating of the pool
    frame = pd.DataFrame({
        "rating": [b.rating or 0.0 for b in books],
        "votes": [b.votes for b in books],
        "pop": [math.log1p(b.want) + 0.5 * math.log1p(b.editions) + 0.5 * math.log1p(b.votes) for b in books],
        "rel": [relevance(b, topic) for b in books]})
    v, m = frame["votes"], float(min_votes)
    frame["wr"] = (v / (v + m)) * frame["rating"] + (m / (v + m)) * prior       # Bayesian weighted rating
    frame["pop_n"] = frame["pop"] / frame["pop"].max() if frame["pop"].max() > 0 else 0.0
    frame["score"] = 100 * (0.45 * frame["wr"] / 5 + 0.30 * frame["rel"] + 0.25 * frame["pop_n"])
    for book, row in zip(books, frame.itertuples()):
        book.score = float(row.score)
        book.parts = {"quality": float(row.wr), "relevance": float(row.rel), "popularity": float(row.pop_n)}
    ranked = sorted(books, key=lambda b: b.score, reverse=True)
    relevant = [b for b in ranked if b.parts["relevance"] > 0]
    return relevant if len(relevant) >= 5 else ranked                         # drop off-topic noise


def curated_for(topic):
    tokens = set(topic_tokens(topic))
    out = []
    for keys, items in CURATED.items():
        if tokens & set(keys):
            out += [Book(t, [a], source="offline suggestion") for t, a in items]
    return out


def explain(book):
    p = book.parts
    rating = f"{book.rating:.2f} from {book.votes} ratings" if book.rating and book.votes else "no ratings available"
    return (f"{book.title}\nby {book.author_text}\n"
            f"First published: {book.year or 'n/a'}    Pages: {book.pages or 'n/a'}    "
            f"Editions: {book.editions or 'n/a'}    Want-to-read: {book.want or 'n/a'}\n"
            f"Rating: {rating}\nSources: {', '.join(sorted(book.sources)) or 'n/a'}\n\n"
            f"Score {book.score:.1f}/100 = quality {p.get('quality', 0):.2f}/5 (45%) + "
            f"relevance {p.get('relevance', 0):.0%} (30%) + popularity {p.get('popularity', 0):.0%} (25%)")


# ======================= storage =======================
class BookDB:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS searches(topic TEXT PRIMARY KEY, fetched TEXT, payload TEXT);
            CREATE TABLE IF NOT EXISTS library(
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, authors TEXT, year INTEGER,
                status TEXT DEFAULT 'Want to read', my_rating INTEGER, notes TEXT, link TEXT);
        """)

    def cache_put(self, topic, books):
        self.con.execute("INSERT OR REPLACE INTO searches VALUES (?,?,?)", (
            topic.lower(), datetime.now().isoformat(timespec="minutes"), json.dumps([b.to_dict() for b in books])))
        self.con.commit()

    def cache_get(self, topic):
        row = self.con.execute("SELECT fetched, payload FROM searches WHERE topic=?", (topic.lower(),)).fetchone()
        if not row:
            return None
        return row[0], [Book.from_dict(d) for d in json.loads(row[1])]

    def library(self):
        """Dictionary {id: record} - the reading list is managed as a dict (add/update/search/show)."""
        rows = self.con.execute("SELECT id,title,authors,year,status,my_rating,notes,link FROM library").fetchall()
        return {r[0]: {"title": r[1], "authors": r[2], "year": r[3], "status": r[4],
                       "my_rating": r[5], "notes": r[6], "link": r[7]} for r in rows}

    def add_to_library(self, book):
        for record in self.library().values():
            if record["title"].lower() == book.title.lower():
                return False
        self.con.execute("INSERT INTO library(title,authors,year,link) VALUES (?,?,?,?)",
                         (book.title, book.author_text, book.year, book.link))
        self.con.commit()
        return True

    def update_library(self, book_id, status=None, my_rating=None, notes=None):
        record = self.library().get(book_id)
        if record is None:
            raise KeyError(book_id)
        self.con.execute("UPDATE library SET status=?, my_rating=?, notes=? WHERE id=?", (
            status or record["status"], my_rating if my_rating is not None else record["my_rating"],
            notes if notes is not None else record["notes"], book_id))
        self.con.commit()

    def remove_from_library(self, book_id):
        self.con.execute("DELETE FROM library WHERE id=?", (book_id,))
        self.con.commit()


# ======================= GUI =======================
class BookPage(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.db = BookDB(ctx.path("books.db"))
        self.results = []
        self.jobs = queue.Queue()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.build_search_tab()
        self.build_library_tab()
        self.refresh_library()

    def on_show(self):
        self.refresh_library()

    # ---------- search tab ----------
    def build_search_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F50E Find the best book  ")
        tab.columnconfigure(0, weight=1)
        bar = card(tab)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="Topic", style="CardTitle.TLabel").grid(row=0, column=0, padx=(0, 10))
        self.v_topic = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.v_topic, font=(self.ctx.theme.family, 12))
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<Return>", lambda event: self.start_search())
        self.v_source = tk.StringVar(value="Both")
        ttk.Combobox(bar, textvariable=self.v_source, values=["Both", "Open Library", "Google Books"],
                     state="readonly", width=13).grid(row=0, column=2, padx=8)
        self.v_english = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="English only", variable=self.v_english, style="Card.TCheckbutton").grid(row=0, column=3, padx=4)
        self.search_btn = ttk.Button(bar, text="Search", style="Accent.TButton", command=self.start_search)
        self.search_btn.grid(row=0, column=4, padx=(8, 0))
        self.v_status = tk.StringVar(value="Type a topic such as 'python programming' or 'discrete mathematics'.")
        ttk.Label(tab, textvariable=self.v_status, style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(6, 6))
        self.best = card(tab)
        self.best.grid(row=2, column=0, sticky="ew")
        self.best_title = ttk.Label(self.best, text="Best pick will appear here", style="CardTitle.TLabel")
        self.best_title.pack(anchor="w")
        self.best_sub = ttk.Label(self.best, text="", style="CardMuted.TLabel")
        self.best_sub.pack(anchor="w")
        self.best_bar = ttk.Progressbar(self.best, maximum=100)
        self.best_bar.pack(fill="x", pady=(8, 0))
        body = ttk.Frame(tab)
        body.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        tab.rowconfigure(3, weight=1)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)
        left = card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        frame, self.tree = make_table(left, [("rank", "#", 36, "center"), ("title", "Title", 260, "w"),
                                             ("author", "Author", 150, "w"), ("year", "Year", 55, "center"),
                                             ("rating", "Rating", 90, "center"), ("score", "Score", 60, "e")], height=12)
        frame.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda event: self.show_detail())
        right = card(body)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self.detail = tk.Text(right, height=10, wrap="word", font=(self.ctx.theme.family, 10))
        self.detail.grid(row=0, column=0, columnspan=3, sticky="nsew")
        self.detail.config(state="disabled")
        ttk.Button(right, text="Open page", command=self.open_link).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(right, text="Save to my library", style="Accent.TButton", command=self.save_selected).grid(row=1, column=1, pady=(8, 0), padx=6)
        ttk.Button(right, text="Export CSV", command=self.export_csv).grid(row=1, column=2, sticky="e", pady=(8, 0))

    def start_search(self):
        topic = self.v_topic.get().strip()
        if len(topic) < 2:
            return self.ctx.toast("Enter a topic first", "warning")
        self.search_btn.config(state="disabled")
        self.v_status.set("Searching the internet ...")
        threading.Thread(target=self.worker, args=(topic, self.v_source.get(), self.v_english.get()), daemon=True).start()
        self.after(120, self.poll)

    def worker(self, topic, source, english):               # runs off the UI thread: only talks to the queue
        try:
            books, notes = search_books(topic, source, english)
            self.jobs.put(("ok", topic, books, notes))
        except BookSearchError as err:
            self.jobs.put(("error", topic, str(err), None))

    def poll(self):
        try:
            kind, topic, payload, notes = self.jobs.get_nowait()
        except queue.Empty:
            return self.after(120, self.poll)
        self.search_btn.config(state="normal")
        if kind == "ok":
            books = merge_books(payload)
            self.db.cache_put(topic, books)
            self.show_results(rank_books(books, topic), f"{len(books)} books from {' + '.join(notes)}")
            return
        cached = self.db.cache_get(topic)
        if cached:
            fetched, books = cached
            self.show_results(rank_books(books, topic), f"Offline - showing cached results from {fetched}")
            self.ctx.toast("No internet connection - used your cached search", "warning")
            return
        offline = curated_for(topic)
        if offline:
            self.show_results(offline, "Offline - well-known textbooks (not ranked, no ratings available)")
        else:
            self.v_status.set(f"Could not reach the book services ({payload}). Check your internet connection.")
            self.ctx.toast("Search failed - check your internet connection", "error")

    def show_results(self, books, status):
        self.results = books[:30]
        clear_table(self.tree)
        for i, book in enumerate(self.results, 1):
            rating = f"{book.rating:.1f} ({book.votes})" if book.rating and book.votes else "-"
            insert_row(self.tree, (i, book.title, book.author_text, book.year or "-", rating,
                                   f"{book.score:.0f}" if book.score else "-"), iid=str(i - 1))
        self.v_status.set(status)
        if self.results:
            top = self.results[0]
            self.best_title.config(text=f"Best pick:  {top.title}")
            self.best_sub.config(text=f"{top.author_text}   |   score {top.score:.0f}/100" if top.score else top.author_text)
            self.best_bar.config(value=top.score)
            self.tree.selection_set("0")
        else:
            self.best_title.config(text="No books found - try different words")
            self.best_sub.config(text="")
            self.best_bar.config(value=0)

    def selected_book(self):
        selection = self.tree.selection()
        return self.results[int(selection[0])] if selection else None

    def show_detail(self):
        book = self.selected_book()
        if book:
            self.detail.config(state="normal")
            self.detail.delete("1.0", "end")
            self.detail.insert("1.0", explain(book) if book.score else f"{book.title}\nby {book.author_text}")
            self.detail.config(state="disabled")

    def open_link(self):
        book = self.selected_book()
        if book and book.link:
            webbrowser.open(book.link)
        else:
            self.ctx.toast("No web page for this book", "warning")

    def save_selected(self):
        book = self.selected_book()
        if not book:
            return self.ctx.toast("Select a book first", "warning")
        if self.db.add_to_library(book):
            self.ctx.toast(f"Saved '{book.title}' to your library", "success")
            self.refresh_library()
        else:
            self.ctx.toast("Already in your library", "info")

    def export_csv(self):
        if not self.results:
            return self.ctx.toast("Search first", "warning")
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="best_books.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["rank", "title", "authors", "year", "rating", "votes", "score", "link"])
                for i, b in enumerate(self.results, 1):
                    writer.writerow([i, b.title, b.author_text, b.year, b.rating, b.votes, round(b.score, 1), b.link])
        except OSError as err:
            self.ctx.toast(f"Could not save: {err}", "error")
        else:
            self.ctx.toast("Exported", "success")

    # ---------- library tab (dictionary-based CRUD) ----------
    def build_library_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F4DA My library  ")
        tab.columnconfigure(1, weight=1)
        form = card(tab)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Label(form, text="Update a book", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.l_id, self.l_status, self.l_rating, self.l_notes = tk.StringVar(), tk.StringVar(value=STATUSES[0]), tk.StringVar(), tk.StringVar()
        add_field(form, 1, "Book ID", ttk.Entry(form, textvariable=self.l_id, width=22))
        add_field(form, 2, "Status", ttk.Combobox(form, textvariable=self.l_status, values=STATUSES, state="readonly", width=20))
        add_field(form, 3, "My rating (1-5)", ttk.Entry(form, textvariable=self.l_rating, width=22))
        add_field(form, 4, "Notes", ttk.Entry(form, textvariable=self.l_notes, width=22))
        ttk.Button(form, text="Update", style="Accent.TButton", command=self.update_library).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(form, text="Search by ID", command=self.find_by_id).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(form, text="Remove", command=self.remove_book).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        right = card(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        frame, self.lib_tree = make_table(right, [("id", "ID", 40, "center"), ("title", "Title", 230, "w"),
                                                  ("authors", "Authors", 150, "w"), ("status", "Status", 100, "w"),
                                                  ("rating", "My rating", 70, "center"), ("notes", "Notes", 160, "w")], height=14)
        frame.grid(row=0, column=0, sticky="nsew")
        self.lib_tree.bind("<<TreeviewSelect>>", lambda event: self.fill_form())

    def refresh_library(self):
        clear_table(self.lib_tree)
        for book_id, r in self.db.library().items():
            tag = "success" if r["status"] == "Finished" else None
            insert_row(self.lib_tree, (book_id, r["title"], r["authors"], r["status"], r["my_rating"] or "-", r["notes"] or ""), tag=tag)
        self.ctx.theme.recolor(self)

    def fill_form(self):
        selection = self.lib_tree.selection()
        if selection:
            values = self.lib_tree.item(selection[0])["values"]
            self.l_id.set(values[0])
            self.l_status.set(values[3])

    def update_library(self):
        try:
            book_id = int(self.l_id.get())
            rating = int(self.l_rating.get()) if self.l_rating.get().strip() else None
            if rating is not None and not 1 <= rating <= 5:
                raise ValueError
            self.db.update_library(book_id, self.l_status.get(), rating, self.l_notes.get().strip() or None)
        except ValueError:
            return self.ctx.toast("Enter a numeric book ID and a rating from 1 to 5", "error")
        except KeyError:
            return self.ctx.toast("No book with that ID", "error")
        self.ctx.toast("Library updated", "success")
        self.refresh_library()

    def find_by_id(self):
        try:
            record = self.db.library()[int(self.l_id.get())]
        except (ValueError, KeyError):
            return self.ctx.toast("No book with that ID", "error")
        self.ctx.toast(f"{record['title']} - {record['status']}", "info")

    def remove_book(self):
        selection = self.lib_tree.selection()
        if selection:
            self.db.remove_from_library(self.lib_tree.item(selection[0])["values"][0])
            self.refresh_library()
