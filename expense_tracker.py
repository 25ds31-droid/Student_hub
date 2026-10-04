"""
Expense Tracker & Budget Coach
------------------------------
* Quick-add from plain text:  "Lunch with friends 450 upi yesterday"  (regular expressions + keyword rules)
* Ledger with filters, monthly analytics, budgets per category and a savings goal
* Month-end forecast (exponentially weighted run-rate), unusual-spend detection (mean + 2 standard deviations)
* Split-bill settlement that needs the fewest possible payments (two heaps: who is owed, who owes)
* Charts: category donut, daily spend with budget line, cumulative spend vs budget pace, income vs expense trend,
  payment-method bars, budget usage bars
"""
import calendar
import csv
import heapq
import random
import re
import sqlite3
import statistics
from datetime import date, datetime, timedelta

import tkinter as tk
from tkinter import ttk, filedialog

from hub_charts import BarChart, DonutChart, HBarChart, LineChart
from hub_theme import (MONTHS, DatePicker, add_field, badge, card, clear_table, info_icon, insert_row, make_table,
                       titled_card)

ICONS = {"Food": "\U0001F354", "Transport": "\U0001F68C", "Rent": "\U0001F3E0", "Education": "\U0001F4DA",
         "Shopping": "\U0001F6CD", "Entertainment": "\U0001F3AC", "Health": "\U0001F48A", "Bills": "\U0001F4A1",
         "Travel": "\u2708", "Other": "\U0001F4E6", "Pocket money": "\U0001F4B5", "Salary": "\U0001F4BC",
         "Scholarship": "\U0001F393", "Freelance": "\U0001F4BB", "Gift": "\U0001F381", "Other income": "\U0001F4B0"}
EXPENSE_CATS = ["Food", "Transport", "Rent", "Education", "Shopping", "Entertainment", "Health", "Bills", "Travel", "Other"]
INCOME_CATS = ["Pocket money", "Salary", "Scholarship", "Freelance", "Gift", "Other income"]
METHODS = ["UPI", "Cash", "Card", "Net banking", "Wallet"]
FIXED = {"Rent", "Bills", "Education", "Travel"}      # lumpy costs: not projected forward, ignored by the unusual-spend detector
KEYWORDS = {"Food": "lunch dinner breakfast snack coffee tea pizza biryani cafe canteen groceries swiggy zomato",
            "Transport": "uber ola bus metro auto petrol fuel train cab rickshaw",
            "Entertainment": "movie netflix game concert spotify party",
            "Education": "book books course fees fee stationery exam xerox",
            "Shopping": "shirt shoes amazon flipkart clothes jeans",
            "Health": "medicine doctor pharmacy clinic gym",
            "Bills": "recharge wifi electricity bill internet",
            "Rent": "rent hostel", "Travel": "trip flight hotel ticket"}
INCOME_WORDS = {"income", "salary", "received", "stipend", "scholarship", "allowance", "pocket", "freelance", "refund"}
METHOD_WORDS = {"upi": "UPI", "gpay": "UPI", "phonepe": "UPI", "paytm": "Wallet", "cash": "Cash", "card": "Card",
                "debit": "Card", "credit": "Card", "netbanking": "Net banking", "wallet": "Wallet"}

AMOUNT_RE = re.compile(r"(?<![\w.#])(\d+(?:\.\d+)?)(k?)(?![\w.])", re.I)
DATE_RE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})\b")
AGO_RE = re.compile(r"\b(\d{1,3}) days? ago\b", re.I)
TAG_RE = re.compile(r"#(\w+)")


class ExpenseError(Exception):
    pass


class InvalidExpenseError(ExpenseError):
    pass


def money(value):
    return f"Rs {value:,.0f}"


def strip_icon(text):
    return re.sub(r"^[^A-Za-z]+", "", text).strip()


def choices(categories):
    return [f"{ICONS[c]} {c}" for c in categories]


# ======================= pure logic =======================
def guess_category(words, income):
    cats = INCOME_CATS if income else EXPENSE_CATS
    for cat in cats:
        if cat.lower() in words or cat.lower().split()[0] in words:
            return cat
    if income:
        return "Pocket money" if words & {"pocket", "allowance"} else "Scholarship" if "scholarship" in words else \
            "Freelance" if "freelance" in words else "Salary" if words & {"salary", "stipend"} else "Other income"
    for cat, bag in KEYWORDS.items():
        if words & set(bag.split()):
            return cat
    return "Other"


def parse_quick(text, today=None):
    """'Lunch 250 #food upi yesterday' -> dict(date, amount, category, method, note, kind)"""
    today = today or date.today()
    work = text.strip()
    if not work:
        raise InvalidExpenseError("Type something like:  Lunch 250 upi")
    day = today
    m = DATE_RE.search(work)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            day = date(y + 2000 if y < 100 else y, mo, d)
        except ValueError:
            raise InvalidExpenseError("That date does not exist") from None
        work = work.replace(m.group(0), " ", 1)
    elif AGO_RE.search(work):
        m = AGO_RE.search(work)
        day = today - timedelta(days=int(m.group(1)))
        work = work.replace(m.group(0), " ", 1)
    elif re.search(r"\byesterday\b", work, re.I):
        day = today - timedelta(days=1)
        work = re.sub(r"\byesterday\b", " ", work, flags=re.I)
    work = re.sub(r"\btoday\b", " ", work, flags=re.I)
    m = AMOUNT_RE.search(work)
    if not m:
        raise InvalidExpenseError("No amount found - include a number such as 250")
    amount = float(m.group(1)) * (1000 if m.group(2) else 1)
    work = work.replace(m.group(0), " ", 1)
    income = work.lstrip().startswith("+")
    work = work.replace("+", " ")
    tag = TAG_RE.search(work)
    wanted = tag.group(1).lower() if tag else ""
    work = TAG_RE.sub(" ", work)
    words = {w.lower() for w in re.findall(r"[A-Za-z]+", work)}
    income = income or bool(words & INCOME_WORDS)
    method = next((METHOD_WORDS[w] for w in re.findall(r"[a-z]+", work.lower()) if w in METHOD_WORDS), "UPI")
    for w in list(METHOD_WORDS):
        work = re.sub(rf"\b{w}\b", " ", work, flags=re.I)
    cats = INCOME_CATS if income else EXPENSE_CATS
    category = next((c for c in cats if c.lower().startswith(wanted)), None) if wanted else None
    category = category or guess_category(words | {wanted}, income)
    note = " ".join(work.split()) or category
    return {"date": day.isoformat(), "amount": amount, "category": category, "method": method,
            "note": note[:80], "kind": "Income" if income else "Expense"}


def month_summary(rows, year, month):
    """rows: (id,date,amount,category,method,note,kind) -> dict of totals for one month."""
    out = {"income": 0.0, "expense": 0.0, "cats": {}, "methods": {}, "days": {}, "income_cats": {}}
    for _id, d, amount, cat, method, _note, kind in rows:
        day = date.fromisoformat(d)
        if (day.year, day.month) != (year, month):
            continue
        if kind == "Income":
            out["income"] += amount
            out["income_cats"][cat] = out["income_cats"].get(cat, 0) + amount
        else:
            out["expense"] += amount
            out["cats"][cat] = out["cats"].get(cat, 0) + amount
            out["methods"][method] = out["methods"].get(method, 0) + amount
            out["days"].setdefault(day.day, {})
            out["days"][day.day][cat] = out["days"][day.day].get(cat, 0) + amount
    return out


def forecast(day_cats, year, month, today=None, alpha=0.3):
    """Month-end projection. One-off fixed costs (rent, bills, fees) are kept as paid; only everyday spending
    is projected forward, using an exponentially weighted average of recent daily spend."""
    today = today or date.today()
    dim = calendar.monthrange(year, month)[1]
    fixed = sum(v for cats in day_cats.values() for c, v in cats.items() if c in FIXED)
    variable = {d: sum(v for c, v in cats.items() if c not in FIXED) for d, cats in day_cats.items()}
    if (today.year, today.month) != (year, month):
        total = fixed + sum(variable.values())
        return {"so_far": total, "projected": total, "daily_avg": total / dim, "days_left": 0}
    var_so_far = sum(v for d, v in variable.items() if d <= today.day)
    so_far = fixed + var_so_far
    ewma = var_so_far / max(today.day, 1)
    for d in range(1, today.day + 1):
        ewma = alpha * variable.get(d, 0.0) + (1 - alpha) * ewma
    left = dim - today.day
    return {"so_far": so_far, "projected": so_far + ewma * left, "daily_avg": so_far / max(today.day, 1), "days_left": left}


def unusual_days(day_cat_totals, sigmas=2.0):
    """Days whose variable spending is more than `sigmas` standard deviations above the monthly norm."""
    variable = {d: sum(v for c, v in cats.items() if c not in FIXED) for d, cats in day_cat_totals.items()}
    values = [v for v in variable.values() if v > 0]
    if len(values) < 7:
        return []
    mean, sd = statistics.mean(values), statistics.pstdev(values)
    return sorted(((d, v) for d, v in variable.items() if sd and v > mean + sigmas * sd), key=lambda p: -p[1])


def settle_up(paid):
    """Equal split. Returns (share, balances, transfers) with the fewest payments (greedy over two heaps)."""
    if len(paid) < 2:
        raise InvalidExpenseError("Add at least two people")
    total = sum(paid.values())
    share = total / len(paid)
    balances = {name: round(amount - share, 2) for name, amount in paid.items()}
    owed = [(-b, n) for n, b in balances.items() if b > 0.004]          # max-heap by negating
    owes = [(b, n) for n, b in balances.items() if b < -0.004]
    heapq.heapify(owed)
    heapq.heapify(owes)
    transfers = []
    while owed and owes:
        credit, creditor = heapq.heappop(owed)
        debt, debtor = heapq.heappop(owes)
        pay = min(-credit, -debt)
        transfers.append((debtor, creditor, round(pay, 2)))
        if -credit - pay > 0.004:
            heapq.heappush(owed, (credit + pay, creditor))
        if -debt - pay > 0.004:
            heapq.heappush(owes, (debt + pay, debtor))
    return share, balances, transfers


def parse_payers(text):
    paid = {}
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        m = re.fullmatch(r"\s*([A-Za-z][A-Za-z .'-]*?)\s*(?:paid|:|-|=)?\s*(\d+(?:\.\d+)?)\s*", line)
        if not m:
            raise InvalidExpenseError(f"Cannot read '{line.strip()}'. Use  Name paid 1200")
        name = m.group(1).strip().title()
        paid[name] = paid.get(name, 0.0) + float(m.group(2))
    return paid


def goal_eta(goal, saved, monthly_net):
    if saved >= goal:
        return "Goal reached!"
    if monthly_net <= 0:
        return "Savings are not growing yet - cut spending or add income"
    months = (goal - saved) / monthly_net
    return f"About {months:.1f} months at your recent saving rate ({money(monthly_net)} / month)"


def month_key(day):
    return f"{day.year:04d}-{day.month:02d}"


def label_month(key):
    y, m = key.split("-")
    return f"{MONTHS[int(m) - 1]} {y}"


def parse_month(label):
    mon, year = label.split()
    return int(year), MONTHS.index(mon) + 1


# ======================= database =======================
class ExpenseDB:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS entries(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL,
                amount REAL NOT NULL, category TEXT NOT NULL, method TEXT NOT NULL, note TEXT, kind TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS budgets(category TEXT PRIMARY KEY, monthly REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        """)
        self.con.commit()

    def add(self, day, amount, category, method, note, kind):
        try:
            date.fromisoformat(day)
            amount = float(amount)
        except (TypeError, ValueError):
            raise InvalidExpenseError("Enter a valid date and a numeric amount") from None
        if not 0 < amount <= 10_000_000:
            raise InvalidExpenseError("Amount must be above 0 and at most 1 crore")
        if kind not in ("Expense", "Income") or not category or not method:
            raise InvalidExpenseError("Choose the type, category and payment method")
        self.con.execute("INSERT INTO entries(date,amount,category,method,note,kind) VALUES (?,?,?,?,?,?)",
                         (day, amount, category, method, (note or "").strip()[:80], kind))
        self.con.commit()

    def delete(self, entry_id):
        self.con.execute("DELETE FROM entries WHERE id=?", (entry_id,))
        self.con.commit()

    def rows(self):
        return self.con.execute("SELECT id,date,amount,category,method,note,kind FROM entries ORDER BY date DESC, id DESC").fetchall()

    def months(self):
        found = {r[1][:7] for r in self.rows()} | {month_key(date.today())}
        return sorted(found, reverse=True)

    def budgets(self):
        return dict(self.con.execute("SELECT category, monthly FROM budgets").fetchall())

    def set_budget(self, category, amount):
        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise InvalidExpenseError("Budget must be a number") from None
        if amount < 0:
            raise InvalidExpenseError("Budget cannot be negative")
        if amount == 0:
            self.con.execute("DELETE FROM budgets WHERE category=?", (category,))
        else:
            self.con.execute("INSERT OR REPLACE INTO budgets VALUES (?,?)", (category, amount))
        self.con.commit()

    def setting(self, key, default=""):
        row = self.con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.con.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))
        self.con.commit()

    def load_demo(self):
        rng, today, batch = random.Random(7), date.today(), []
        notes = {"Food": ["Canteen lunch", "Dinner with friends", "Coffee", "Snacks", "Biryani", "Groceries"],
                 "Transport": ["Metro", "Auto", "Bus pass top-up", "Cab"], "Entertainment": ["Movie night", "Games", "Concert"],
                 "Shopping": ["Clothes", "Headphones", "Online order"], "Health": ["Pharmacy", "Doctor visit"]}
        day = today - timedelta(days=89)
        while day <= today:
            iso = day.isoformat()

            def put(amount, cat, note, kind="Expense", method=None):
                batch.append((iso, float(amount), cat, method or rng.choice(METHODS[:3]), note, kind))
            if day.day == 1:
                put(12000, "Pocket money", "Monthly allowance", "Income", "Net banking")
            if day.day == 3:
                put(6500, "Rent", "Hostel rent", method="Net banking")
            if day.day == 5:
                put(899, "Bills", "Wi-Fi and mobile recharge", method="UPI")
            if day.day == 10:
                put(1200, "Education", "Books and stationery")
            if day.day == 15 and rng.random() < 0.7:
                put(rng.randint(1500, 4500), "Freelance", "Small project", "Income", "UPI")
            for _ in range(rng.choice([1, 1, 2])):
                put(rng.randint(80, 380), "Food", rng.choice(notes["Food"]))
            if rng.random() < 0.55:
                put(rng.choice([30, 45, 60, 120, 200]), "Transport", rng.choice(notes["Transport"]))
            if day.weekday() >= 5 and rng.random() < 0.6:
                put(rng.randint(150, 900), "Entertainment", rng.choice(notes["Entertainment"]))
            if rng.random() < 0.08:
                put(rng.randint(500, 2500), "Shopping", rng.choice(notes["Shopping"]))
            if rng.random() < 0.04:
                put(rng.randint(200, 900), "Health", rng.choice(notes["Health"]))
            if rng.random() < 0.02:
                put(4200, "Travel", "Weekend trip", method="Card")
            day += timedelta(days=1)
        self.con.executemany("INSERT INTO entries(date,amount,category,method,note,kind) VALUES (?,?,?,?,?,?)", batch)
        for cat, amount in {"Food": 4500, "Transport": 1500, "Rent": 6500, "Education": 1500, "Shopping": 2000,
                            "Entertainment": 1500, "Health": 1000, "Bills": 1200, "Travel": 3000}.items():
            self.con.execute("INSERT OR REPLACE INTO budgets VALUES (?,?)", (cat, amount))
        self.con.execute("INSERT OR REPLACE INTO settings VALUES ('goal', '25000')")
        self.con.commit()


# ======================= GUI =======================
class ExpensePage(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.db = ExpenseDB(ctx.path("expenses.db"))
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.build_ledger_tab()
        self.build_analytics_tab()
        self.build_budget_tab()
        self.build_split_tab()
        self.refresh_all()

    def on_show(self):
        self.refresh_all()

    def tab(self, title):
        frame = ttk.Frame(self.nb, padding=(0, 12))
        self.nb.add(frame, text=title)
        return frame

    # ---------- ledger ----------
    def build_ledger_tab(self):
        tab = self.tab("  \U0001F9FE Ledger  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        form = titled_card(tab, "NEW ENTRY", "Add money in or out", grid=dict(row=0, column=0, sticky="ns", padx=(0, 10)))
        form.columnconfigure(1, weight=1)
        self.v_quick = tk.StringVar()
        quick = ttk.Entry(form, textvariable=self.v_quick, width=30)
        quick.grid(row=2, column=0, columnspan=2, sticky="ew")
        quick.bind("<Return>", lambda event: self.quick_add())
        info_icon(form, "Examples:\n  Lunch with friends 450 upi\n  Uber 220 #transport yesterday\n  +12000 allowance\n  Netflix 649 card 12.09.2026\n"
                        "Amounts like 1.5k work too.").grid(row=2, column=2, padx=4)
        ttk.Button(form, text="Add from text", style="Accent.TButton", command=self.quick_add).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Separator(form).grid(row=4, column=0, columnspan=3, sticky="ew", pady=10)
        self.v_kind, self.v_cat, self.v_method = tk.StringVar(value="Expense"), tk.StringVar(), tk.StringVar(value="UPI")
        self.v_amount, self.v_note = tk.StringVar(), tk.StringVar()
        kind_box = add_field(form, 5, "Type", ttk.Combobox(form, textvariable=self.v_kind, values=["Expense", "Income"], state="readonly", width=22))
        kind_box.bind("<<ComboboxSelected>>", lambda event: self.kind_changed())
        self.entry_date = add_field(form, 6, "Date", DatePicker(form, years_ahead=1))
        add_field(form, 7, "Amount (Rs)", ttk.Entry(form, textvariable=self.v_amount, width=24))
        self.cat_box = add_field(form, 8, "Category", ttk.Combobox(form, textvariable=self.v_cat, state="readonly", width=22))
        add_field(form, 9, "Paid with", ttk.Combobox(form, textvariable=self.v_method, values=METHODS, state="readonly", width=22))
        add_field(form, 10, "Note", ttk.Entry(form, textvariable=self.v_note, width=24))
        ttk.Button(form, text="Add entry", command=self.add_entry).grid(row=11, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        ttk.Button(form, text="Load demo data", command=self.load_demo).grid(row=12, column=0, columnspan=3, sticky="ew", pady=2)
        self.kind_changed()

        right = titled_card(tab, "LEDGER", "All entries", grid=dict(row=0, column=1, sticky="nsew"))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        bar = ttk.Frame(right, style="Card.TFrame")
        bar.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.f_month, self.f_cat, self.f_kind = tk.StringVar(value="All months"), tk.StringVar(value="All categories"), tk.StringVar(value="All types")
        self.month_filter = ttk.Combobox(bar, textvariable=self.f_month, state="readonly", width=12)
        self.cat_filter = ttk.Combobox(bar, textvariable=self.f_cat, values=["All categories"] + choices(EXPENSE_CATS + INCOME_CATS), state="readonly", width=20)
        kind_filter = ttk.Combobox(bar, textvariable=self.f_kind, values=["All types", "Expense", "Income"], state="readonly", width=10)
        for box in (self.month_filter, self.cat_filter, kind_filter):
            box.pack(side="left", padx=(0, 6))
            box.bind("<<ComboboxSelected>>", lambda event: self.fill_table())
        self.totals = ttk.Label(bar, text="", style="Card.TLabel")
        self.totals.pack(side="right")
        frame, self.tree = make_table(right, [("date", "Date", 90, "center"), ("kind", "Type", 70, "center"), ("cat", "Category", 120, "w"),
                                              ("method", "Paid with", 90, "w"), ("note", "Note", 190, "w"), ("amt", "Amount", 90, "e")], height=14)
        frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        buttons = ttk.Frame(right, style="Card.TFrame")
        buttons.grid(row=4, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(buttons, text="Export CSV", command=self.export_csv).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete selected", style="Danger.TButton", command=self.delete_selected).pack(side="left")

    def kind_changed(self):
        cats = choices(INCOME_CATS if self.v_kind.get() == "Income" else EXPENSE_CATS)
        self.cat_box.configure(values=cats)
        self.v_cat.set(cats[0])

    def quick_add(self):
        try:
            e = parse_quick(self.v_quick.get())
            self.db.add(e["date"], e["amount"], e["category"], e["method"], e["note"], e["kind"])
        except ExpenseError as err:
            return self.ctx.toast(str(err), "error")
        self.v_quick.set("")
        self.ctx.toast(f"{e['kind']}: {money(e['amount'])} in {e['category']} via {e['method']} on {e['date']}", "success")
        self.refresh_all()

    def add_entry(self):
        try:
            self.db.add(self.entry_date.iso(), self.v_amount.get().replace(",", ""), strip_icon(self.v_cat.get()),
                        self.v_method.get(), self.v_note.get(), self.v_kind.get())
        except ExpenseError as err:
            return self.ctx.toast(str(err), "error")
        self.v_amount.set("")
        self.v_note.set("")
        self.ctx.toast("Entry added", "success")
        self.refresh_all()

    def delete_selected(self):
        for item in self.tree.selection():
            self.db.delete(int(item))
        self.refresh_all()

    def load_demo(self):
        if self.db.rows():
            return self.ctx.toast("Demo data is only added to an empty tracker", "warning")
        self.db.load_demo()
        self.ctx.toast("Three months of sample data added", "success")
        self.refresh_all()

    def export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="expenses.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Date", "Type", "Category", "Paid with", "Note", "Amount"])
                for _id, d, amount, cat, method, note, kind in reversed(self.db.rows()):
                    writer.writerow([d, kind, cat, method, note, amount])
        except OSError as err:
            self.ctx.toast(f"Could not save: {err}", "error")
        else:
            self.ctx.toast("Exported", "success")

    def fill_table(self):
        clear_table(self.tree)
        month = self.f_month.get()
        cat = strip_icon(self.f_cat.get()) if self.f_cat.get() != "All categories" else ""
        kind = self.f_kind.get()
        key = ""
        if month != "All months":
            y, m = parse_month(month)
            key = f"{y:04d}-{m:02d}"
        spent = earned = 0.0
        for row_id, d, amount, category, method, note, k in self.db.rows():
            if (key and not d.startswith(key)) or (cat and category != cat) or (kind != "All types" and k != kind):
                continue
            sign = "+" if k == "Income" else "-"
            spent += amount if k == "Expense" else 0
            earned += amount if k == "Income" else 0
            insert_row(self.tree, (d, k, f"{ICONS.get(category, '')} {category}", method, note, f"{sign}{amount:,.0f}"),
                       tag="success" if k == "Income" else None, iid=str(row_id))
        self.totals.config(text=f"In {money(earned)}   Out {money(spent)}   Net {money(earned - spent)}")

    # ---------- analytics ----------
    def build_analytics_tab(self):
        tab = self.tab("  \U0001F4CA Analytics  ")
        tab.columnconfigure((0, 1, 2), weight=1, uniform="an")
        tab.rowconfigure((1, 2), weight=1)
        head = ttk.Frame(tab)
        head.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        head.columnconfigure(5, weight=1)
        self.v_month = tk.StringVar()
        self.month_box = ttk.Combobox(head, textvariable=self.v_month, state="readonly", width=12)
        self.month_box.grid(row=0, column=0, padx=(0, 10), sticky="n")
        self.month_box.bind("<<ComboboxSelected>>", lambda event: self.draw_analytics())
        self.stats = {}
        for i, (key, eyebrow) in enumerate((("income", "INCOME"), ("spent", "SPENT"), ("saved", "SAVED"), ("proj", "PROJECTED SPEND"))):
            box = card(head, padding=10)
            box.grid(row=0, column=1 + i, sticky="ew", padx=(0, 8))
            ttk.Label(box, text=eyebrow, style="CardEyebrow.TLabel").pack(anchor="w")
            value = ttk.Label(box, text="-", style="Stat.TLabel", font=(self.ctx.theme.family, 17, "bold"))
            value.pack(anchor="w")
            sub = ttk.Label(box, text="", style="CardMuted.TLabel")
            sub.pack(anchor="w")
            self.stats[key] = (value, sub)
        head.columnconfigure((1, 2, 3, 4), weight=1)
        specs = [("DOUGHNUT", "Where the money goes", DonutChart, 0, 0), ("DAILY", "Spending per day", BarChart, 0, 1),
                 ("PACE", "Cumulative spend vs budget", LineChart, 0, 2), ("TREND", "Income vs expense (6 months)", BarChart, 1, 0),
                 ("METHODS", "How you pay", HBarChart, 1, 1)]
        self.charts = {}
        for name, (eyebrow, title, cls, r, c) in zip(("cats", "daily", "pace", "trend", "methods"), specs):
            box = titled_card(tab, eyebrow, title, grid=dict(row=1 + r, column=c, sticky="nsew", padx=(0 if c == 0 else 8, 0), pady=(0, 8)))
            box.columnconfigure(0, weight=1)
            chart = cls(box, self.ctx.theme, height=190)
            chart.grid(row=2, column=0, columnspan=3, sticky="nsew")
            self.charts[name] = chart
        notes = titled_card(tab, "INSIGHTS", "Top categories and unusual days", grid=dict(row=2, column=2, sticky="nsew", padx=(8, 0), pady=(0, 8)))
        self.insights = ttk.Frame(notes, style="Card.TFrame")
        self.insights.grid(row=2, column=0, columnspan=3, sticky="nw")

    def draw_analytics(self):
        theme, c = self.ctx.theme, self.ctx.theme.colors
        year, month = parse_month(self.v_month.get())
        rows, today = self.db.rows(), date.today()
        s = month_summary(rows, year, month)
        dim = calendar.monthrange(year, month)[1]
        day_totals = {d: sum(v.values()) for d, v in s["days"].items()}
        fc = forecast(s["days"], year, month)
        budgets = self.db.budgets()
        total_budget = sum(budgets.values())
        saved = s["income"] - s["expense"]
        self.stats["income"][0].config(text=money(s["income"]))
        self.stats["income"][1].config(text=f"{len(s['income_cats'])} sources")
        self.stats["spent"][0].config(text=money(s["expense"]))
        self.stats["spent"][1].config(text=f"{money(fc['daily_avg'])} per day")
        self.stats["saved"][0].config(text=money(saved))
        self.stats["saved"][1].config(text=f"{saved / s['income']:.0%} of income" if s["income"] else "no income logged")
        self.stats["proj"][0].config(text=money(fc["projected"]))
        self.stats["proj"][1].config(text=(f"budget {money(total_budget)}" if total_budget else "set budgets to compare"))
        self.charts["cats"].set(list(s["cats"].items()), center=money(s["expense"]), sub="spent", fmt="Rs {:,.0f}")
        shown = dim if (year, month) != (today.year, today.month) else today.day
        labels = [str(d) for d in range(1, shown + 1)]
        self.charts["daily"].set(labels, [("Spent", [day_totals.get(d, 0) for d in range(1, shown + 1)])], fmt="Rs {:,.0f}",
                                 goal=total_budget / dim if total_budget else None, goal_label="daily budget")
        cum, run = [], 0.0
        for d in range(1, shown + 1):
            run += day_totals.get(d, 0)
            cum.append(run)
        series = [("Spent so far", cum)]
        if total_budget:
            series.append(("Budget pace", [total_budget * d / dim for d in range(1, shown + 1)]))
        self.charts["pace"].set(labels, series, fmt="Rs {:,.0f}", fill=True)
        keys = [k for k in self.db.months()][:6][::-1]
        inc, exp = [], []
        for key in keys:
            y, m = map(int, key.split("-"))
            ms = month_summary(rows, y, m)
            inc.append(ms["income"])
            exp.append(ms["expense"])
        self.charts["trend"].set([label_month(k)[:3] for k in keys], [("Income", inc), ("Expense", exp)], fmt="Rs {:,.0f}")
        self.charts["methods"].set(sorted(s["methods"].items(), key=lambda p: -p[1]), fmt="Rs {:,.0f}")
        for child in self.insights.winfo_children():
            child.destroy()
        top = heapq.nlargest(3, s["cats"].items(), key=lambda p: p[1])
        for i, (cat, value) in enumerate(top):
            ttk.Label(self.insights, text=f"{ICONS.get(cat, '')} {cat}", style="Card.TLabel").grid(row=i, column=0, sticky="w", padx=(0, 14))
            ttk.Label(self.insights, text=f"{money(value)}  ({value / s['expense']:.0%})", style="CardMuted.TLabel").grid(row=i, column=1, sticky="w")
        odd = unusual_days(s["days"])[:3]
        row = len(top) + 1
        if odd:
            for d, value in odd:
                line = ttk.Frame(self.insights, style="Card.TFrame")
                line.grid(row=row, column=0, columnspan=2, sticky="w", pady=2)
                badge(line, theme, "UNUSUAL", "warn").pack(side="left", padx=(0, 8))
                ttk.Label(line, text=f"{d} {MONTHS[month - 1]}: {money(value)} spent", style="Card.TLabel").pack(side="left")
                row += 1
        else:
            ttk.Label(self.insights, text="No unusual spending days", style="CardMuted.TLabel").grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))
        theme.recolor(self)

    # ---------- budgets ----------
    def build_budget_tab(self):
        tab = self.tab("  \U0001F3AF Budgets  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        form = titled_card(tab, "MONTHLY LIMITS", "Set a budget", grid=dict(row=0, column=0, sticky="ns", padx=(0, 10)))
        form.columnconfigure(1, weight=1)
        self.v_b_cat, self.v_b_amount = tk.StringVar(value=choices(EXPENSE_CATS)[0]), tk.StringVar()
        add_field(form, 2, "Category", ttk.Combobox(form, textvariable=self.v_b_cat, values=choices(EXPENSE_CATS), state="readonly", width=22))
        add_field(form, 3, "Monthly limit (Rs)", ttk.Entry(form, textvariable=self.v_b_amount, width=24))
        info_icon(form, "Enter 0 to remove a budget.").grid(row=3, column=2, padx=4)
        ttk.Button(form, text="Save budget", style="Accent.TButton", command=self.save_budget).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        ttk.Separator(form).grid(row=5, column=0, columnspan=3, sticky="ew", pady=12)
        ttk.Label(form, text="Savings goal", style="CardTitle.TLabel").grid(row=6, column=0, columnspan=3, sticky="w")
        self.v_goal = tk.StringVar(value=self.db.setting("goal", ""))
        add_field(form, 7, "Target (Rs)", ttk.Entry(form, textvariable=self.v_goal, width=24))
        ttk.Button(form, text="Save goal", command=self.save_goal).grid(row=8, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        self.goal_label = ttk.Label(form, text="", style="Card.TLabel", wraplength=260, justify="left")
        self.goal_label.grid(row=9, column=0, columnspan=3, sticky="w", pady=(10, 0))

        right = titled_card(tab, "THIS MONTH", "Budget usage", grid=dict(row=0, column=1, sticky="nsew"))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)
        frame, self.budget_tree = make_table(right, [("cat", "Category", 130, "w"), ("limit", "Limit", 90, "e"), ("spent", "Spent", 90, "e"),
                                                     ("left", "Left", 90, "e"), ("pct", "Used", 70, "center"), ("st", "Status", 80, "center")], height=7)
        frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        self.budget_chart = HBarChart(right, self.ctx.theme, height=220)
        self.budget_chart.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(10, 0))

    def save_budget(self):
        try:
            self.db.set_budget(strip_icon(self.v_b_cat.get()), self.v_b_amount.get().replace(",", ""))
        except ExpenseError as err:
            return self.ctx.toast(str(err), "error")
        self.v_b_amount.set("")
        self.ctx.toast("Budget saved", "success")
        self.refresh_all()

    def save_goal(self):
        try:
            value = float(self.v_goal.get().replace(",", ""))
            if value <= 0:
                raise ValueError
        except ValueError:
            return self.ctx.toast("Enter the goal as a positive number", "error")
        self.db.set_setting("goal", value)
        self.ctx.toast("Goal saved", "success")
        self.refresh_all()

    def draw_budgets(self):
        c = self.ctx.theme.colors
        today = date.today()
        rows = self.db.rows()
        s = month_summary(rows, today.year, today.month)
        clear_table(self.budget_tree)
        items = []
        for cat, limit in sorted(self.db.budgets().items()):
            spent = s["cats"].get(cat, 0.0)
            pct = spent / limit * 100
            status, tag = ("OVER", "danger") if pct > 100 else ("WATCH", "warning") if pct >= 80 else ("OK", "success")
            insert_row(self.budget_tree, (f"{ICONS.get(cat, '')} {cat}", f"{limit:,.0f}", f"{spent:,.0f}", f"{limit - spent:,.0f}", f"{pct:.0f}%", status), tag=tag)
            items.append((cat, min(pct, 100), c["danger"] if pct > 100 else c["warning"] if pct >= 80 else c["success"],
                          f"{cat}: {money(spent)} of {money(limit)} ({pct:.0f}%)"))
        self.budget_chart.set(items, fmt="{:.0f}%", max_value=100)
        goal = float(self.db.setting("goal", "0") or 0)
        if goal:
            net_by_month = []
            for key in self.db.months()[1:4]:
                y, m = map(int, key.split("-"))
                ms = month_summary(rows, y, m)
                net_by_month.append(ms["income"] - ms["expense"])
            monthly = statistics.mean(net_by_month) if net_by_month else 0
            saved = max(0.0, sum(r[2] if r[6] == "Income" else -r[2] for r in rows))
            self.goal_label.config(text=f"Saved {money(min(saved, goal))} of {money(goal)} ({min(saved / goal, 1):.0%})\n{goal_eta(goal, saved, monthly)}")
        else:
            self.goal_label.config(text="Set a goal to see how long it will take")

    # ---------- split bills ----------
    def build_split_tab(self):
        tab = self.tab("  \U0001F91D Split bills  ")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(0, weight=1)
        left = titled_card(tab, "GROUP EXPENSES", "Who paid what?", grid=dict(row=0, column=0, sticky="ns", padx=(0, 10)))
        left.rowconfigure(2, weight=1)
        self.payers = tk.Text(left, width=30, height=10, wrap="word", font=(self.ctx.theme.family, 10))
        self.payers.insert("1.0", "Asha paid 2400\nRohit paid 600\nMeera paid 0\nKabir paid 1500\nZoya paid 0")
        self.ctx.theme.recolor(self.payers)
        self.payers.grid(row=2, column=0, columnspan=2, sticky="nsew")
        info_icon(left, "One person per line:  Name paid amount.\nEveryone listed shares the total equally, even people who paid 0.").grid(row=2, column=2, sticky="n", padx=4)
        ttk.Button(left, text="Calculate settlement", style="Accent.TButton", command=self.settle).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.split_note = ttk.Label(left, text="", style="CardMuted.TLabel", wraplength=280, justify="left")
        self.split_note.grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        right = ttk.Frame(tab)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure((0, 1), weight=1)
        pay = titled_card(right, "SETTLEMENT", "Fewest payments to settle up", grid=dict(row=0, column=0, sticky="nsew", pady=(0, 10)))
        pay.columnconfigure(0, weight=1)
        frame, self.transfer_tree = make_table(pay, [("from", "Who pays", 160, "w"), ("to", "Pays to", 160, "w"), ("amt", "Amount", 110, "e")], height=5)
        frame.grid(row=2, column=0, columnspan=3, sticky="ew")
        chart = titled_card(right, "BALANCES", "Paid vs fair share", grid=dict(row=1, column=0, sticky="nsew"))
        chart.columnconfigure(0, weight=1)
        self.split_chart = BarChart(chart, self.ctx.theme, height=200)
        self.split_chart.grid(row=2, column=0, columnspan=3, sticky="nsew")

    def settle(self):
        try:
            paid = parse_payers(self.payers.get("1.0", "end"))
            share, balances, transfers = settle_up(paid)
        except ExpenseError as err:
            return self.ctx.toast(str(err), "error")
        clear_table(self.transfer_tree)
        for debtor, creditor, amount in transfers:
            insert_row(self.transfer_tree, (debtor, creditor, f"Rs {amount:,.2f}"))
        names = list(paid)
        self.split_chart.set(names, [("Paid", [paid[n] for n in names]), ("Fair share", [share] * len(names))], fmt="Rs {:,.0f}")
        self.split_note.config(text=f"Total {money(sum(paid.values()))} for {len(paid)} people: {money(share)} each. "
                                    f"{len(transfers)} payment{'s' if len(transfers) != 1 else ''} settle everything.")
        self.ctx.theme.recolor(self)

    # ---------- refresh ----------
    def refresh_all(self):
        months = [label_month(k) for k in self.db.months()]
        self.month_filter.configure(values=["All months"] + months)
        self.month_box.configure(values=months)
        if self.v_month.get() not in months:
            self.v_month.set(months[0])
        if self.f_month.get() not in ["All months"] + months:
            self.f_month.set("All months")
        self.fill_table()
        self.draw_analytics()
        self.draw_budgets()
