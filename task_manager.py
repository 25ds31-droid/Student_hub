"""
Task & Deadline Manager
-----------------------
* Quick-add with natural text:  "Submit DBMS file by 12.10.2026 !high #college"  (regular expressions)
* Overdue / due-today alerts, week calendar strip, "focus list" chosen with a heap (heapq.nlargest)
* OOP: Task -> Assignment -> ExamPrep (multilevel); urgency() is overridden (polymorphism)
"""
import heapq
import re
import sqlite3
from collections import namedtuple
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import ttk

from hub_charts import BarChart, DonutChart, HBarChart
from hub_theme import (DatePicker, Tooltip, add_field, badge, card, clear_table, info_icon, insert_row, make_table,
                       titled_card)

DayEntry = namedtuple("DayEntry", ["name", "day", "activity"])
PRIORITY_NAMES = {1: "High", 2: "Medium", 3: "Low"}
PRIORITY_NUMBERS = {"high": 1, "h": 1, "1": 1, "medium": 2, "med": 2, "m": 2, "2": 2, "low": 3, "l": 3, "3": 3}
CATEGORIES = ["College", "Assignment", "Exam", "Personal", "Project", "Other"]
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})\b")
PRIORITY_RE = re.compile(r"!(high|medium|med|low|[hml123])\b", re.I)
CATEGORY_RE = re.compile(r"#(\w+)")
RELATIVE_RE = re.compile(r"\b(today|tomorrow|in (\d{1,3}) days?|(?:next )?(monday|tuesday|wednesday|thursday|friday|saturday|sunday))\b", re.I)


class TaskError(Exception):
    """Base class for task errors."""


class InvalidTaskError(TaskError):
    pass


# ======================= OOP model =======================
class Task:
    count = 0
    WEIGHT = 1.0

    def __init__(self, title, due, priority=2, category="Other", done=False):
        Task.count += 1
        self.title = title
        self.due = due
        self.priority = priority
        self.category = category
        self.done = bool(done)

    def __del__(self):
        try:
            Task.count -= 1
        except Exception:
            pass

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        value = str(value).strip()
        if len(value) < 2:
            raise InvalidTaskError("Give the task a title (at least 2 characters)")
        self._title = value

    @property
    def due(self):
        return self._due

    @due.setter
    def due(self, value):
        try:
            self._due = datetime.strptime(str(value).strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            raise InvalidTaskError("Due date must be YYYY-MM-DD") from None

    @property
    def priority(self):
        return self._priority

    @priority.setter
    def priority(self, value):
        if value not in PRIORITY_NAMES:
            raise InvalidTaskError("Priority must be 1 (high), 2 (medium) or 3 (low)")
        self._priority = value

    def days_left(self, today=None):
        return (datetime.strptime(self.due, "%Y-%m-%d").date() - (today or date.today())).days

    def status(self, today=None):
        if self.done:
            return "Done"
        left = self.days_left(today)
        return "Overdue" if left < 0 else "Today" if left == 0 else "Pending"

    def urgency(self, today=None):
        """Higher = more urgent. Overdue tasks jump to the top."""
        if self.done:
            return -1.0
        left = self.days_left(today)
        base = (4 - self.priority) * self.WEIGHT
        return base * 10 if left < 0 else base / (left + 1)


class Assignment(Task):                                  # single inheritance
    WEIGHT = 1.4


class ExamPrep(Assignment):                              # multilevel inheritance
    WEIGHT = 2.0


def make_task(title, due, priority, category, done=False):
    cls = {"Exam": ExamPrep, "Assignment": Assignment}.get(category, Task)
    return cls(title, due, priority, category, done)


# ======================= regex quick-add =======================
def parse_quick_task(text, today=None):
    """'Submit DBMS file by 12.10.2026 !high #college' -> dict(title, due, priority, category)"""
    today = today or date.today()
    work = text
    due = today + timedelta(days=1)                           # default: tomorrow
    m = DATE_RE.search(work)
    if m:
        day, month, year = map(int, m.groups())
        year += 2000 if year < 100 else 0
        try:
            due = date(year, month, day)
        except ValueError:
            raise InvalidTaskError(f"'{m.group(0)}' is not a real date") from None
        work = work.replace(m.group(0), " ", 1)
    else:
        r = RELATIVE_RE.search(work)
        if r:
            word = r.group(1).lower()
            if word == "today":
                due = today
            elif word == "tomorrow":
                due = today + timedelta(days=1)
            elif r.group(2):
                due = today + timedelta(days=int(r.group(2)))
            else:
                ahead = (WEEKDAYS.index(r.group(3).lower()) - today.weekday()) % 7 or 7
                due = today + timedelta(days=ahead)
            work = work.replace(r.group(0), " ", 1)
    priority = 2
    p = PRIORITY_RE.search(work)
    if p:
        priority = PRIORITY_NUMBERS[p.group(1).lower()]
        work = work.replace(p.group(0), " ", 1)
    category = "Other"
    c = CATEGORY_RE.search(work)
    if c:
        wanted = c.group(1).lower()
        category = next((cat for cat in CATEGORIES if cat.lower() == wanted), "Other")
        work = work.replace(c.group(0), " ", 1)
    title = re.sub(r"\b(?:by|on|due|before)\s*$", "", " ".join(work.split()), flags=re.I).strip()
    if "exam" in title.lower() and category == "Other":
        category = "Exam"
    return {"title": title, "due": due.isoformat(), "priority": priority, "category": category}


# ======================= database =======================
class TaskDB:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.execute("""CREATE TABLE IF NOT EXISTS tasks(
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, due TEXT NOT NULL,
            priority INTEGER NOT NULL, category TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0)""")
        self.con.commit()

    def add(self, task):
        self.con.execute("INSERT INTO tasks(title,due,priority,category,done) VALUES (?,?,?,?,?)",
                         (task.title, task.due, task.priority, task.category, int(task.done)))
        self.con.commit()

    def toggle(self, task_id):
        self.con.execute("UPDATE tasks SET done = 1 - done WHERE id=?", (task_id,))
        self.con.commit()

    def delete(self, task_id):
        self.con.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.con.commit()

    def rows(self):
        return self.con.execute("SELECT id,title,due,priority,category,done FROM tasks ORDER BY due, priority").fetchall()

    def objects(self):
        out = []
        for tid, title, due, pr, cat, done in self.rows():
            try:
                task = make_task(title, due, pr, cat, done)
            except TaskError:
                continue
            task.id = tid
            out.append(task)
        return out

    def summary(self):
        counts = {"Pending": 0, "Overdue": 0, "Today": 0, "Done": 0}
        for task in self.objects():
            counts[task.status()] += 1
        return counts

    def focus_list(self, n=5):
        pending = [t for t in self.objects() if not t.done]
        return heapq.nlargest(n, pending, key=lambda t: t.urgency())          # heap-based top-N


def week_calendar(tasks, today=None):
    """Array of 7 DayEntry items (Mon..Sun) listing how many tasks fall on each day."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    week = []
    for i in range(7):
        d = monday + timedelta(days=i)
        n = sum(1 for t in tasks if t.due == d.isoformat() and not t.done)
        week.append(DayEntry(d.strftime("%a"), d.day, f"{n} due" if n else "free"))
    return week


# ======================= GUI =======================
class TaskPage(ttk.Frame):
    FILTERS = ["All", "Pending", "Overdue", "Today", "Done"]

    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.db = TaskDB(ctx.path("tasks.db"))
        self.filter = tk.StringVar(value="Pending")
        self.build()
        self.refresh()

    def on_show(self):
        self.refresh()

    def build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)
        self.week_frame = ttk.Frame(self)
        self.week_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 10))
        form = titled_card(self, "NEW TASK", "Quick add", grid=dict(row=1, column=0, sticky="ns", padx=(16, 10), pady=(0, 16)))
        form.columnconfigure(1, weight=1)
        self.v_quick = tk.StringVar()
        quick = ttk.Entry(form, textvariable=self.v_quick, width=30)
        quick.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 2))
        quick.bind("<Return>", lambda event: self.quick_add())
        info_icon(form, "Examples:\n  Submit DBMS file by 12.10.2026 !high #college\n  Study for physics exam in 3 days !1\n"
                        "  Lab record next friday !low #assignment\nUse ! for priority and # for category.").grid(row=2, column=2, padx=4)
        ttk.Button(form, text="Add from text", style="Accent.TButton", command=self.quick_add).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Separator(form).grid(row=4, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(form, text="Or fill the form", style="CardTitle.TLabel").grid(row=5, column=0, columnspan=3, sticky="w")
        self.v_title = tk.StringVar()
        self.v_priority, self.v_category = tk.StringVar(value="Medium"), tk.StringVar(value="College")
        add_field(form, 6, "Title", ttk.Entry(form, textvariable=self.v_title, width=24))
        self.due_picker = add_field(form, 7, "Due date", DatePicker(form, value=date.today() + timedelta(days=1), years_ahead=2))
        add_field(form, 8, "Priority", ttk.Combobox(form, textvariable=self.v_priority, values=list(PRIORITY_NAMES.values()), state="readonly", width=22))
        add_field(form, 9, "Category", ttk.Combobox(form, textvariable=self.v_category, values=CATEGORIES, state="readonly", width=22))
        ttk.Button(form, text="Add task", command=self.add_task).grid(row=10, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Separator(form).grid(row=11, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Label(form, text="FOCUS LIST", style="CardEyebrow.TLabel").grid(row=12, column=0, columnspan=3, sticky="w")
        self.focus_box = ttk.Frame(form, style="Card.TFrame")
        self.focus_box.grid(row=13, column=0, columnspan=3, sticky="w", pady=(4, 0))

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(0, 16), pady=(0, 16))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=1)
        table = titled_card(right, "ALL TASKS", "Your task list", grid=dict(row=0, column=0, sticky="nsew"))
        table.rowconfigure(3, weight=1)
        table.columnconfigure(0, weight=1)
        bar = ttk.Frame(table, style="Card.TFrame")
        bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(bar, text="Show", style="CardMuted.TLabel").pack(side="left", padx=(0, 6))
        picker = ttk.Combobox(bar, textvariable=self.filter, values=self.FILTERS, state="readonly", width=12)
        picker.pack(side="left")
        picker.bind("<<ComboboxSelected>>", lambda event: self.refresh())
        self.count_label = ttk.Label(bar, text="", style="CardMuted.TLabel")
        self.count_label.pack(side="right")
        frame, self.tree = make_table(table, [("id", "ID", 40, "center"), ("title", "Task", 250, "w"),
                                              ("due", "Due", 95, "center"), ("left", "In", 80, "center"),
                                              ("pr", "Priority", 75, "center"), ("cat", "Category", 95, "w"),
                                              ("st", "Status", 80, "center")], height=7)
        frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        buttons = ttk.Frame(table, style="Card.TFrame")
        buttons.grid(row=4, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Mark done / undo", command=self.toggle).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete", style="Danger.TButton", command=self.delete).pack(side="left")

        charts = ttk.Frame(right)
        charts.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        charts.columnconfigure((0, 2), weight=2, uniform="tc")
        charts.columnconfigure(1, weight=3, uniform="tc")
        spec = [("STATUS", "Where tasks stand", DonutChart), ("WORKLOAD", "Pending tasks, next 14 days", BarChart),
                ("CATEGORIES", "Pending by category", HBarChart)]
        self.charts = []
        for i, (eyebrow, title, cls) in enumerate(spec):
            box = titled_card(charts, eyebrow, title, grid=dict(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0)))
            box.columnconfigure(0, weight=1)
            chart = cls(box, self.ctx.theme, height=170)
            chart.grid(row=2, column=0, columnspan=3, sticky="nsew")
            self.charts.append(chart)

    def quick_add(self):
        try:
            data = parse_quick_task(self.v_quick.get())
            task = make_task(data["title"], data["due"], data["priority"], data["category"])
            self.db.add(task)
        except TaskError as err:
            return self.ctx.toast(str(err), "error")
        self.v_quick.set("")
        self.ctx.toast(f"Added '{task.title}' - due {task.due}, {PRIORITY_NAMES[task.priority]} priority", "success")
        self.refresh()

    def add_task(self):
        priority = {v: k for k, v in PRIORITY_NAMES.items()}[self.v_priority.get()]
        try:
            self.db.add(make_task(self.v_title.get(), self.due_picker.iso(), priority, self.v_category.get()))
        except TaskError as err:
            return self.ctx.toast(str(err), "error")
        self.v_title.set("")
        self.ctx.toast("Task added", "success")
        self.refresh()

    def toggle(self):
        for item in self.tree.selection():
            self.db.toggle(self.tree.item(item)["values"][0])
        self.refresh()

    def delete(self):
        for item in self.tree.selection():
            self.db.delete(self.tree.item(item)["values"][0])
        self.refresh()

    def refresh(self):
        theme, c = self.ctx.theme, self.ctx.theme.colors
        tasks = self.db.objects()
        wanted = self.filter.get()
        clear_table(self.tree)
        shown = 0
        for t in tasks:
            status = t.status()
            if wanted != "All" and status != wanted:
                continue
            shown += 1
            left = t.days_left()
            text = "overdue" if left < 0 and not t.done else "today" if left == 0 else f"{left} d"
            tag = {"Overdue": "danger", "Today": "warning", "Done": "done"}.get(status)
            insert_row(self.tree, (t.id, t.title, t.due, text if not t.done else "-",
                                   PRIORITY_NAMES[t.priority], t.category, status), tag=tag)
        self.count_label.config(text=f"{shown} shown")
        # focus list as badges
        for child in self.focus_box.winfo_children():
            child.destroy()
        focus = self.db.focus_list(3)
        for i, t in enumerate(focus):
            line = ttk.Frame(self.focus_box, style="Card.TFrame")
            line.grid(row=i, column=0, sticky="w", pady=2)
            kind = {"Overdue": "bad", "Today": "warn"}.get(t.status(), "info")
            badge(line, theme, t.status().upper(), kind).pack(side="left", padx=(0, 8))
            ttk.Label(line, text=t.title, style="Card.TLabel", wraplength=190).pack(side="left")
        if not focus:
            ttk.Label(self.focus_box, text="Nothing pending - enjoy!", style="CardMuted.TLabel").grid(row=0, column=0)
        # week strip: coloured chip per day, details on hover
        for child in self.week_frame.winfo_children():
            child.destroy()
        today = date.today()
        for i, entry in enumerate(week_calendar(tasks)):
            self.week_frame.columnconfigure(i, weight=1)
            day = today - timedelta(days=today.weekday()) + timedelta(days=i)
            due = [t for t in tasks if t.due == day.isoformat() and not t.done]
            box = card(self.week_frame, padding=8)
            box.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            ttk.Label(box, text=f"{entry.name} {entry.day}", style="Card.TLabel",
                      font=(theme.family, 10, "bold" if day == today else "normal")).pack()
            if due:
                chip = badge(box, theme, f"{len(due)} due", "bad" if any(t.priority == 1 for t in due) else "warn")
            else:
                chip = badge(box, theme, "\u2713", "ok")
            chip.pack(pady=(4, 0))
            text = "\n".join(f"- {t.title} ({PRIORITY_NAMES[t.priority]})" for t in due) or f"Nothing due on {day:%A}"
            for widget in (box, chip):
                Tooltip(widget, text)
        # charts
        counts = {"Done": 0, "Pending": 0, "Today": 0, "Overdue": 0}
        for t in tasks:
            counts[t.status()] += 1
        self.charts[0].set(list(counts.items()), center=str(len(tasks)), sub="tasks")
        pending = [t for t in tasks if not t.done]
        labels, series = ["Late"], {1: [0], 2: [0], 3: [0]}
        for t in pending:
            if t.days_left() < 0:
                series[t.priority][0] += 1
        for d in range(14):
            labels.append(f"{(today + timedelta(days=d)):%d}")
            for p in series:
                series[p].append(sum(1 for t in pending if t.days_left() == d and t.priority == p))
        self.charts[1].set(labels, [(PRIORITY_NAMES[p], series[p]) for p in (1, 2, 3)], stacked=True, fmt="{:g} task(s)")
        by_cat = {}
        for t in pending:
            by_cat[t.category] = by_cat.get(t.category, 0) + 1
        self.charts[2].set(sorted(by_cat.items(), key=lambda p: -p[1]), fmt="{:g}")
        theme.recolor(self)
