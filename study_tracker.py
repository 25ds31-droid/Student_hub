"""
Daily Study Hours Tracker & Calculator
--------------------------------------
* Log sessions manually or with a live timer; duration accepts 90, 1.5, 1h30m, 1:30 (regex)
* Goal, streak, 7-day average, moving average (NumPy), weekly report (Pandas)
* Time-budget calculator: free hours in a day -> study hours -> split across subjects by
  difficulty and exam urgency
* OOP: Session -> StudySession -> RevisionSession (multilevel),
       DeepWorkSession(DeepWorkMixin, StudySession) (multiple), polymorphic effective_hours()
"""
import functools
import operator
import re
import sqlite3
import time
from collections import namedtuple
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

import tkinter as tk
from tkinter import ttk, filedialog

from hub_theme import ChartCanvas, DatePicker, add_field, card, clear_table, info_icon, insert_row, make_table

DayEntry = namedtuple("DayEntry", ["name", "day", "activity"])       # 3-field structure (Wk 12)
Plan = namedtuple("Plan", ["subject", "difficulty", "days_left", "hours", "pomodoros"])
TIME_RE = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
SUBJECT_RE = re.compile(r"[\w .&+#-]{1,40}")
KINDS = ["study", "revision", "deep work"]


# ======================= exceptions =======================
class StudyError(Exception):
    """Base class for study-tracker errors."""


class InvalidTimeError(StudyError):
    pass


class InvalidDurationError(StudyError):
    pass


class InvalidSubjectError(StudyError):
    pass


# ======================= OOP model =======================
class Session:
    """Base class: constructor, destructor, validated properties, private minutes."""
    count = 0

    def __init__(self, d, subject, minutes, focus=3, note=""):
        Session.count += 1
        self.date = d
        self.subject = subject
        self.minutes = minutes
        self.focus = focus
        self.note = note
        self.kind = "study"

    def __del__(self):
        try:
            Session.count -= 1
        except Exception:
            pass

    @property
    def date(self):
        return self._date

    @date.setter
    def date(self, value):
        try:
            parsed = datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
        except ValueError:
            raise InvalidTimeError(f"'{value}' is not a valid date (use YYYY-MM-DD)") from None
        if parsed > date.today():
            raise InvalidTimeError("You cannot log study time in the future")
        self._date = parsed.isoformat()

    @property
    def subject(self):
        return self._subject

    @subject.setter
    def subject(self, value):
        value = str(value).strip()
        if not SUBJECT_RE.fullmatch(value):
            raise InvalidSubjectError("Choose or type a subject (up to 40 characters)")
        self._subject = value

    @property
    def minutes(self):
        return self.__minutes

    @minutes.setter
    def minutes(self, value):
        if not isinstance(value, int) or not 1 <= value <= 16 * 60:
            raise InvalidDurationError("Duration must be between 1 minute and 16 hours")
        self.__minutes = value

    @property
    def focus(self):
        return self._focus

    @focus.setter
    def focus(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise StudyError("Focus must be a number from 1 to 5") from None
        if not 1 <= value <= 5:
            raise StudyError("Focus must be between 1 and 5")
        self._focus = value

    def hours(self):
        return self.minutes / 60

    def effective_hours(self):                           # overridden below (polymorphism)
        return self.hours()

    def to_row(self):
        return (self.date, self.subject, self.minutes, self.focus, self.kind, self.note)


class StudySession(Session):                             # single inheritance
    def effective_hours(self):
        return self.hours() * (0.5 + self.focus / 10)    # focus 5 -> 100%, focus 1 -> 60%


class RevisionSession(StudySession):                     # multilevel inheritance
    def __init__(self, d, subject, minutes, focus=3, note=""):
        super().__init__(d, subject, minutes, focus, note)
        self.kind = "revision"

    def effective_hours(self):
        return super().effective_hours() * 1.1           # revising consolidates memory


class DeepWorkMixin:
    BONUS = 1.25

    def effective_hours(self):
        return super().effective_hours() * self.BONUS


class DeepWorkSession(DeepWorkMixin, StudySession):      # multiple inheritance
    def __init__(self, d, subject, minutes, focus=3, note=""):
        super().__init__(d, subject, minutes, focus, note)
        self.kind = "deep work"


def make_session(kind, d, subject, minutes, focus=3, note=""):
    cls = {"revision": RevisionSession, "deep work": DeepWorkSession}.get(kind, StudySession)
    return cls(d, subject, minutes, focus, note)


# ======================= parsing (regular expressions) =======================
def parse_duration(text):
    """'90' -> 90 min | '1.5' -> 1.5 h | '1:30' | '1h30m' | '2h' | '45 min'  ->  minutes"""
    t = text.strip().lower()
    if re.fullmatch(r"\d+", t):
        minutes = int(t)
    elif re.fullmatch(r"\d+\.\d+", t):
        minutes = round(float(t) * 60)
    else:
        clock = re.fullmatch(r"(\d{1,2}):([0-5]\d)", t)
        if clock:
            minutes = int(clock.group(1)) * 60 + int(clock.group(2))
        else:
            m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)\s*h\w*)?\s*(?:(\d+)\s*m\w*)?", t)
            if not m or not (m.group(1) or m.group(2)):
                raise InvalidDurationError("Use 90, 1.5, 1:30 or 1h30m")
            minutes = round(float(m.group(1) or 0) * 60) + int(m.group(2) or 0)
    if not 1 <= minutes <= 16 * 60:
        raise InvalidDurationError("Duration must be between 1 minute and 16 hours")
    return minutes


def minutes_between(start, end):
    """Minutes from 'HH:MM' to 'HH:MM' (an end before the start means it crossed midnight)."""
    stamps = []
    for text in (start, end):
        m = TIME_RE.fullmatch(text.strip())
        if not m:
            raise InvalidTimeError(f"'{text}' is not a time (use HH:MM, 24-hour)")
        stamps.append(int(m.group(1)) * 60 + int(m.group(2)))
    diff = stamps[1] - stamps[0]
    return diff if diff > 0 else diff + 24 * 60


# ======================= calculations =======================
def streak(day_totals, goal, today=None):
    """Consecutive days that met the goal (today may still be in progress)."""
    cursor = today or date.today()
    if day_totals.get(cursor.isoformat(), 0) < goal:
        cursor -= timedelta(days=1)
    count = 0
    while day_totals.get(cursor.isoformat(), 0) >= goal > 0:
        count += 1
        cursor -= timedelta(days=1)
    return count


def last_days(day_totals, n=7, end=None):
    end = end or date.today()
    days = [end - timedelta(days=i) for i in range(n - 1, -1, -1)]
    labels = list(map(lambda d: d.strftime("%a")[:2] + d.strftime(" %d").replace(" 0", " "), days))
    values = list(map(lambda d: round(day_totals.get(d.isoformat(), 0.0), 2), days))
    return labels, values


def moving_average(values, window=7):
    """NumPy moving average; the first points use the available history."""
    if not values:
        return []
    window = max(1, min(window, len(values)))
    padded = np.pad(np.asarray(values, dtype=float), (window - 1, 0), mode="edge")
    return list(np.convolve(padded, np.ones(window) / window, mode="valid"))


def week_calendar(day_totals, goal, end=None):
    """Array of 7 DayEntry items (Mon..Sun) for the week containing `end`."""
    end = end or date.today()
    monday = end - timedelta(days=end.weekday())
    week = []
    for i in range(7):
        d = monday + timedelta(days=i)
        hours = day_totals.get(d.isoformat(), 0.0)
        week.append(DayEntry(d.strftime("%a"), d.day, f"{hours:.1f} h" + ("  goal met" if hours >= goal > 0 else "")))
    return week


def time_budget(sleep, college, travel, meals, exercise, leisure):
    """Hours left in a 24-hour day after fixed activities, and a realistic study allowance."""
    parts = [sleep, college, travel, meals, exercise, leisure]
    if any(p < 0 for p in parts):
        raise StudyError("Hours cannot be negative")
    used = functools.reduce(operator.add, parts)
    if used > 24:
        raise StudyError(f"Your day adds up to {used:g} hours - more than 24!")
    free = 24 - used
    return {"used": used, "free": free, "study": round(free * 0.8 * 4) / 4}     # keep 20% buffer


def allocate_hours(subjects, available, today=None):
    """subjects = [(name, difficulty 1-5, exam_date or '')]. Harder + closer exam -> more hours."""
    if not subjects:
        raise StudyError("Add subjects first")
    today = today or date.today()
    names, diffs, left = [], [], []
    for name, difficulty, exam in subjects:
        try:
            days = (datetime.strptime(exam, "%Y-%m-%d").date() - today).days if exam else 30
        except ValueError:
            days = 30
        names.append(name)
        diffs.append(difficulty)
        left.append(max(days, 0))
    weights = np.array(diffs, dtype=float) * (1 + 14 / (np.array(left, dtype=float) + 1))
    hours = np.round(weights / weights.sum() * available * 4) / 4              # quarter-hour steps
    return [Plan(n, d, l, float(h), int(round(h * 60 / 30))) for n, d, l, h in zip(names, diffs, left, hours)]


# ======================= database =======================
class StudyDB:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS sessions(
                id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, subject TEXT NOT NULL,
                minutes INTEGER NOT NULL, focus INTEGER NOT NULL, kind TEXT NOT NULL, note TEXT);
            CREATE TABLE IF NOT EXISTS subjects(
                name TEXT PRIMARY KEY, difficulty INTEGER NOT NULL DEFAULT 3, exam_date TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        """)

    def add_session(self, s):
        self.con.execute("INSERT INTO sessions(date,subject,minutes,focus,kind,note) VALUES (?,?,?,?,?,?)", s.to_row())
        self.con.commit()

    def delete_session(self, session_id):
        self.con.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        self.con.commit()

    def recent(self, limit=60):
        return self.con.execute("SELECT id,date,subject,minutes,focus,kind,note FROM sessions "
                                "ORDER BY date DESC, id DESC LIMIT ?", (limit,)).fetchall()

    def day_totals(self):
        return dict(self.con.execute("SELECT date, SUM(minutes)/60.0 FROM sessions GROUP BY date").fetchall())

    def subject_totals(self, days=7):
        since = (date.today() - timedelta(days=days - 1)).isoformat()
        return self.con.execute("SELECT subject, SUM(minutes)/60.0, COUNT(*), AVG(focus) FROM sessions "
                                "WHERE date>=? GROUP BY subject ORDER BY 2 DESC", (since,)).fetchall()

    def goal(self):
        row = self.con.execute("SELECT value FROM settings WHERE key='goal'").fetchone()
        return float(row[0]) if row else 4.0

    def set_goal(self, hours):
        self.con.execute("INSERT OR REPLACE INTO settings VALUES ('goal', ?)", (str(hours),))
        self.con.commit()

    def subjects(self):
        return self.con.execute("SELECT name, difficulty, exam_date FROM subjects ORDER BY name").fetchall()

    def add_subject(self, name, difficulty=3, exam_date=""):
        name = name.strip()
        if not SUBJECT_RE.fullmatch(name):
            raise InvalidSubjectError("Subject names can use letters, digits and . & + # -")
        if exam_date:
            try:
                datetime.strptime(exam_date, "%Y-%m-%d")
            except ValueError:
                raise InvalidTimeError("Exam date must be YYYY-MM-DD") from None
        self.con.execute("INSERT OR REPLACE INTO subjects VALUES (?,?,?)", (name, int(difficulty), exam_date))
        self.con.commit()

    def delete_subject(self, name):
        self.con.execute("DELETE FROM subjects WHERE name=?", (name,))
        self.con.commit()


def weekly_report(db):
    """Text report built with Pandas (groupby, pivot_table, fillna, describe)."""
    rows = db.recent(2000)
    since = (date.today() - timedelta(days=6)).isoformat()
    df = pd.DataFrame(rows, columns=["id", "date", "subject", "minutes", "focus", "kind", "note"])
    df = df[df["date"] >= since].dropna(subset=["minutes"])
    if df.empty:
        return "No study sessions in the last 7 days."
    df["hours"] = df["minutes"] / 60
    by_subject = df.groupby("subject").agg(sessions=("id", "count"), hours=("hours", "sum"),
                                           avg_focus=("focus", "mean")).round(2).sort_values("hours", ascending=False)
    grid = df.pivot_table(index="subject", columns="date", values="hours", aggfunc="sum").fillna(0).round(1)
    per_day = df.groupby("date")["hours"].sum()
    best = per_day.idxmax()
    lines = ["=" * 60, f"STUDY REPORT - last 7 days (to {date.today().isoformat()})", "=" * 60,
             f"Total: {df['hours'].sum():.1f} h over {per_day.size} days   |   Daily mean: {per_day.mean():.1f} h",
             f"Best day: {best} ({per_day.max():.1f} h)   |   Average focus: {df['focus'].mean():.1f}/5",
             "", "BY SUBJECT (groupby)", by_subject.to_string(),
             "", "SUBJECT x DAY HOURS (pivot_table + fillna)", grid.to_string(),
             "", "DAILY HOURS (describe)", per_day.describe().round(2).to_string()]
    return "\n".join(lines)


def summary(path_to_db):
    """Numbers for the dashboard."""
    db = StudyDB(path_to_db)
    totals, goal = db.day_totals(), db.goal()
    labels, values = last_days(totals, 7)
    return {"today": totals.get(date.today().isoformat(), 0.0), "goal": goal, "labels": labels,
            "values": values, "streak": streak(totals, goal)}


# ======================= GUI =======================
class StudyPage(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.db = StudyDB(ctx.path("study.db"))
        self.timer_start = None
        self.timer_job = None
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.build_log_tab()
        self.build_stats_tab()
        self.build_calc_tab()
        self.build_subjects_tab()
        self.refresh_all()

    def on_show(self):
        self.refresh_all()

    # ---------- tab 1: log ----------
    def build_log_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \u23F1 Log session  ")
        tab.columnconfigure(1, weight=1)
        form = card(tab)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Label(form, text="New session", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.v_date = tk.StringVar(value=date.today().isoformat())
        self.v_subject = tk.StringVar()
        self.v_kind = tk.StringVar(value="study")
        self.v_duration = tk.StringVar()
        self.v_start, self.v_end = tk.StringVar(), tk.StringVar()
        self.v_focus = tk.IntVar(value=4)
        self.v_note = tk.StringVar()
        self.date_picker = add_field(form, 1, "Date", DatePicker(form, years_back=1, years_ahead=0))
        self.subject_box = add_field(form, 2, "Subject", ttk.Combobox(form, textvariable=self.v_subject, width=20))
        add_field(form, 3, "Type", ttk.Combobox(form, textvariable=self.v_kind, values=KINDS, state="readonly", width=20))
        add_field(form, 4, "Duration", ttk.Combobox(form, textvariable=self.v_duration, values=["15", "25", "30", "45", "60", "90", "120", "180"], width=20))
        info_icon(form, "Pick a number of minutes from the list or type your own.\nAccepted: 90, 1.5 (hours), 1:30, 1h30m").grid(row=4, column=2, padx=4)
        add_field(form, 6, "or Start (HH:MM)", ttk.Entry(form, textvariable=self.v_start, width=22))
        add_field(form, 7, "End (HH:MM)", ttk.Entry(form, textvariable=self.v_end, width=22))
        add_field(form, 8, "Focus (1-5)", ttk.Spinbox(form, from_=1, to=5, textvariable=self.v_focus, width=20))
        add_field(form, 9, "Note", ttk.Entry(form, textvariable=self.v_note, width=22))
        ttk.Button(form, text="Add session", style="Accent.TButton", command=self.add_session).grid(
            row=10, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Separator(form).grid(row=11, column=0, columnspan=2, sticky="ew", pady=12)
        ttk.Label(form, text="Live timer", style="CardTitle.TLabel").grid(row=12, column=0, sticky="w")
        self.timer_label = ttk.Label(form, text="00:00:00", style="Stat.TLabel")
        self.timer_label.grid(row=13, column=0, columnspan=2, sticky="w")
        buttons = ttk.Frame(form, style="Card.TFrame")
        buttons.grid(row=14, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="Start", command=self.timer_toggle).pack(side="left")
        ttk.Button(buttons, text="Stop & fill duration", command=self.timer_stop).pack(side="left", padx=6)

        right = card(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Recent sessions", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        frame, self.tree = make_table(right, [("date", "Date", 95, "w"), ("subject", "Subject", 150, "w"),
                                              ("minutes", "Minutes", 70, "e"), ("focus", "Focus", 55, "center"),
                                              ("kind", "Type", 90, "w"), ("note", "Note", 220, "w")], height=14)
        frame.grid(row=1, column=0, sticky="nsew")
        ttk.Button(right, text="Delete selected", command=self.delete_selected).grid(row=2, column=0, sticky="e", pady=(8, 0))

    def add_session(self):
        try:
            if self.v_duration.get().strip():
                minutes = parse_duration(self.v_duration.get())
            elif self.v_start.get().strip() and self.v_end.get().strip():
                minutes = minutes_between(self.v_start.get(), self.v_end.get())
            else:
                raise InvalidDurationError("Enter a duration, or a start and end time")
            session = make_session(self.v_kind.get(), self.date_picker.iso(), self.v_subject.get(), minutes,
                                   self.v_focus.get(), self.v_note.get().strip())
            self.db.add_session(session)
        except (StudyError, tk.TclError) as err:
            return self.ctx.toast(str(err), "error")
        self.ctx.toast(f"Logged {minutes} min of {session.subject}  (focus-weighted {session.effective_hours():.1f} h)", "success")
        for var in (self.v_duration, self.v_start, self.v_end, self.v_note):
            var.set("")
        self.refresh_all()

    def delete_selected(self):
        for item in self.tree.selection():
            self.db.delete_session(self.tree.item(item)["values"][0])
        self.refresh_all()

    def timer_toggle(self):
        if self.timer_start is None:
            self.timer_start = time.monotonic()
            self.tick()
            self.ctx.toast("Timer started - good luck!", "info")
        else:
            self.timer_stop()

    def tick(self):
        if self.timer_start is None:
            return
        elapsed = int(time.monotonic() - self.timer_start)
        self.timer_label.config(text=f"{elapsed // 3600:02d}:{elapsed % 3600 // 60:02d}:{elapsed % 60:02d}")
        self.timer_job = self.after(1000, self.tick)

    def timer_stop(self):
        if self.timer_start is None:
            return
        minutes = max(1, round((time.monotonic() - self.timer_start) / 60))
        self.timer_start = None
        if self.timer_job:
            self.after_cancel(self.timer_job)
        self.timer_label.config(text="00:00:00")
        self.v_duration.set(str(minutes))
        self.ctx.toast(f"{minutes} min recorded - pick a subject and press Add session", "success")

    # ---------- tab 2: statistics ----------
    def build_stats_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F4C8 Statistics  ")
        tab.columnconfigure((0, 1, 2, 3), weight=1)
        self.stat_labels = {}
        for col, (key, title) in enumerate((("today", "Today"), ("avg", "7-day average"),
                                            ("streak", "Goal streak"), ("best", "Best day (14 d)"))):
            box = card(tab)
            box.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 10, 0))
            ttk.Label(box, text=title, style="CardMuted.TLabel").pack(anchor="w")
            self.stat_labels[key] = ttk.Label(box, text="-", style="Stat.TLabel")
            self.stat_labels[key].pack(anchor="w")
        self.goal_bar = ttk.Progressbar(tab, maximum=100)
        self.goal_bar.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        self.goal_text = ttk.Label(tab, text="", style="Muted.TLabel")
        self.goal_text.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 8))
        chart_card = card(tab)
        chart_card.grid(row=3, column=0, columnspan=3, sticky="nsew")
        ttk.Label(chart_card, text="Hours per day (dashed line = goal)", style="CardTitle.TLabel").pack(anchor="w")
        self.chart = ChartCanvas(chart_card, self.ctx.theme, height=210)
        self.chart.pack(fill="both", expand=True, pady=(6, 0))
        subj = card(tab)
        subj.grid(row=3, column=3, sticky="nsew", padx=(10, 0))
        ttk.Label(subj, text="By subject (7 days)", style="CardTitle.TLabel").pack(anchor="w")
        frame, self.subject_tree = make_table(subj, [("s", "Subject", 100, "w"), ("h", "Hours", 55, "e")], height=7)
        frame.pack(fill="both", expand=True, pady=(6, 0))
        self.week_frame = ttk.Frame(tab)
        self.week_frame.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        ttk.Button(tab, text="Weekly report (Pandas)", command=self.show_report).grid(row=5, column=0, sticky="w", pady=(10, 0))
        ttk.Button(tab, text="Charts (Matplotlib)", command=self.show_charts).grid(row=5, column=1, sticky="w", pady=(10, 0))
        tab.rowconfigure(3, weight=1)

    def show_report(self):
        text = weekly_report(self.db)
        win = tk.Toplevel(self)
        win.title("Weekly study report")
        win.geometry("760x560")
        box = tk.Text(win, font=("Consolas", 10), wrap="none")
        box.insert("1.0", text)
        box.config(state="disabled")
        box.pack(fill="both", expand=True)
        ttk.Button(win, text="Save as .txt", command=lambda: self.save_text(text)).pack(pady=8)
        self.ctx.theme.recolor(win)

    def save_text(self, text):
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="study_report.txt")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as err:
            self.ctx.toast(f"Could not save: {err}", "error")
        else:
            self.ctx.toast("Report saved", "success")

    def show_charts(self):
        try:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        except ImportError:
            return self.ctx.toast("Install matplotlib:  pip install matplotlib", "error")
        totals = self.db.day_totals()
        labels, values = last_days(totals, 14)
        win = tk.Toplevel(self)
        win.title("Study charts")
        fig = Figure(figsize=(10.5, 4.4), dpi=90)
        ax1, ax2 = fig.add_subplot(121), fig.add_subplot(122)
        ax1.bar(range(len(values)), values, label="Hours")
        ax1.plot(range(len(values)), moving_average(values, 7), color=self.ctx.theme.colors["warning"], marker="o", label="7-day average")
        ax1.axhline(self.db.goal(), linestyle="--", color=self.ctx.theme.colors["danger"], label="Goal")
        ax1.set_xticks(range(len(labels)), labels, rotation=60, fontsize=8)
        ax1.set_title("Last 14 days")
        ax1.legend()
        rows = self.db.subject_totals(30)
        if rows:
            ax2.pie([r[1] for r in rows], labels=[r[0] for r in rows], autopct="%1.0f%%", startangle=90)
        ax2.set_title("Share by subject (30 days)")
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------- tab 3: calculator ----------
    def build_calc_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F9EE Hours calculator  ")
        tab.columnconfigure(1, weight=1)
        left = card(tab)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Label(left, text="Where does your day go?", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.budget_vars = {}
        for i, (key, label, default) in enumerate((("sleep", "Sleep", 7), ("college", "College", 6), ("travel", "Travel", 2),
                                                   ("meals", "Meals & chores", 2), ("exercise", "Exercise", 1),
                                                   ("leisure", "Leisure & phone", 2))):
            self.budget_vars[key] = tk.DoubleVar(value=default)
            add_field(left, i + 1, label + " (h)", ttk.Spinbox(left, from_=0, to=24, increment=0.5,
                                                               textvariable=self.budget_vars[key], width=10))
        ttk.Button(left, text="Calculate", style="Accent.TButton", command=self.calculate).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.budget_result = ttk.Label(left, text="", style="Card.TLabel", justify="left")
        self.budget_result.grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(left, text="Use as my daily goal", command=self.use_as_goal).grid(row=10, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        right = card(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Suggested split across your subjects (harder subject / closer exam = more time)",
                  style="CardTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        frame, self.plan_tree = make_table(right, [("s", "Subject", 170, "w"), ("d", "Difficulty", 80, "center"),
                                                   ("l", "Days to exam", 95, "center"), ("h", "Hours / day", 90, "e"),
                                                   ("p", "Pomodoros", 80, "e")], height=12)
        frame.grid(row=1, column=0, sticky="nsew")
        self.available_hours = 0.0

    def calculate(self):
        try:
            result = time_budget(*(var.get() for var in self.budget_vars.values()))
        except (StudyError, tk.TclError) as err:
            return self.ctx.toast(str(err), "error")
        self.available_hours = result["study"]
        self.budget_result.config(text=f"Fixed activities: {result['used']:g} h\nFree time: {result['free']:g} h\n"
                                       f"Realistic study time: {result['study']:g} h")
        clear_table(self.plan_tree)
        try:
            for plan in allocate_hours(self.db.subjects(), result["study"]):
                insert_row(self.plan_tree, (plan.subject, plan.difficulty, plan.days_left,
                                            f"{plan.hours:.2f}", plan.pomodoros))
        except StudyError as err:
            self.ctx.toast(str(err) + " (Subjects tab)", "warning")

    def use_as_goal(self):
        if self.available_hours <= 0:
            return self.ctx.toast("Press Calculate first", "warning")
        self.db.set_goal(self.available_hours)
        self.ctx.toast(f"Daily goal set to {self.available_hours:g} hours", "success")
        self.refresh_all()

    # ---------- tab 4: subjects & goal ----------
    def build_subjects_tab(self):
        tab = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(tab, text="  \U0001F3AF Subjects & goal  ")
        tab.columnconfigure(1, weight=1)
        form = card(tab)
        form.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        ttk.Label(form, text="Add subject", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.s_name, self.s_diff, self.s_exam = tk.StringVar(), tk.IntVar(value=3), tk.StringVar()
        add_field(form, 1, "Name", ttk.Entry(form, textvariable=self.s_name, width=22))
        add_field(form, 2, "Difficulty (1-5)", ttk.Spinbox(form, from_=1, to=5, textvariable=self.s_diff, width=20))
        add_field(form, 3, "Exam date", ttk.Entry(form, textvariable=self.s_exam, width=22))
        ttk.Label(form, text="YYYY-MM-DD (optional)", style="CardMuted.TLabel").grid(row=4, column=1, sticky="w")
        ttk.Button(form, text="Save subject", style="Accent.TButton", command=self.save_subject).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(form, text="Import from Exam Scheduler", command=self.import_subjects).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Separator(form).grid(row=7, column=0, columnspan=2, sticky="ew", pady=12)
        self.v_goal = tk.DoubleVar(value=self.db.goal())
        add_field(form, 8, "Daily goal (h)", ttk.Spinbox(form, from_=0.5, to=16, increment=0.5, textvariable=self.v_goal, width=20))
        ttk.Button(form, text="Save goal", command=self.save_goal).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        right = card(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        frame, self.sub_tree = make_table(right, [("n", "Subject", 200, "w"), ("d", "Difficulty", 90, "center"),
                                                  ("e", "Exam date", 110, "center")], height=12)
        frame.grid(row=1, column=0, sticky="nsew")
        ttk.Button(right, text="Delete selected", command=self.delete_subject).grid(row=2, column=0, sticky="e", pady=(8, 0))

    def save_subject(self):
        try:
            self.db.add_subject(self.s_name.get(), self.s_diff.get(), self.s_exam.get().strip())
        except (StudyError, tk.TclError) as err:
            return self.ctx.toast(str(err), "error")
        self.s_name.set("")
        self.s_exam.set("")
        self.refresh_all()

    def delete_subject(self):
        for item in self.sub_tree.selection():
            self.db.delete_subject(self.sub_tree.item(item)["values"][0])
        self.refresh_all()

    def save_goal(self):
        try:
            self.db.set_goal(float(self.v_goal.get()))
        except (ValueError, tk.TclError):
            return self.ctx.toast("Enter the goal in hours, e.g. 4", "error")
        self.ctx.toast("Goal saved", "success")
        self.refresh_all()

    def import_subjects(self):
        try:
            import exam_scheduler
            names = [code for code, _ in exam_scheduler.Database(self.ctx.path("exam_scheduler.db")).subjects()]
        except (ImportError, sqlite3.Error) as err:
            return self.ctx.toast(f"Could not read the Exam Scheduler: {err}", "error")
        existing = {row[0] for row in self.db.subjects()}
        added = 0
        for name in names:
            if name not in existing:
                self.db.add_subject(name)
                added += 1
        self.ctx.toast(f"Imported {added} subjects from the Exam Scheduler", "success" if added else "info")
        self.refresh_all()

    # ---------- refresh ----------
    def refresh_all(self):
        totals, goal = self.db.day_totals(), self.db.goal()
        self.subject_box["values"] = [row[0] for row in self.db.subjects()]
        clear_table(self.tree)
        for sid, d, subject, minutes, focus, kind, note in self.db.recent():
            insert_row(self.tree, (sid, d, subject, minutes, focus, kind, note or ""))
        clear_table(self.sub_tree)
        for name, diff, exam in self.db.subjects():
            insert_row(self.sub_tree, (name, diff, exam or "-"))
        today_hours = totals.get(date.today().isoformat(), 0.0)
        labels, values = last_days(totals, 14)
        recent14 = dict(zip(labels, values))
        best = max(values) if values else 0
        self.stat_labels["today"].config(text=f"{today_hours:.1f} h")
        self.stat_labels["avg"].config(text=f"{sum(values[-7:]) / 7:.1f} h")
        self.stat_labels["streak"].config(text=f"{streak(totals, goal)} d")
        self.stat_labels["best"].config(text=f"{best:.1f} h")
        pct = min(100, today_hours / goal * 100) if goal else 0
        self.goal_bar.config(value=pct, style="Success.Horizontal.TProgressbar" if pct >= 100 else "Horizontal.TProgressbar")
        self.goal_text.config(text=f"Today: {today_hours:.1f} of {goal:g} h goal ({pct:.0f}%)")
        self.chart.set(labels, values, goal)
        clear_table(self.subject_tree)
        for subject, hours, _count, _focus in self.db.subject_totals(7):
            insert_row(self.subject_tree, (subject, f"{hours:.1f}"))
        for child in self.week_frame.winfo_children():
            child.destroy()
        for i, entry in enumerate(week_calendar(totals, goal)):
            self.week_frame.columnconfigure(i, weight=1)
            box = card(self.week_frame, padding=8)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            ttk.Label(box, text=f"{entry.name} {entry.day}", style="CardMuted.TLabel").pack()
            ttk.Label(box, text=entry.activity, style="Card.TLabel").pack()
        self.ctx.theme.recolor(self)
