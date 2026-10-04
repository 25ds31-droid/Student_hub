"""
Exam Scheduler & Smart Study Planner
------------------------------------
* Subjects with credits, difficulty and syllabus progress; exams with date, time, duration, venue and weight
* Clash detection: overlapping papers, back-to-back papers and heavy weeks
* Smart study plan: every day the available hours are split between subjects by a priority score
  (exam weight x difficulty x unfinished syllabus / days left) and rounded with a heap (largest remainder)
* Charts: calendar heat-map, stacked daily plan, allocation donut, coverage bars, readiness gauge, countdown bars
* study_tracker.py imports Database(...).subjects() from this module to pull in your subject list
"""
import csv
import heapq
import re
import sqlite3
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import ttk, filedialog

from hub_charts import BarChart, CalendarHeat, DonutChart, Gauge, HBarChart
from hub_theme import (MONTHS, DatePicker, TimePicker, add_field, badge, card, clear_table, info_icon, insert_row,
                       make_table)

KINDS = ["Final", "Mid-term", "Quiz", "Viva", "Practical", "Assignment"]
DURATIONS = ["30 min", "45 min", "60 min", "90 min", "120 min", "150 min", "180 min", "240 min"]
WEIGHTS = ["5%", "10%", "15%", "20%", "25%", "30%", "40%", "50%", "60%", "70%", "80%", "100%"]
CREDITS = ["1", "2", "3", "4", "5", "6"]
VENUES = ["Exam Hall A", "Exam Hall B", "Exam Hall C", "Lab 1", "Lab 2", "Seminar Room", "Online"]
DIFFICULTY = {1: "1 - Very easy", 2: "2 - Easy", 3: "3 - Moderate", 4: "4 - Hard", 5: "5 - Very hard"}
HOURS_PER_TOPIC = {1: 1.0, 2: 1.25, 3: 1.5, 4: 1.75, 5: 2.0}
CODE_RE = re.compile(r"[A-Za-z0-9-]{2,10}")
TIME_RE = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


class ExamError(Exception):
    pass


class InvalidExamError(ExamError):
    pass


# ======================= model =======================
class Subject:
    def __init__(self, code, name, credits, difficulty, total, done):
        self.code, self.name, self.credits = code, name, int(credits)
        self.difficulty, self.total, self.done = int(difficulty), int(total), int(done)

    @property
    def progress(self):
        return self.done / self.total if self.total else 0.0

    @property
    def need_hours(self):
        return (self.total - self.done) * HOURS_PER_TOPIC[self.difficulty]


class Exam:
    def __init__(self, exam_id, code, kind, day, start, duration, venue, weight):
        self.id, self.code, self.kind = exam_id, code, kind
        self.date = date.fromisoformat(day) if isinstance(day, str) else day
        self.start, self.duration, self.venue, self.weight = start, int(duration), venue, int(weight)

    @property
    def start_dt(self):
        h, m = map(int, self.start.split(":"))
        return datetime.combine(self.date, datetime.min.time()) + timedelta(hours=h, minutes=m)

    @property
    def end_dt(self):
        return self.start_dt + timedelta(minutes=self.duration)

    def days_left(self, today=None):
        return (self.date - (today or date.today())).days

    def title(self):
        return f"{self.code} {self.kind}"


# ======================= pure logic =======================
def find_clashes(exams):
    """Returns [(severity, message, {exam ids})] with severity 'bad' or 'warn'."""
    found, ordered = [], sorted(exams, key=lambda e: e.start_dt)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if b.start_dt >= a.end_dt + timedelta(hours=18):
                break
            if a.start_dt < b.end_dt and b.start_dt < a.end_dt:
                found.append(("bad", f"{a.title()} and {b.title()} overlap on {a.date:%d %b}", {a.id, b.id}))
            else:
                gap = (b.start_dt - a.end_dt).total_seconds() / 3600
                found.append(("warn", f"{a.title()} -> {b.title()}: only {gap:.1f} h between papers", {a.id, b.id}))
    days = sorted({e.date for e in exams})
    for d in days:
        window = [e for e in exams if 0 <= (e.date - d).days <= 2]
        if len({e.date for e in window}) >= 2 and len(window) >= 3:
            ids = {e.id for e in window}
            message = f"Heavy stretch: {len(window)} exams between {d:%d %b} and {d + timedelta(days=2):%d %b}"
            if not any(m == message for _, m, _ in found):
                found.append(("warn", message, ids))
    return found


def exam_priority(exam, subject, day):
    days = max((exam.date - day).days, 1)
    return exam.weight * (0.5 + subject.difficulty / 5) * (0.15 + 1 - subject.progress) / days ** 0.6


def allocate(hours, weights):
    """Split `hours` in half-hour units by weight using the largest-remainder method (heap)."""
    units = int(round(hours * 2))
    total = sum(weights.values())
    if units <= 0 or total <= 0:
        return {}
    raw = {k: v / total * units for k, v in weights.items()}
    base = {k: int(x) for k, x in raw.items()}
    left = units - sum(base.values())
    for k, _ in heapq.nlargest(left, ((k, raw[k] - base[k]) for k in raw), key=lambda p: p[1]):
        base[k] += 1
    return {k: v / 2 for k, v in base.items() if v}


def study_plan(exams, subjects, hours_per_day, start=None, skip_weekends=False):
    """Day-by-day plan. Returns dict(days=[(date, {code: hours})], totals, need, coverage).

    Each subject stays in the plan until its LAST upcoming exam; its urgency on any day comes from its NEXT exam."""
    start = start or date.today()
    by_code = {s.code: s for s in subjects}
    upcoming = {}
    for e in sorted(exams, key=lambda e: e.date):
        if e.date > start and e.code in by_code:
            upcoming.setdefault(e.code, []).append(e)
    if not upcoming:
        return {"days": [], "totals": {}, "need": {}, "coverage": {}}
    last = max(e.date for lst in upcoming.values() for e in lst)
    need = {c: by_code[c].need_hours for c in upcoming}
    given = {c: 0.0 for c in upcoming}
    days, day = [], start
    while day < last:
        if not (skip_weekends and day.weekday() >= 5):
            nxt = {c: next(e for e in lst if e.date > day) for c, lst in upcoming.items() if lst[-1].date > day}
            raw = {}
            for c, e in nxt.items():
                w = exam_priority(e, by_code[c], day)
                if (e.date - day).days == 1:
                    w *= 1.5                                           # revision boost on the eve of an exam
                raw[c] = w
            weights = {c: w for c, w in raw.items() if given[c] < need[c]}      # covered subjects stop taking hours
            plan = allocate(hours_per_day, weights or raw)                     # all covered: spread light revision
            for c, h in plan.items():
                given[c] += h
            if plan:
                days.append((day, plan))
        day += timedelta(days=1)
    coverage = {c: (given[c] / need[c] if need[c] else 1.0) for c in upcoming}
    return {"days": days, "totals": given, "need": need, "coverage": coverage}


def week_load(exams):
    """{(year, week): (number of exams, exam hours)}"""
    out = {}
    for e in exams:
        key = e.date.isocalendar()[:2]
        n, h = out.get(key, (0, 0.0))
        out[key] = (n + 1, h + e.duration / 60)
    return dict(sorted(out.items()))


# ======================= database =======================
class Database:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS subjects(code TEXT PRIMARY KEY COLLATE NOCASE, name TEXT NOT NULL,
                credits INTEGER NOT NULL, difficulty INTEGER NOT NULL, topics_total INTEGER NOT NULL,
                topics_done INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL COLLATE NOCASE,
                kind TEXT NOT NULL, date TEXT NOT NULL, start TEXT NOT NULL, duration INTEGER NOT NULL,
                venue TEXT, weight INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        """)
        self.con.commit()

    # -- used by study_tracker.py --
    def subjects(self):
        return self.con.execute("SELECT code, name FROM subjects ORDER BY code").fetchall()

    def subject_objects(self):
        rows = self.con.execute("SELECT code,name,credits,difficulty,topics_total,topics_done FROM subjects ORDER BY code")
        return [Subject(*r) for r in rows.fetchall()]

    def add_subject(self, code, name, credits, difficulty, total):
        code, name = code.strip().upper(), name.strip()
        if not CODE_RE.fullmatch(code):
            raise InvalidExamError("Subject code: 2-10 letters, digits or -")
        if not 2 <= len(name) <= 40:
            raise InvalidExamError("Subject name must be 2-40 characters")
        try:
            total, credits, difficulty = int(total), int(credits), int(difficulty)
        except (TypeError, ValueError):
            raise InvalidExamError("Topics, credits and difficulty must be whole numbers") from None
        if not 1 <= total <= 200:
            raise InvalidExamError("Number of topics must be between 1 and 200")
        self.con.execute("""INSERT INTO subjects(code,name,credits,difficulty,topics_total,topics_done) VALUES (?,?,?,?,?,0)
                            ON CONFLICT(code) DO UPDATE SET name=excluded.name, credits=excluded.credits,
                            difficulty=excluded.difficulty, topics_total=excluded.topics_total,
                            topics_done=MIN(topics_done, excluded.topics_total)""", (code, name, credits, difficulty, total))
        self.con.commit()

    def set_progress(self, code, done):
        row = self.con.execute("SELECT topics_total FROM subjects WHERE code=?", (code,)).fetchone()
        if row is None:
            raise InvalidExamError("Pick a subject first")
        try:
            done = int(done)
        except (TypeError, ValueError):
            raise InvalidExamError("Topics done must be a whole number") from None
        if not 0 <= done <= row[0]:
            raise InvalidExamError(f"Topics done must be between 0 and {row[0]}")
        self.con.execute("UPDATE subjects SET topics_done=? WHERE code=?", (done, code))
        self.con.commit()

    def delete_subject(self, code):
        self.con.execute("DELETE FROM exams WHERE code=?", (code,))
        self.con.execute("DELETE FROM subjects WHERE code=?", (code,))
        self.con.commit()

    def add_exam(self, code, kind, day, start, duration, venue, weight):
        if not code or self.con.execute("SELECT 1 FROM subjects WHERE code=?", (code,)).fetchone() is None:
            raise InvalidExamError("Add the subject first (Subjects tab), then pick it here")
        if not TIME_RE.fullmatch(start):
            raise InvalidExamError("Start time must look like 09:30")
        try:
            date.fromisoformat(day)
            duration, weight = int(str(duration).split()[0]), int(str(weight).strip("%"))
        except (ValueError, IndexError):
            raise InvalidExamError("Check the date, duration and weight") from None
        self.con.execute("INSERT INTO exams(code,kind,date,start,duration,venue,weight) VALUES (?,?,?,?,?,?,?)",
                         (code, kind, day, start, duration, venue.strip(), weight))
        self.con.commit()

    def delete_exam(self, exam_id):
        self.con.execute("DELETE FROM exams WHERE id=?", (exam_id,))
        self.con.commit()

    def exams(self):
        rows = self.con.execute("SELECT id,code,kind,date,start,duration,venue,weight FROM exams ORDER BY date,start")
        return [Exam(*r) for r in rows.fetchall()]

    def get_setting(self, key, default):
        row = self.con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))
        self.con.commit()

    def load_demo(self):
        today = date.today()
        subjects = [("DBMS", "Database Management", 4, 4, 24, 10), ("OS", "Operating Systems", 4, 5, 30, 8),
                    ("MATH", "Engineering Maths", 4, 4, 20, 12), ("JAVA", "Java Programming", 3, 3, 18, 14),
                    ("NET", "Computer Networks", 3, 3, 16, 5)]
        for code, name, cr, diff, total, done in subjects:
            self.add_subject(code, name, cr, diff, total)
            self.set_progress(code, done)
        for code, kind, offset, start, dur, venue, weight in [
                ("MATH", "Mid-term", 4, "14:00", 90, "Exam Hall C", 30), ("DBMS", "Final", 6, "10:00", 120, "Exam Hall A", 60),
                ("NET", "Quiz", 6, "11:30", 45, "Exam Hall A", 15), ("OS", "Final", 8, "10:00", 180, "Exam Hall B", 70),
                ("JAVA", "Practical", 11, "14:00", 120, "Lab 2", 40), ("NET", "Final", 14, "10:00", 120, "Exam Hall B", 60),
                ("MATH", "Final", 16, "10:00", 180, "Exam Hall A", 70)]:
            self.add_exam(code, kind, (today + timedelta(days=offset)).isoformat(), start, dur, venue, weight)


# ======================= GUI =======================
class ExamPage(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.db = Database(ctx.path("exam_scheduler.db"))
        self.plan = None
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.build_schedule_tab()
        self.build_subjects_tab()
        self.build_plan_tab()
        self.build_insights_tab()
        self.refresh_all()

    def on_show(self):
        self.refresh_all()

    # ---------- helpers ----------
    def tab(self, title):
        frame = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(frame, text=title)
        return frame

    def choices(self):
        return [f"{code} - {name}" for code, name in self.db.subjects()]

    @staticmethod
    def code_of(choice):
        return choice.split(" - ")[0].strip()

    def titled_card(self, parent, eyebrow, title, **grid):
        box = card(parent)
        box.grid(**grid)
        ttk.Label(box, text=eyebrow, style="CardEyebrow.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(box, text=title, style="CardTitle.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))
        return box

    # ---------- tab 1: schedule ----------
    def build_schedule_tab(self):
        tab = self.tab("  \U0001F4C5 Schedule  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        form = self.titled_card(tab, "NEW EXAM", "Add a paper", row=0, column=0, rowspan=2, sticky="ns", padx=(0, 10))
        form.columnconfigure(1, weight=1)
        self.v_subject, self.v_kind = tk.StringVar(), tk.StringVar(value=KINDS[0])
        self.v_duration, self.v_weight, self.v_venue = tk.StringVar(value="120 min"), tk.StringVar(value="30%"), tk.StringVar(value=VENUES[0])
        self.subject_box = add_field(form, 2, "Subject", ttk.Combobox(form, textvariable=self.v_subject, state="readonly", width=24))
        add_field(form, 3, "Type", ttk.Combobox(form, textvariable=self.v_kind, values=KINDS, state="readonly", width=24))
        self.exam_date = add_field(form, 4, "Date", DatePicker(form, value=date.today() + timedelta(days=7)))
        self.exam_time = add_field(form, 5, "Start time", TimePicker(form, "10:00"))
        add_field(form, 6, "Duration", ttk.Combobox(form, textvariable=self.v_duration, values=DURATIONS, state="readonly", width=24))
        add_field(form, 7, "Venue", ttk.Combobox(form, textvariable=self.v_venue, values=VENUES, width=24))
        add_field(form, 8, "Weight", ttk.Combobox(form, textvariable=self.v_weight, values=WEIGHTS, state="readonly", width=24))
        info_icon(form, "Weight = how much of the course grade this paper carries. Heavier papers get more study hours in the plan.").grid(row=8, column=2, padx=4)
        info_icon(form, "Add subjects first in the Subjects tab, or press 'Load demo data' to see everything working.").grid(row=2, column=2, padx=4)
        ttk.Button(form, text="Add exam", style="Accent.TButton", command=self.add_exam).grid(row=9, column=0, columnspan=3, sticky="ew", pady=(12, 4))
        ttk.Button(form, text="Load demo data", command=self.load_demo).grid(row=10, column=0, columnspan=3, sticky="ew", pady=2)
        ttk.Button(form, text="Export schedule (CSV)", command=self.export_schedule).grid(row=11, column=0, columnspan=3, sticky="ew", pady=2)

        top = self.titled_card(tab, "UPCOMING EXAMS", "Schedule and countdown", row=0, column=1, sticky="nsew")
        top.columnconfigure(0, weight=1)
        top.rowconfigure(2, weight=1)
        frame, self.tree = make_table(top, [("date", "Date", 90, "center"), ("time", "Time", 60, "center"),
                                            ("sub", "Subject", 70, "w"), ("kind", "Type", 80, "w"),
                                            ("venue", "Venue", 100, "w"), ("w", "Weight", 55, "center"),
                                            ("in", "In", 80, "center"), ("st", "Status", 80, "center")], height=7)
        frame.grid(row=2, column=0, columnspan=3, sticky="nsew")
        ttk.Button(top, text="Delete selected", style="Danger.TButton", command=self.delete_exam).grid(row=3, column=0, columnspan=3, sticky="e", pady=(8, 0))

        lower = ttk.Frame(tab)
        lower.grid(row=1, column=1, sticky="nsew", pady=(10, 0))
        lower.columnconfigure((0, 1), weight=1, uniform="low")
        self.warn_card = self.titled_card(lower, "CLASH CHECK", "Warnings", row=0, column=0, sticky="nsew", padx=(0, 10))
        self.warn_box = ttk.Frame(self.warn_card, style="Card.TFrame")
        self.warn_box.grid(row=2, column=0, columnspan=3, sticky="nsew")
        cal = self.titled_card(lower, "CALENDAR", "Exam days", row=0, column=1, sticky="nsew")
        cal.columnconfigure(0, weight=1)
        today = date.today()
        self.v_cal_m, self.v_cal_y = tk.StringVar(value=MONTHS[today.month - 1]), tk.StringVar(value=str(today.year))
        pick = ttk.Frame(cal, style="Card.TFrame")
        pick.grid(row=2, column=0, sticky="w")
        for var, values, width in ((self.v_cal_m, MONTHS, 5), (self.v_cal_y, [str(today.year + i) for i in range(-1, 3)], 6)):
            box = ttk.Combobox(pick, textvariable=var, values=values, width=width, state="readonly")
            box.pack(side="left", padx=(0, 4))
            box.bind("<<ComboboxSelected>>", lambda event: self.draw_calendar())
        self.calendar = CalendarHeat(cal, self.ctx.theme, height=210)
        self.calendar.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(6, 0))

    def add_exam(self):
        try:
            self.db.add_exam(self.code_of(self.v_subject.get()), self.v_kind.get(), self.exam_date.iso(), self.exam_time.get(),
                             self.v_duration.get(), self.v_venue.get(), self.v_weight.get())
        except ExamError as err:
            return self.ctx.toast(str(err), "error")
        self.ctx.toast("Exam added", "success")
        self.refresh_all()

    def delete_exam(self):
        for item in self.tree.selection():
            self.db.delete_exam(int(item))
        self.refresh_all()

    def load_demo(self):
        if self.db.subject_objects() or self.db.exams():
            return self.ctx.toast("Demo data is only added to an empty scheduler", "warning")
        self.db.load_demo()
        self.ctx.toast("Demo subjects and exams added", "success")
        self.refresh_all()

    def export_schedule(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="exam_schedule.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Date", "Start", "Duration (min)", "Subject", "Type", "Venue", "Weight %"])
                for e in self.db.exams():
                    writer.writerow([e.date.isoformat(), e.start, e.duration, e.code, e.kind, e.venue, e.weight])
        except OSError as err:
            self.ctx.toast(f"Could not save: {err}", "error")
        else:
            self.ctx.toast("Schedule exported", "success")

    def draw_calendar(self):
        year, month = int(self.v_cal_y.get()), MONTHS.index(self.v_cal_m.get()) + 1
        exams = [e for e in self.db.exams() if e.date.year == year and e.date.month == month]
        clash_ids = set().union(*[ids for _, _, ids in find_clashes(self.db.exams())] or [set()])
        data = {}
        for e in exams:
            value, tip, ring = data.get(e.date.day, (0, "", None))
            line = f"{e.start} {e.title()} ({e.duration} min, {e.venue or 'venue TBA'})"
            data[e.date.day] = (min(1.0, value + 0.45), (tip + "\n" if tip else "") + line,
                                self.ctx.theme.colors["danger"] if e.id in clash_ids else ring or self.ctx.theme.colors["warning"])
        self.calendar.set(year, month, data)

    # ---------- tab 2: subjects ----------
    def build_subjects_tab(self):
        tab = self.tab("  \U0001F4DA Subjects  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        form = self.titled_card(tab, "SYLLABUS", "Add or update a subject", row=0, column=0, sticky="ns", padx=(0, 10))
        form.columnconfigure(1, weight=1)
        self.v_code, self.v_name = tk.StringVar(), tk.StringVar()
        self.v_credits, self.v_diff = tk.StringVar(value="4"), tk.StringVar(value=DIFFICULTY[3])
        self.v_topics = tk.StringVar(value="20")
        add_field(form, 2, "Code", ttk.Entry(form, textvariable=self.v_code, width=24))
        add_field(form, 3, "Name", ttk.Entry(form, textvariable=self.v_name, width=24))
        add_field(form, 4, "Credits", ttk.Combobox(form, textvariable=self.v_credits, values=CREDITS, state="readonly", width=22))
        add_field(form, 5, "Difficulty", ttk.Combobox(form, textvariable=self.v_diff, values=list(DIFFICULTY.values()), state="readonly", width=22))
        add_field(form, 6, "Topics in syllabus", ttk.Spinbox(form, from_=1, to=200, textvariable=self.v_topics, width=8))
        info_icon(form, "Example: code DBMS, name Database Management, difficulty 4, 24 topics.\nHarder subjects need more hours per topic.").grid(row=2, column=2, padx=4)
        ttk.Button(form, text="Save subject", style="Accent.TButton", command=self.save_subject).grid(row=7, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        ttk.Button(form, text="Delete selected", style="Danger.TButton", command=self.delete_subject).grid(row=8, column=0, columnspan=3, sticky="ew")
        ttk.Separator(form).grid(row=9, column=0, columnspan=3, sticky="ew", pady=12)
        ttk.Label(form, text="Update progress", style="CardTitle.TLabel").grid(row=10, column=0, columnspan=3, sticky="w")
        self.v_prog_subject, self.v_prog_done = tk.StringVar(), tk.StringVar(value="0")
        self.prog_box = add_field(form, 11, "Subject", ttk.Combobox(form, textvariable=self.v_prog_subject, state="readonly", width=22))
        add_field(form, 12, "Topics done", ttk.Spinbox(form, from_=0, to=200, textvariable=self.v_prog_done, width=8))
        ttk.Button(form, text="Update progress", command=self.update_progress).grid(row=13, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        right = self.titled_card(tab, "PROGRESS", "Syllabus completed per subject", row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        frame, self.sub_tree = make_table(right, [("code", "Code", 70, "w"), ("name", "Name", 190, "w"), ("cr", "Credits", 60, "center"),
                                                  ("diff", "Difficulty", 100, "w"), ("topics", "Topics", 80, "center"),
                                                  ("pct", "Done", 70, "center"), ("need", "Hours needed", 90, "center")], height=6)
        frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.progress_chart = HBarChart(right, self.ctx.theme, height=170)
        self.progress_chart.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(10, 0))

    def save_subject(self):
        try:
            self.db.add_subject(self.v_code.get(), self.v_name.get(), self.v_credits.get(), self.v_diff.get()[0], self.v_topics.get())
        except ExamError as err:
            return self.ctx.toast(str(err), "error")
        self.v_code.set("")
        self.v_name.set("")
        self.ctx.toast("Subject saved", "success")
        self.refresh_all()

    def delete_subject(self):
        for item in self.sub_tree.selection():
            self.db.delete_subject(item)
        self.refresh_all()

    def update_progress(self):
        try:
            self.db.set_progress(self.code_of(self.v_prog_subject.get()), self.v_prog_done.get())
        except ExamError as err:
            return self.ctx.toast(str(err), "error")
        self.ctx.toast("Progress updated", "success")
        self.refresh_all()

    # ---------- tab 3: study plan ----------
    def build_plan_tab(self):
        tab = self.tab("  \U0001F9E0 Study plan  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(1, weight=1)
        bar = card(tab)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.v_hours, self.v_weekend = tk.StringVar(value=self.db.get_setting("hours", "5")), tk.StringVar(value="Study on weekends")
        ttk.Label(bar, text="Hours per day", style="CardMuted.TLabel").pack(side="left")
        ttk.Combobox(bar, textvariable=self.v_hours, values=[f"{x / 2:g}" for x in range(2, 25)], width=6, state="readonly").pack(side="left", padx=(6, 18))
        ttk.Label(bar, text="Weekends", style="CardMuted.TLabel").pack(side="left")
        ttk.Combobox(bar, textvariable=self.v_weekend, values=["Study on weekends", "Skip weekends"], width=18, state="readonly").pack(side="left", padx=(6, 18))
        ttk.Button(bar, text="Generate plan", style="Accent.TButton", command=self.make_plan).pack(side="left")
        ttk.Button(bar, text="Export plan (CSV)", command=self.export_plan).pack(side="left", padx=8)
        info_icon(bar, "Each day's hours are shared between subjects using exam weight x difficulty x unfinished syllabus / days left. "
                       "The day before an exam gets a revision boost.").pack(side="left")
        self.plan_summary = ttk.Label(bar, text="", style="Card.TLabel")
        self.plan_summary.pack(side="right")

        left = self.titled_card(tab, "DAY BY DAY", "Your plan", row=1, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(2, weight=1)
        frame, self.plan_tree = make_table(left, [("date", "Date", 85, "center"), ("day", "Day", 45, "center"),
                                                  ("plan", "What to study", 270, "w"), ("h", "Hours", 55, "center")], height=14)
        frame.grid(row=2, column=0, columnspan=3, sticky="nsew")
        right = ttk.Frame(tab)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure((0, 1), weight=1, uniform="pl")
        right.rowconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        daily = self.titled_card(right, "WORKLOAD", "Hours per day (next 14 days)", row=0, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
        daily.columnconfigure(0, weight=1)
        daily.rowconfigure(2, weight=1)
        self.plan_bar = BarChart(daily, self.ctx.theme, height=170)
        self.plan_bar.grid(row=2, column=0, columnspan=3, sticky="nsew")
        share = self.titled_card(right, "ALLOCATION", "Total hours by subject", row=1, column=0, sticky="nsew", padx=(0, 10))
        share.columnconfigure(0, weight=1)
        self.plan_donut = DonutChart(share, self.ctx.theme, height=170)
        self.plan_donut.grid(row=2, column=0, columnspan=3, sticky="nsew")
        cover = self.titled_card(right, "COVERAGE", "Planned vs needed hours", row=1, column=1, sticky="nsew")
        cover.columnconfigure(0, weight=1)
        self.plan_cover = HBarChart(cover, self.ctx.theme, height=170)
        self.plan_cover.grid(row=2, column=0, columnspan=3, sticky="nsew")

    def make_plan(self):
        exams, subjects = self.db.exams(), self.db.subject_objects()
        try:
            hours = float(self.v_hours.get())
        except ValueError:
            return self.ctx.toast("Pick the hours per day from the list", "error")
        self.db.set_setting("hours", self.v_hours.get())
        self.plan = study_plan(exams, subjects, hours, skip_weekends=self.v_weekend.get() == "Skip weekends")
        if not self.plan["days"]:
            self.ctx.toast("Add subjects and at least one future exam first", "warning")
        self.draw_plan()

    def draw_plan(self):
        clear_table(self.plan_tree)
        c = self.ctx.theme.colors
        plan = self.plan
        if not plan or not plan["days"]:
            self.plan_summary.config(text="Press 'Generate plan'")
            for chart in (self.plan_bar, self.plan_donut, self.plan_cover):
                chart.set([], []) if chart is self.plan_bar else chart.set([])
            return
        for day, hours in plan["days"]:
            text = "  |  ".join(f"{code} {h:g}h" for code, h in sorted(hours.items(), key=lambda p: -p[1]))
            insert_row(self.plan_tree, (f"{day:%d %b}", f"{day:%a}", text, f"{sum(hours.values()):g}"),
                       tag="warning" if day.weekday() >= 5 else None)
        window = plan["days"][:14]
        codes = sorted(plan["totals"])
        self.plan_bar.set([f"{d:%a %d}" for d, _ in window], [(code, [h.get(code, 0) for _, h in window]) for code in codes],
                          stacked=True, fmt="{:g} h")
        self.plan_donut.set(list(plan["totals"].items()), center=f"{sum(plan['totals'].values()):g} h", sub="planned", fmt="{:g} h")
        items = []
        for code in codes:
            cov = plan["coverage"][code]
            colour = c["success"] if cov >= 1 else c["warning"] if cov >= 0.7 else c["danger"]
            items.append((code, min(cov, 1.0) * 100, colour, f"{code}: {plan['totals'][code]:g} h planned of {plan['need'][code]:g} h needed ({cov:.0%})"))
        self.plan_cover.set(items, fmt="{:.0f}%", max_value=100)
        short_of = [code for code in codes if plan["coverage"][code] < 1]
        self.plan_summary.config(text=("Short on time for: " + ", ".join(short_of) + " - raise hours/day") if short_of
                                 else "Plan covers every syllabus")

    def export_plan(self):
        if not self.plan or not self.plan["days"]:
            return self.ctx.toast("Generate a plan first", "warning")
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="study_plan.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Date", "Subject", "Hours"])
                for day, hours in self.plan["days"]:
                    for code, h in sorted(hours.items()):
                        writer.writerow([day.isoformat(), code, h])
        except OSError as err:
            self.ctx.toast(f"Could not save: {err}", "error")
        else:
            self.ctx.toast("Plan exported", "success")

    # ---------- tab 4: insights ----------
    def build_insights_tab(self):
        tab = self.tab("  \U0001F4CA Insights  ")
        tab.columnconfigure((0, 1), weight=1, uniform="ins")
        tab.rowconfigure(1, weight=1)
        gauge = self.titled_card(tab, "READINESS", "Overall syllabus completion", row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        gauge.columnconfigure(0, weight=1)
        self.gauge = Gauge(gauge, self.ctx.theme, height=160)
        self.gauge.grid(row=2, column=0, columnspan=3, sticky="nsew")
        nxt = self.titled_card(tab, "NEXT UP", "Your next exam", row=0, column=1, sticky="nsew", pady=(0, 10))
        self.next_big = ttk.Label(nxt, text="-", style="StatPrimary.TLabel")
        self.next_big.grid(row=2, column=0, columnspan=3, sticky="w")
        self.next_sub = ttk.Label(nxt, text="", style="CardMuted.TLabel", wraplength=360, justify="left")
        self.next_sub.grid(row=3, column=0, columnspan=3, sticky="w")
        self.risk_row = ttk.Frame(nxt, style="Card.TFrame")
        self.risk_row.grid(row=4, column=0, columnspan=3, sticky="w", pady=(10, 0))
        left = self.titled_card(tab, "COUNTDOWN", "Days left for each exam", row=1, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        self.countdown = HBarChart(left, self.ctx.theme, height=190)
        self.countdown.grid(row=2, column=0, columnspan=3, sticky="nsew")
        right = self.titled_card(tab, "EXAM LOAD", "Exams and exam hours per week", row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        self.load_chart = BarChart(right, self.ctx.theme, height=190)
        self.load_chart.grid(row=2, column=0, columnspan=3, sticky="nsew")

    # ---------- refresh ----------
    def refresh_all(self):
        theme, c = self.ctx.theme, self.ctx.theme.colors
        exams, subjects, today = self.db.exams(), self.db.subject_objects(), date.today()
        by_code = {s.code: s for s in subjects}
        choices = self.choices()
        for box in (self.subject_box, self.prog_box):
            box.configure(values=choices)
        if choices and self.v_subject.get() not in choices:
            self.v_subject.set(choices[0])
        if choices and self.v_prog_subject.get() not in choices:
            self.v_prog_subject.set(choices[0])
        clashes = find_clashes(exams)
        clash_ids = set().union(*[ids for sev, _, ids in clashes if sev == "bad"] or [set()])
        # schedule table
        clear_table(self.tree)
        for e in exams:
            left = e.days_left(today)
            when = "done" if left < 0 else "today" if left == 0 else "tomorrow" if left == 1 else f"{left} days"
            status = "past" if left < 0 else "CLASH" if e.id in clash_ids else "ok"
            tag = "done" if left < 0 else "danger" if e.id in clash_ids or left <= 2 else "warning" if left <= 7 else None
            insert_row(self.tree, (f"{e.date:%d %b %Y}", e.start, e.code, e.kind, e.venue, f"{e.weight}%", when, status), tag=tag, iid=str(e.id))
        for child in self.warn_box.winfo_children():
            child.destroy()
        for row, (sev, message, _) in enumerate(clashes[:5] or [("ok", "No clashes - your timetable looks clean", set())]):
            line = ttk.Frame(self.warn_box, style="Card.TFrame")
            line.grid(row=row, column=0, sticky="w", pady=2)
            badge(line, theme, {"bad": "CLASH", "warn": "WATCH", "ok": "OK"}[sev], {"bad": "bad", "warn": "warn", "ok": "ok"}[sev]).pack(side="left", padx=(0, 8))
            ttk.Label(line, text=message, style="Card.TLabel", wraplength=230, justify="left").pack(side="left")
        self.draw_calendar()
        # subjects
        clear_table(self.sub_tree)
        for s in subjects:
            insert_row(self.sub_tree, (s.code, s.name, s.credits, DIFFICULTY[s.difficulty][4:], f"{s.done}/{s.total}",
                                       f"{s.progress:.0%}", f"{s.need_hours:.1f}"), iid=s.code)
        self.progress_chart.set([(s.code, s.progress * 100, c["success"] if s.progress >= 0.7 else c["warning"] if s.progress >= 0.4 else c["danger"],
                                  f"{s.name}: {s.done} of {s.total} topics done") for s in subjects], fmt="{:.0f}%", max_value=100)
        # plan + insights
        self.draw_plan()
        upcoming = [e for e in exams if e.days_left(today) >= 0]
        weight_sum = sum(by_code[e.code].credits for e in upcoming if e.code in by_code) or 1
        overall = sum(by_code[e.code].progress * by_code[e.code].credits for e in upcoming if e.code in by_code) / weight_sum * 100 if upcoming else 0
        self.gauge.set(overall, "Syllabus ready", f"{len(upcoming)} upcoming exams")
        for child in self.risk_row.winfo_children():
            child.destroy()
        if upcoming:
            nxt = upcoming[0]
            self.next_big.config(text=f"{nxt.days_left(today)} days" if nxt.days_left(today) else "Today")
            subject = by_code.get(nxt.code)
            self.next_sub.config(text=f"{nxt.title()} on {nxt.date:%a %d %b}, {nxt.start} at {nxt.venue or 'venue TBA'}"
                                      + (f"\nSyllabus {subject.progress:.0%} done, about {subject.need_hours:.0f} h still needed" if subject else ""))
            if subject:
                risk = subject.need_hours / max(nxt.days_left(today), 1)
                kind, text = ("bad", "HIGH RISK") if risk > 6 else ("warn", "TIGHT") if risk > 3 else ("ok", "ON TRACK")
                badge(self.risk_row, theme, text, kind).pack(side="left")
        else:
            self.next_big.config(text="-")
            self.next_sub.config(text="No upcoming exams. Add one in the Schedule tab.")
        self.countdown.set([(e.title(), max(e.days_left(today), 0),
                             c["danger"] if e.days_left(today) <= 3 else c["warning"] if e.days_left(today) <= 7 else c["primary"],
                             f"{e.title()}: {e.date:%d %b} at {e.start}") for e in upcoming[:10]], fmt="{:.0f} d")
        load = week_load(upcoming)
        labels = [f"W{w}" for (_, w) in load]
        self.load_chart.set(labels, [("Exams", [n for n, _ in load.values()]), ("Exam hours", [round(h, 1) for _, h in load.values()])])
        theme.recolor(self)
