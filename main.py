"""
Student Hub - launcher.

Run this file:   python main.py

Login / registration, then a sidebar app with a top bar (date, sun/moon theme toggle) and these pages:
Home dashboard | Tasks | Exam Scheduler | Study Tracker | Notes Lab | Expense Tracker | Toolbox | Book Finder | Profile
Every page is built the first time you open it, so startup stays fast and a missing library (for example pandas)
only affects the page that needs it.
"""
import importlib
import os
import tkinter as tk
from datetime import date, datetime
from tkinter import ttk

from hub_auth import AuthDB, AuthError, COURSES, user_dir
from hub_charts import BarChart, DonutChart, HBarChart
from hub_theme import Theme, ThemeToggle, Toast, add_field, badge, card, titled_card

# (key, sidebar label, icon, module, class, description shown on the Home page)
PAGES = [
    ("tasks", "Tasks", "\u2705", "task_manager", "TaskPage",
     "Quick-add deadlines from plain text, week view with hover details, workload charts."),
    ("exams", "Exam Scheduler", "\U0001F5D3", "exam_scheduler", "ExamPage",
     "Clash detection, a calendar, and a smart day-by-day study plan built from your syllabus progress."),
    ("study", "Study Tracker", "\u23F1", "study_tracker", "StudyPage",
     "Log sessions with a live timer, track goals and streaks, plan your time budget."),
    ("notes", "Notes Lab", "\U0001F4DD", "notes_lab", "NotesPage",
     "Tagged notes, text tools, a NumPy lab and a Pandas CSV explorer."),
    ("expenses", "Expense Tracker", "\U0001F4B8", "expense_tracker", "ExpensePage",
     "Type 'Lunch 250 upi' to log it. Budgets, forecasts, analytics and a split-bill settler."),
    ("toolbox", "Toolbox", "\U0001F9F0", "toolbox", "ToolboxPage",
     "Drop-down workbench: prime explorer, matrix lab, statistics, regression, loan EMI, SIP planner and more."),
    ("books", "Book Finder", "\U0001F4DA", "book_finder", "BookPage",
     "Search the web for the best books on a topic and keep a reading library."),
]
NAV = [("home", "Home", "\U0001F3E0")] + [(k, label, icon) for k, label, icon, *_ in PAGES] + [("profile", "Profile", "\U0001F464")]
TITLES = {key: f"{icon}  {label}" for key, label, icon in NAV}


class Context:
    """What every page receives as `ctx`: theme, toast(), and a per-user file path."""

    def __init__(self, theme, toast, username):
        self.theme = theme
        self._toast = toast
        self.username = username

    def toast(self, message, kind="info"):
        self._toast.show(message, kind)

    def path(self, filename):
        return os.path.join(user_dir(self.username), filename)


# ============================================================ login / register
class AuthScreen(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        hero = ttk.Frame(self, style="Sidebar.TFrame", width=360)
        hero.grid(row=0, column=0, sticky="ns")
        hero.grid_propagate(False)
        fam = app.theme.family
        ttk.Label(hero, text="\U0001F393", style="SidebarTitle.TLabel", font=(fam, 40)).pack(anchor="w", padx=34, pady=(90, 0))
        ttk.Label(hero, text="Student Hub", style="SidebarTitle.TLabel", font=(fam, 26, "bold")).pack(anchor="w", padx=34)
        ttk.Label(hero, text="Plan. Study. Spend wisely.", style="Sidebar.TLabel", font=(fam, 11)).pack(anchor="w", padx=34, pady=(2, 26))
        for icon, text in (("\u2705", "Tasks and deadlines"), ("\U0001F5D3", "Exam scheduler and study plans"), ("\u23F1", "Study tracker with live timer"),
                           ("\U0001F4B8", "Expense tracker and budgets"), ("\U0001F4CA", "Charts everywhere")):
            ttk.Label(hero, text=f"{icon}   {text}", style="Sidebar.TLabel", font=(fam, 11)).pack(anchor="w", padx=34, pady=5)
        stage = ttk.Frame(self)
        stage.grid(row=0, column=1, sticky="nsew")
        box = card(stage, padding=26)
        box.place(relx=0.5, rely=0.5, anchor="center")
        self.title = ttk.Label(box, text="Welcome back", style="CardTitle.TLabel", font=(fam, 20, "bold"))
        self.title.grid(row=0, column=0, pady=(0, 2))
        self.subtitle = ttk.Label(box, text="Sign in to continue", style="CardMuted.TLabel")
        self.subtitle.grid(row=1, column=0, pady=(0, 14))
        self.login_form = self.build_login(box)
        self.register_form = self.build_register(box)
        self.login_form.grid(row=2, column=0)
        self.error = ttk.Label(box, text="", style="CardError.TLabel", wraplength=360, justify="left")
        self.error.grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.switch = ttk.Button(box, text="Create an account", command=self.toggle)
        self.switch.grid(row=4, column=0, pady=(10, 0))
        self.toggle_button = ThemeToggle(stage, app.theme, app.toggle_theme)
        self.toggle_button.bg_key = "bg"
        self.toggle_button.place(relx=1.0, x=-18, y=18, anchor="ne")
        self.mode = "login"
        self.u_login.focus_set()

    # ---------- login ----------
    def build_login(self, parent):
        f = ttk.Frame(parent, style="Card.TFrame")
        f.columnconfigure(1, weight=1)
        self.u_login = add_field(f, 0, "Username", ttk.Entry(f, width=30))
        self.p_login = add_field(f, 1, "Password", ttk.Entry(f, width=30, show="*"))
        ttk.Button(f, text="Log in", style="Accent.TButton", command=self.do_login
                   ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        for entry in (self.u_login, self.p_login):
            entry.bind("<Return>", lambda event: self.do_login())
        return f

    def do_login(self):
        try:
            student = self.app.auth.login(self.u_login.get(), self.p_login.get())
        except AuthError as err:
            return self.error.configure(text=str(err))
        self.app.start_session(student)

    # ---------- register ----------
    def build_register(self, parent):
        f = ttk.Frame(parent, style="Card.TFrame")
        f.columnconfigure(1, weight=1)
        self.reg = {}
        rows = [("username", "Username", False), ("password", "Password", True), ("confirm", "Confirm password", True),
                ("full_name", "Full name", False), ("age", "Age", False), ("email", "Email", False),
                ("phone", "Mobile (10 digits)", False)]
        for i, (key, label, secret) in enumerate(rows):
            self.reg[key] = add_field(f, i, label, ttk.Entry(f, width=30, show="*" if secret else ""))
        n = len(rows)
        self.reg["course"] = add_field(f, n, "Course", ttk.Combobox(f, values=COURSES, state="readonly", width=28))
        self.level = tk.StringVar(value="UG")
        picker = ttk.Combobox(f, values=["Undergraduate", "Postgraduate"], state="readonly", width=28)
        picker.set("Undergraduate")
        picker.bind("<<ComboboxSelected>>", lambda event: self.pick_level(picker.get()))
        add_field(f, n + 1, "Level", picker)
        self.sem_label = ttk.Label(f, text="Semester", style="CardMuted.TLabel")
        self.reg["semester"] = ttk.Combobox(f, values=[str(i) for i in range(1, 9)], state="readonly", width=6)
        self.reg["semester"].set("1")
        self.thesis_label = ttk.Label(f, text="Thesis topic", style="CardMuted.TLabel")
        self.reg["thesis_topic"] = ttk.Entry(f, width=30)
        self.extra_row = n + 2
        self.level_changed()
        ttk.Button(f, text="Register", style="Accent.TButton", command=self.do_register
                   ).grid(row=n + 3, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        return f

    def pick_level(self, text):
        self.level.set("UG" if text == "Undergraduate" else "PG")
        self.level_changed()

    def level_changed(self):
        for w in (self.sem_label, self.reg["semester"], self.thesis_label, self.reg["thesis_topic"]):
            w.grid_remove()
        label, widget = ((self.sem_label, self.reg["semester"]) if self.level.get() == "UG"
                         else (self.thesis_label, self.reg["thesis_topic"]))
        label.grid(row=self.extra_row, column=0, sticky="w", padx=(0, 10), pady=4)
        widget.grid(row=self.extra_row, column=1, sticky="ew", pady=4)

    def do_register(self):
        form = {k: self.reg[k].get() for k in ("full_name", "age", "email", "phone", "course", "semester",
                                                "thesis_topic")}
        form["level"] = self.level.get()
        try:
            student = self.app.auth.register(self.reg["username"].get(), self.reg["password"].get(),
                                             self.reg["confirm"].get(), form)
        except AuthError as err:
            return self.error.configure(text=str(err))
        self.app.start_session(student)

    def toggle(self):
        self.error.configure(text="")
        if self.mode == "login":
            self.login_form.grid_remove()
            self.register_form.grid(row=2, column=0)
            self.title.configure(text="Create your account")
            self.subtitle.configure(text="It takes a minute")
            self.switch.configure(text="Back to login")
            self.mode = "register"
        else:
            self.register_form.grid_remove()
            self.login_form.grid(row=2, column=0)
            self.title.configure(text="Welcome back")
            self.subtitle.configure(text="Sign in to continue")
            self.switch.configure(text="Create an account")
            self.mode = "login"


# ============================================================ home dashboard
class HomePage(ttk.Frame):
    """Live summary across every tool, with charts. Built from the same databases the pages use."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.columnconfigure((0, 1, 2), weight=1, uniform="home")
        self.build()
        self.refresh()

    def on_show(self):
        self.refresh()

    def build(self):
        theme = self.app.theme
        self.hero = ttk.Frame(self, style="Hero.TFrame", padding=(26, 20))
        self.hero.grid(row=0, column=0, columnspan=3, sticky="ew", padx=16, pady=(0, 14))
        self.hero.columnconfigure((0, 1, 2), weight=1, uniform="hero")
        ttk.Label(self.hero, text="YOUR STUDENT PULSE", style="HeroEyebrow.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        self.pulse = []
        for i in range(3):
            eyebrow = ttk.Label(self.hero, text="", style="HeroMuted.TLabel")
            value = ttk.Label(self.hero, text="-", style="HeroValue.TLabel")
            eyebrow.grid(row=1, column=i, sticky="w")
            value.grid(row=2, column=i, sticky="w")
            self.pulse.append((eyebrow, value))
        specs = [("STUDY", "Hours studied, last 7 days", BarChart, 0), ("MONEY", "Spending this month", DonutChart, 1),
                 ("EXAMS", "Days until each exam", HBarChart, 2)]
        self.charts = []
        for eyebrow, title, cls, col in specs:
            box = titled_card(self, eyebrow, title, grid=dict(row=1, column=col, sticky="nsew", padx=(16 if col == 0 else 0, 16 if col == 2 else 8), pady=(0, 14)))
            box.columnconfigure(0, weight=1)
            chart = cls(box, theme, height=200)
            chart.grid(row=2, column=0, columnspan=3, sticky="nsew")
            self.charts.append(chart)
        self.tiles = ttk.Frame(self)
        self.tiles.grid(row=2, column=0, columnspan=3, sticky="ew", padx=16)
        self.tiles.columnconfigure((0, 1, 2, 3), weight=1, uniform="tile")
        for i, (key, label, icon, _mod, _cls, text) in enumerate(PAGES):
            tile = card(self.tiles, padding=14)
            tile.grid(row=i // 4, column=i % 4, sticky="nsew", padx=(0 if i % 4 == 0 else 8, 0), pady=(0, 8))
            ttk.Label(tile, text=icon, style="Card.TLabel", font=(theme.family, 22)).pack(anchor="w")
            ttk.Label(tile, text=label, style="CardTitle.TLabel").pack(anchor="w", pady=(2, 0))
            ttk.Label(tile, text=text, style="CardMuted.TLabel", wraplength=190, justify="left").pack(anchor="w", pady=(2, 8))
            ttk.Button(tile, text="Open  \u2192", style="CardLink.TButton", command=lambda k=key: self.app.show(k)).pack(anchor="w")

    def refresh(self):
        c = self.app.theme.colors
        ctx = self.app.ctx
        today = date.today()
        streak, data = 0, {"today": 0.0}
        try:                                                                     # study
            import study_tracker
            data = study_tracker.summary(ctx.path("study.db"))
            labels, values, goal, streak = data["labels"], data["values"], data["goal"], data["streak"]
        except Exception:
            labels, values, goal = [], [], 4
        self.charts[0].set(labels, [("Hours", [round(v, 2) for v in values])], fmt="{:.1f} h", goal=goal, goal_label="daily goal")
        spent, total = {}, 0.0
        try:                                                                     # money
            import expense_tracker
            db = expense_tracker.ExpenseDB(ctx.path("expenses.db"))
            summary = expense_tracker.month_summary(db.rows(), today.year, today.month)
            spent, total = summary["cats"], summary["expense"]
        except Exception:
            pass
        self.charts[1].set(list(spent.items()), center=f"Rs {total:,.0f}", sub="this month", fmt="Rs {:,.0f}")
        nxt, upcoming = None, []
        try:                                                                     # exams
            import exam_scheduler
            upcoming = [e for e in exam_scheduler.Database(ctx.path("exam_scheduler.db")).exams() if e.days_left(today) >= 0]
            nxt = upcoming[0] if upcoming else None
        except Exception:
            pass
        self.charts[2].set([(e.title(), e.days_left(today), c["danger"] if e.days_left(today) <= 3 else c["warning"] if e.days_left(today) <= 7 else c["primary"],
                             f"{e.title()} on {e.date:%d %b} at {e.start}") for e in upcoming[:6]], fmt="{:.0f} d")
        try:                                                                     # tasks
            import task_manager
            counts = task_manager.TaskDB(ctx.path("tasks.db")).summary()
        except Exception:
            counts = {"Overdue": 0, "Today": 0, "Pending": 0}
        if nxt is None:
            exam_text = "No exam scheduled"
        else:
            left = nxt.days_left(today)
            exam_text = f"{nxt.title()} today" if left == 0 else f"{nxt.title()} in {left} day{'s' if left != 1 else ''}"
        pulse = [("\u23F3  Next exam", exam_text),
                 ("\u2705  Tasks needing attention", f"{counts['Overdue']} overdue, {counts['Today']} due today"),
                 ("\U0001F525  Study streak", f"{streak} day{'s' if streak != 1 else ''}  |  {data['today']:.1f} h today")]
        for (eyebrow, value), (title, text) in zip(self.pulse, pulse):
            eyebrow.config(text=title)
            value.config(text=text)
        self.app.theme.recolor(self)


# ============================================================ profile
class ProfilePage(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.columnconfigure((0, 1), weight=1, uniform="cols")
        s = app.student
        prof = titled_card(self, "ACCOUNT", "Your profile", grid=dict(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(0, 16)))
        prof.columnconfigure(1, weight=1)
        ttk.Label(prof, text=s.display_info(), style="CardMuted.TLabel", wraplength=360, justify="left").grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.f = {}
        values = {"full_name": s.name, "age": s.age, "email": s.email, "phone": s.phone}
        labels = {"full_name": "Full name", "age": "Age", "email": "Email", "phone": "Mobile"}
        for i, key in enumerate(values, start=3):
            entry = add_field(prof, i, labels[key], ttk.Entry(prof, width=28))
            entry.insert(0, str(values[key]))
            self.f[key] = entry
        self.f["course"] = add_field(prof, 7, "Course", ttk.Combobox(prof, values=COURSES, state="readonly", width=26))
        self.f["course"].set(s.course)
        self.level = "UG" if s.level == "Undergraduate" else "PG"
        if self.level == "UG":
            self.extra = add_field(prof, 8, "Semester", ttk.Combobox(prof, values=[str(i) for i in range(1, 9)], state="readonly", width=26))
            self.extra.set(str(getattr(s, "semester", 1) or 1))
        else:
            self.extra = add_field(prof, 8, "Thesis topic", ttk.Entry(prof, width=28))
            self.extra.insert(0, str(getattr(s, "thesis_topic", "")))
        ttk.Button(prof, text="Save profile", style="Accent.TButton", command=self.save_profile
                   ).grid(row=9, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        pw = titled_card(self, "SECURITY", "Change password", grid=dict(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(0, 16)))
        pw.columnconfigure(1, weight=1)
        self.old = add_field(pw, 2, "Current", ttk.Entry(pw, width=28, show="*"))
        self.new = add_field(pw, 3, "New", ttk.Entry(pw, width=28, show="*"))
        self.confirm = add_field(pw, 4, "Confirm", ttk.Entry(pw, width=28, show="*"))
        ttk.Button(pw, text="Update password", style="Accent.TButton", command=self.change_password
                   ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def save_profile(self):
        form = {k: w.get() for k, w in self.f.items()}
        form["level"] = self.level
        form["semester"] = self.extra.get() if self.level == "UG" else ""
        form["thesis_topic"] = self.extra.get() if self.level == "PG" else ""
        try:
            self.app.student = self.app.auth.update_profile(self.app.student.username, form)
        except AuthError as err:
            return self.app.ctx.toast(str(err), "error")
        self.app.user_label.configure(text=self.app.student.name)
        self.app.ctx.toast("Profile saved", "success")

    def change_password(self):
        try:
            self.app.auth.change_password(self.app.student.username, self.old.get(), self.new.get(),
                                          self.confirm.get())
        except AuthError as err:
            return self.app.ctx.toast(str(err), "error")
        for entry in (self.old, self.new, self.confirm):
            entry.delete(0, "end")
        self.app.ctx.toast("Password changed", "success")


# ============================================================ application shell
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Student Hub")
        self.root.geometry("1280x820")
        self.root.minsize(1060, 700)
        self.theme = Theme()
        self.theme.apply(self.root)
        self.toast = Toast(self.root, self.theme)
        self.auth = AuthDB()
        self.student = self.ctx = self.shell = None
        self.pages, self.nav = {}, {}
        self.current = None
        self.clock_job = None
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.show_auth()

    # ---------- screens ----------
    def show_auth(self):
        self.stop_clock()
        if self.shell is not None:
            self.shell.destroy()
        self.pages, self.nav, self.current = {}, {}, None
        self.shell = AuthScreen(self.root, self)
        self.shell.pack(fill="both", expand=True)
        self.theme.recolor(self.root)

    def start_session(self, student):
        self.student = student
        self.ctx = Context(self.theme, self.toast, student.username)
        self.shell.destroy()
        self.build_shell()
        self.show("home")
        self.tick()

    def build_shell(self):
        self.shell = ttk.Frame(self.root)
        self.shell.pack(fill="both", expand=True)
        self.shell.columnconfigure(1, weight=1)
        self.shell.rowconfigure(0, weight=1)

        side = ttk.Frame(self.shell, style="Sidebar.TFrame", width=232)
        side.grid(row=0, column=0, sticky="ns")
        side.grid_propagate(False)
        ttk.Label(side, text="\U0001F393  Student Hub", style="SidebarTitle.TLabel").pack(anchor="w", padx=18, pady=(22, 2))
        ttk.Label(side, text="Plan. Study. Spend wisely.", style="Sidebar.TLabel").pack(anchor="w", padx=20, pady=(0, 16))
        for key, label, icon in NAV:
            button = ttk.Button(side, text=f"  {icon}   {label}", style="Nav.TButton", command=lambda k=key: self.show(k))
            button.pack(fill="x", pady=1)
            self.nav[key] = button
        footer = ttk.Frame(side, style="Sidebar.TFrame")
        footer.pack(side="bottom", fill="x", padx=14, pady=14)
        self.user_label = ttk.Label(footer, text=self.student.name, style="Sidebar.TLabel")
        self.user_label.pack(anchor="w", pady=(0, 8))
        ttk.Button(footer, text="\u21AA  Log out", command=self.logout).pack(fill="x")

        main = ttk.Frame(self.shell)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        top = ttk.Frame(main, style="Topbar.TFrame", padding=(22, 12))
        top.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        top.columnconfigure(0, weight=1)
        titles = ttk.Frame(top, style="Topbar.TFrame")
        titles.grid(row=0, column=0, sticky="w")
        self.title = ttk.Label(titles, text="", style="TopbarTitle.TLabel")
        self.title.pack(anchor="w")
        self.subtitle = ttk.Label(titles, text="", style="TopbarMuted.TLabel")
        self.subtitle.pack(anchor="w")
        self.clock = badge(top, self.theme, "", "ok")
        self.clock.grid(row=0, column=1, padx=(0, 12))
        self.toggle_button = ThemeToggle(top, self.theme, self.toggle_theme)
        self.toggle_button.grid(row=0, column=2)
        self.container = ttk.Frame(main)
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)

    # ---------- clock + theme ----------
    def tick(self):
        if self.student is None:
            return
        self.clock.configure(text=f"\u25CF  {datetime.now():%d %b %Y, %I:%M %p}")
        self.clock_job = self.root.after(30_000, self.tick)

    def stop_clock(self):
        if self.clock_job is not None:
            self.root.after_cancel(self.clock_job)
            self.clock_job = None

    def toggle_theme(self):
        self.theme.toggle(self.root)
        self.theme.recolor(self.root)

    # ---------- navigation ----------
    def make_page(self, key):
        if key == "home":
            return HomePage(self.container, self)
        if key == "profile":
            return ProfilePage(self.container, self)
        _key, _label, _icon, module, cls, _text = next(p for p in PAGES if p[0] == key)
        try:
            return getattr(importlib.import_module(module), cls)(self.container, self.ctx)
        except ImportError as err:
            page = ttk.Frame(self.container)
            ttk.Label(page, text=f"This page needs a library that is not installed:\n{err}\n\n"
                                 "Run:  pip install pandas numpy matplotlib", justify="left"
                      ).pack(anchor="w", padx=16, pady=16)
            return page

    def show(self, key):
        first = key not in self.pages
        if first:
            page = self.make_page(key)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = page
            self.theme.recolor(page)
        page = self.pages[key]
        page.tkraise()
        if not first and hasattr(page, "on_show"):
            page.on_show()
        self.current = key
        for name, button in self.nav.items():
            button.configure(style="NavActive.TButton" if name == key else "Nav.TButton")
        if key == "home":
            hour = datetime.now().hour
            greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
            self.title.configure(text=f"{greet}, {self.student.name.split()[0]}! \U0001F44B")
            self.subtitle.configure(text="Here is what is happening across your studies and money today.")
        else:
            self.title.configure(text=TITLES[key])
            self.subtitle.configure(text=next((p[5] for p in PAGES if p[0] == key), "Update your details and password."))

    def logout(self):
        self.student = self.ctx = None
        self.show_auth()

    def quit(self):
        self.stop_clock()
        try:
            self.auth.con.close()
        finally:
            self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
