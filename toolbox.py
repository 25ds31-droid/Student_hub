"""
Student Toolbox - a drop-down workbench of tools. Every tool is a plain function; if it returns
(text, chart) the chart (a dict for hub_charts.make_chart) is drawn under the text result.

Converters | Math & Data (prime explorer, combinatorics, Fibonacci/golden ratio, text analyser, number theory,
matrix lab with NumPy, set lab, statistics lab, linear regression) | Geometry | Academics (report card, CGPA
planner) | Money (loan EMI with prepayment, SIP planner, payroll, raise, wallet with custom exceptions)
"""
import collections
import statistics
import functools
import math
import re
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog

from hub_charts import make_chart
from hub_theme import Tooltip, add_field, card, info_icon, titled_card

USD_RATE = 83.0                                                     # approximate Rs per US dollar


# ======================= exceptions (Wk 5) =======================
class WalletError(Exception):
    pass


class InsufficientFundsError(WalletError):
    pass


class InvalidAccountError(WalletError):
    pass


# ======================= converters =======================
def currency(amount, direction="INR to USD", rate=USD_RATE):
    value, rate = float(amount), float(rate)
    if rate <= 0:
        raise ValueError("The exchange rate must be positive")
    return f"Rs {value:,.2f} = USD {value / rate:,.2f}" if direction == "INR to USD" else f"USD {value:,.2f} = Rs {value * rate:,.2f}"


def temperature(value, unit="Celsius"):
    v = float(value)
    c = {"Celsius": v, "Fahrenheit": (v - 32) * 5 / 9, "Kelvin": v - 273.15}[unit]
    return f"{c:.2f} C   |   {c * 9 / 5 + 32:.2f} F   |   {c + 273.15:.2f} K"


LENGTHS = {"millimetre": 0.001, "centimetre": 0.01, "metre": 1.0, "kilometre": 1000.0,
           "inch": 0.0254, "foot": 0.3048, "yard": 0.9144, "mile": 1609.344}


def length(value, frm="inch", to="centimetre"):
    return f"{float(value):g} {frm} = {float(value) * LENGTHS[frm] / LENGTHS[to]:.4g} {to}"


def inches_to_cm(text):
    """Uses map(): '5, 10, 15' -> [12.7, 25.4, 38.1]"""
    inches = [float(x) for x in re.split(r"[,\s]+", text.strip()) if x]
    return str(list(map(lambda x: round(x * 2.54, 2), inches)))


# ======================= math drills =======================
def is_prime(text):
    n = int(text)
    if n < 2:
        return f"{n} is not prime"
    for d in range(2, math.isqrt(n) + 1):
        if n % d == 0:
            return f"{n} is not prime ({d} x {n // d})"
    return f"{n} is prime"


def factorial(text):
    n = int(text)
    if not 0 <= n <= 500:
        raise ValueError("Enter a whole number from 0 to 500")
    result, i = 1, 2
    while i <= n:
        result *= i
        i += 1
    return f"{n}! = {result}"


def fibonacci(text):
    n = int(text)
    if not 1 <= n <= 90:
        raise ValueError("Enter how many terms (1 to 90)")
    a, b, out = 0, 1, []
    while len(out) < n:                                          # while-loop version
        out.append(a)
        a, b = b, a + b
    return ", ".join(map(str, out))


def multiplication_table(text, upto=10):
    n = int(text)
    return "\n".join(f"{n} x {i:>2} = {n * i}" for i in range(1, int(upto) + 1))


def palindrome(text):
    cleaned = re.sub(r"[^a-z0-9]", "", text.lower())
    if not cleaned:
        raise ValueError("Type some text")
    return f"'{text}' is {'' if cleaned == cleaned[::-1] else 'not '}a palindrome"


def sum_digits(text):
    """Uses functools.reduce()"""
    digits = re.sub(r"\D", "", text)
    if not digits:
        raise ValueError("Enter a number")
    return f"Sum of digits of {digits} = {functools.reduce(lambda a, b: a + int(b), digits, 0)}"


def disjoint_sets(a_text, b_text):
    a, b = (set(re.split(r"[,\s]+", t.strip())) - {""} for t in (a_text, b_text))
    common = a & b
    return "No elements in common (disjoint)" if a.isdisjoint(b) else f"Common elements: {sorted(common)}"


def runner_speeds(text):
    speeds = [float(x) for x in re.split(r"[,\s]+", text.strip()) if x]
    if len(speeds) < 2:
        raise ValueError("Enter at least two speeds")
    avg = sum(speeds) / len(speeds)
    qualified = [s for s in speeds if s > 1.5 * avg]
    return f"Average speed: {avg:.2f}\nQualify (more than 1.5 x average = {1.5 * avg:.2f}): {qualified or 'nobody'}"


# ======================= geometry (OOP) =======================
class Polygon:
    def __init__(self, sides=None):
        self.sides = list(sides or [])

    def input_sides(self, text):
        self.sides = [float(x) for x in re.split(r"[,\s]+", text.strip()) if x]
        if any(s <= 0 for s in self.sides):
            raise ValueError("Sides must be positive")

    def display_sides(self):
        return "Sides: " + ", ".join(f"{s:g}" for s in self.sides)


class Triangle(Polygon):                                          # inheritance
    def area(self):
        if len(self.sides) != 3:
            raise ValueError("A triangle needs exactly 3 sides")
        a, b, c = self.sides
        if a + b <= c or a + c <= b or b + c <= a:
            raise ValueError("These sides cannot form a triangle")
        s = (a + b + c) / 2
        return math.sqrt(s * (s - a) * (s - b) * (s - c))      # Heron's formula


def area(shape, d1, d2="0"):
    if shape == "Circle":
        return f"Area = {math.pi * float(d1) ** 2:.2f} (radius {d1})"
    if shape == "Rectangle":
        return f"Area = {float(d1) * float(d2):.2f} ({d1} x {d2})"
    tri = Triangle()
    tri.input_sides(d1)
    return f"{tri.display_sides()}\nArea = {tri.area():.2f} (Heron's formula)"


# ======================= grades & report card =======================
def grade_for(pct):
    for limit, grade, points in ((90, "O", 10), (80, "A+", 9), (70, "A", 8), (60, "B+", 7),
                                 (50, "B", 6), (40, "C", 5)):
        if pct >= limit:
            return grade, points
    return "F", 0


def report_card(student, marks_text):
    """marks_text: one 'Subject score/max [credits]' per line."""
    rows = []
    for line in marks_text.strip().splitlines():
        m = re.fullmatch(r"\s*([A-Za-z][\w .&-]*?)\s+(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)(?:\s+(\d+(?:\.\d+)?))?\s*", line)
        if not m:
            raise ValueError(f"Cannot read '{line.strip()}'. Use  Subject 78/100  or  Subject 78/100 4")
        name, got, top, credits = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4) or 1)
        if top <= 0 or not 0 <= got <= top:
            raise ValueError(f"Marks out of range in '{line.strip()}'")
        rows.append((name, got, top, credits))
    if not rows:
        raise ValueError("Enter at least one subject")
    total, maximum = sum(r[1] for r in rows), sum(r[2] for r in rows)
    pct = total / maximum * 100
    points = sum(grade_for(r[1] / r[2] * 100)[1] * r[3] for r in rows) / sum(r[3] for r in rows)
    lines = ["=" * 50, f"REPORT CARD - {student or 'Student'}", f"Date: {datetime.now():%d %b %Y}", "=" * 50,
             f"{'Subject':<20}{'Marks':>10}{'%':>8}{'Grade':>7}"]
    for name, got, top, _ in rows:
        p = got / top * 100
        lines.append(f"{name:<20}{got:>5g}/{top:<4g}{p:>8.1f}{grade_for(p)[0]:>7}")
    lines += ["-" * 50, f"Total: {total:g}/{maximum:g}    Percentage: {pct:.2f}%", f"Overall grade: {grade_for(pct)[0]}    CGPA (10-point): {points:.2f}"]
    chart = {"kind": "bar", "labels": [r[0][:8] for r in rows], "series": [("Percentage", [round(r[1] / r[2] * 100, 1) for r in rows])],
             "fmt": "{:.1f}%", "goal": 40, "goal_label": "pass mark 40%"}
    return "\n".join(lines), chart


# ======================= pay calculator =======================
def payroll(emp_id, name, basic):
    basic = float(basic)
    if basic <= 0:
        raise ValueError("Basic salary must be positive")
    da, hra, pf = 0.80 * basic, 0.40 * basic, 0.12 * basic
    gross = basic + da + hra
    tax = 0.05 * gross if gross > 50000 else 0.0
    text = (f"Employee {emp_id}: {name}\nBasic {basic:,.2f} + DA {da:,.2f} + HRA {hra:,.2f} = Gross {gross:,.2f}\n"
            f"PF (12% of basic): {pf:,.2f}   Tax (5% if gross > 50,000): {tax:,.2f}\nNET SALARY: {gross - pf - tax:,.2f}")
    return text, {"kind": "donut", "items": [("Take-home", gross - pf - tax), ("PF", pf), ("Tax", tax)], "center": f"{(gross - pf - tax) / gross:.0%}",
                  "sub": "of gross", "fmt": "Rs {:,.0f}"}


def give_raise(percent):
    employees = {1: {"name": "Asha", "age": 28, "salary": 40000.0},
                 2: {"name": "Rohit", "age": 34, "salary": 52000.0},
                 3: {"name": "Meera", "age": 41, "salary": 61000.0}}        # nested dictionary
    pct = float(percent)

    def raise_all(data):
        for record in data.values():
            record["salary"] = round(record["salary"] * (1 + pct / 100), 2)
    before = {k: v["salary"] for k, v in employees.items()}
    raise_all(employees)
    text = "\n".join(f"{k}: {v['name']:<6} age {v['age']}  new salary {v['salary']:,.2f}" for k, v in employees.items())
    names = [v["name"] for v in employees.values()]
    return text, {"kind": "bar", "labels": names, "series": [("Before", list(before.values())), ("After", [v["salary"] for v in employees.values()])],
                  "fmt": "Rs {:,.0f}"}


# ======================= wallet (custom exceptions, immutable log) =======================
class Account:
    def __init__(self, number, holder, balance=0.0):
        if not re.fullmatch(r"\d{10}", number):
            raise InvalidAccountError("Account numbers have exactly 10 digits")
        self.number, self.holder, self._balance = number, holder, float(balance)
        self.log = ()                                                      # tuple: records cannot be edited

    @property
    def balance(self):
        return self._balance

    def _record(self, kind, amount):
        self.log += ((datetime.now().strftime("%H:%M:%S"), kind, amount, self._balance),)

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self._balance += amount
        self._record("DEPOSIT", amount)

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Withdrawal must be positive")
        if amount > self._balance:
            raise InsufficientFundsError(f"Balance Rs {self._balance:,.2f} is less than Rs {amount:,.2f}")
        self._balance -= amount
        self._record("WITHDRAW", amount)


ACCOUNTS = {}


def wallet(number, holder, operation, amount):
    number = number.strip()
    if number not in ACCOUNTS:
        ACCOUNTS[number] = Account(number, holder.strip() or "Student")       # raises InvalidAccountError
    account = ACCOUNTS[number]
    value = float(amount)
    getattr(account, operation.lower())(value)
    history = "\n".join(f"  {t}  {k:<9} {a:>10,.2f}  balance {b:>10,.2f}" for t, k, a, b in account.log)
    text = f"Account {account.number} ({account.holder})\nBalance: Rs {account.balance:,.2f}\n\nTransaction log (tuples)\n{history}"
    return text, {"kind": "line", "labels": [f"#{i + 1}" for i in range(len(account.log))], "series": [("Balance", [rec[3] for rec in account.log])],
                  "fmt": "Rs {:,.2f}", "fill": True}


# ======================= exception lab =======================
def exception_lab():
    cases = [("ValueError", lambda: int("abc")), ("ZeroDivisionError", lambda: 10 / 0),
             ("IndexError", lambda: [1, 2, 3][5]), ("KeyError", lambda: {"a": 1}["b"]),
             ("TypeError", lambda: "5" + 5), ("FileNotFoundError", lambda: open("no_such_file.txt")),
             ("InsufficientFundsError (custom)", lambda: Account("1234567890", "Demo", 100).withdraw(500))]
    lines = []
    for label, action in cases:
        try:
            action()
        except (ValueError, ZeroDivisionError, IndexError, KeyError, TypeError, FileNotFoundError, WalletError) as err:
            lines.append(f"{label:<34} caught -> {type(err).__name__}: {err}")
        else:
            lines.append(f"{label}: no error")
        finally:
            pass
    lines.append("\nEvery case ran inside try / except / else / finally, so the program kept going.")
    return "\n".join(lines)


# ======================= advanced math & data tools =======================
def numbers_from(text, minimum=1):
    values = [float(x) for x in re.split(r"[,;\s]+", text.strip()) if x]
    if len(values) < minimum:
        raise ValueError(f"Enter at least {minimum} number{'s' if minimum > 1 else ''}")
    return values


def prime_explorer(text):
    n = int(text)
    if not 2 <= n <= 5_000_000:
        raise ValueError("Enter a whole number from 2 to 5,000,000")
    sieve = bytearray([1]) * (n + 1)
    sieve[0:2] = b"\x00\x00"
    for i in range(2, math.isqrt(n) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(sieve[i * i::i]))
    primes = [i for i, flag in enumerate(sieve) if flag]
    twins = sum(1 for a, b in zip(primes, primes[1:]) if b - a == 2)
    gap = max(((b - a, a, b) for a, b in zip(primes, primes[1:])), default=(0, 0, 0))
    m, factors, d = n, collections.Counter(), 2
    while d * d <= m:
        while m % d == 0:
            factors[d] += 1
            m //= d
        d += 1
    if m > 1:
        factors[m] += 1
    fact = " x ".join(f"{p}^{e}" if e > 1 else str(p) for p, e in sorted(factors.items()))
    verdict = f"{n} is prime" if sieve[n] else f"{n} is composite = {fact}"
    prev_p = max((p for p in primes if p < n), default=None)
    next_p = next((p for p in range(n + 1, n + 2000) if all(p % q for q in range(2, math.isqrt(p) + 1))), None)
    buckets = 10
    edges = [round(n * i / buckets) for i in range(buckets + 1)]
    counts = [sum(1 for p in primes if edges[i] < p <= edges[i + 1]) for i in range(buckets)]
    text_out = (f"{verdict}\nPrimes up to {n:,}: {len(primes):,}  (density {len(primes) / n:.2%}, n / ln n estimate {n / math.log(n):,.0f})\n"
                f"Twin prime pairs: {twins:,}   Largest gap: {gap[0]} (between {gap[1]} and {gap[2]})\n"
                f"Previous prime: {prev_p}   Next prime: {next_p}\nLast five primes <= {n}: {primes[-5:]}")
    return text_out, {"kind": "bar", "labels": [f"{edges[i + 1]:,}"[:6] for i in range(buckets)],
                      "series": [("Primes in range", counts)], "fmt": "{:,.0f} primes"}


def combinatorics(n_text, r_text):
    n, r = int(n_text), int(r_text)
    if not 0 <= n <= 500 or not 0 <= r <= n:
        raise ValueError("Use 0 <= r <= n <= 500")
    catalan = math.comb(2 * min(n, 250), min(n, 250)) // (min(n, 250) + 1)
    text = (f"{n}! has {len(str(math.factorial(n)))} digits" + (f" = {math.factorial(n)}" if n <= 25 else "") + "\n"
            f"nPr (ordered) = {math.perm(n, r):,}\nnCr (choose)  = {math.comb(n, r):,}\n"
            f"Derangements of {min(n, 20)} items = {sum((-1) ** k * math.factorial(min(n, 20)) // math.factorial(k) for k in range(min(n, 20) + 1)):,}\n"
            f"Catalan number C({min(n, 250)}) has {len(str(catalan))} digits\n"
            f"Probability of a specific {r}-card hand from {n} = 1 in {math.comb(n, r):,}")
    row = list(range(min(n, 30) + 1))
    return text, {"kind": "bar", "labels": [str(k) for k in row], "series": [(f"C({min(n, 30)}, k)", [math.comb(min(n, 30), k) for k in row])],
                  "fmt": "{:,.0f} ways"}


def fibonacci_golden(text):
    n = int(text)
    if not 2 <= n <= 300:
        raise ValueError("Enter how many terms (2 to 300)")
    seq, (a, b) = [], (0, 1)
    while len(seq) < n:                                                   # while-loop generator
        seq.append(a)
        a, b = b, a + b
    ratios = [seq[i + 1] / seq[i] for i in range(1, n - 1)]
    phi = (1 + math.sqrt(5)) / 2
    binet = round((phi ** (n - 1) - (1 - phi) ** (n - 1)) / math.sqrt(5)) if n < 70 else None
    shown = ", ".join(map(str, seq[:20])) + (" ..." if n > 20 else "")
    text_out = (f"First terms: {shown}\nF({n - 1}) has {len(str(seq[-1]))} digits"
                + (f"; Binet's formula agrees: {binet == seq[-1]}" if binet is not None else "") + "\n"
                f"Ratio F(k+1)/F(k) -> golden ratio {phi:.10f}\nLast ratio {ratios[-1]:.10f}   error {abs(ratios[-1] - phi):.2e}\n"
                f"Even terms: {sum(1 for x in seq if x % 2 == 0)} ({sum(x for x in seq if x % 2 == 0) if n < 40 else 'sum hidden'})")
    k = min(len(ratios), 25)
    return text_out, {"kind": "line", "labels": [str(i + 2) for i in range(k)],
                      "series": [("F(k+1)/F(k)", ratios[:k]), ("Golden ratio", [phi] * k)], "fmt": "{:.5f}"}


def text_analyser(text):
    if not text.strip():
        raise ValueError("Type or paste some text")
    cleaned = re.sub(r"[^a-z0-9]", "", text.lower())
    words = re.findall(r"[A-Za-z']+", text.lower())

    def longest_pal(t):
        best = ""
        for centre in range(len(t)):
            for lo, hi in ((centre, centre), (centre, centre + 1)):
                while lo >= 0 and hi < len(t) and t[lo] == t[hi]:
                    lo, hi = lo - 1, hi + 1
                if hi - lo - 1 > len(best):
                    best = t[lo + 1:hi]
        return best
    stop = {"the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "on", "for", "with", "as", "at", "by"}
    freq = collections.Counter(w for w in words if w not in stop and len(w) > 1).most_common(8)
    sentences = [x for x in re.split(r"[.!?]+", text) if x.strip()]
    pal = bool(cleaned) and cleaned == cleaned[::-1]
    text_out = (f"Whole text is {'' if pal else 'not '}a palindrome (ignoring spaces and punctuation)\n"
                f"Longest palindromic piece: '{longest_pal(cleaned)}'\n"
                f"{len(words)} words, {len(set(words))} unique, {len(sentences)} sentences, {len(text)} characters\n"
                f"Average word length {sum(map(len, words)) / max(len(words), 1):.1f}   Lexical variety {len(set(words)) / max(len(words), 1):.0%}")
    return text_out, {"kind": "hbar", "items": [(w, c) for w, c in freq], "fmt": "{:g}x"}


def number_theory(text):
    nums = [int(x) for x in re.split(r"[,;\s]+", text.strip()) if x]
    if not 1 <= len(nums) <= 12 or any(n < 1 or n > 10 ** 12 for n in nums):
        raise ValueError("Enter 1 to 12 whole numbers between 1 and 10^12")
    lines, steps = [], []
    for n in nums:
        digits = [int(d) for d in str(n)]
        root = n
        while root > 9:
            root = sum(int(d) for d in str(root))
        divisors = [d for d in range(1, math.isqrt(n) + 1) if n % d == 0] if n < 10 ** 9 else []
        total = sum(divisors) + sum(n // d for d in divisors if d != n // d) if divisors else None
        armstrong = n == sum(d ** len(digits) for d in digits)
        c, k = n, 0
        while c != 1 and k < 10_000:
            c = c // 2 if c % 2 == 0 else 3 * c + 1
            k += 1
        steps.append((str(n), k))
        traits = [t for t, ok in (("perfect", total == 2 * n if total else False), ("Armstrong", armstrong),
                                  ("palindromic", str(n) == str(n)[::-1])) if ok]
        lines.append(f"{n}: digit sum {sum(digits)} (reduce) | digital root {root} | {2 * len(divisors) - (1 if divisors and divisors[-1] ** 2 == n else 0) if divisors else '?'} divisors"
                     f" | Collatz steps {k}" + (f" | {', '.join(traits)}" if traits else ""))
    g = functools.reduce(math.gcd, nums)
    l = functools.reduce(lambda x, y: x * y // math.gcd(x, y), nums)
    lines.append(f"\nGCD of all = {g}    LCM of all = {l}")
    return "\n".join(lines), {"kind": "hbar", "items": steps, "fmt": "{:g} steps"}


def matrix_lab(matrix_text, operation):
    import numpy as np
    try:
        rows = [[float(x) for x in re.split(r"[,;\s]+", line.strip()) if x] for line in matrix_text.strip().splitlines() if line.strip()]
        a = np.array(rows, dtype=float)
    except ValueError:
        raise ValueError("Write the matrix one row per line, numbers separated by spaces or commas") from None
    if a.ndim != 2 or len({len(r) for r in rows}) != 1:
        raise ValueError("Every row needs the same number of values")

    def show(m):
        return np.array2string(np.asarray(m), precision=4, suppress_small=True)
    square = a.shape[0] == a.shape[1]
    try:
        if operation == "Transpose":
            return f"Transpose:\n{show(a.T)}"
        if operation == "Rank":
            return f"Rank = {np.linalg.matrix_rank(a)}   (shape {a.shape[0]} x {a.shape[1]})"
        if operation == "Solve Ax = b (last column is b)":
            coeff, rhs = a[:, :-1], a[:, -1]
            if coeff.shape[0] != coeff.shape[1]:
                raise ValueError("Use n equations with n unknowns plus the b column")
            x = np.linalg.solve(coeff, rhs)
            return "Solution:\n" + "\n".join(f"  x{i + 1} = {v:.6g}" for i, v in enumerate(x)) + f"\nCheck: max |Ax - b| = {np.max(np.abs(coeff @ x - rhs)):.2e}", \
                {"kind": "bar", "labels": [f"x{i + 1}" for i in range(len(x))], "series": [("Value", list(map(float, x)))], "fmt": "{:.4g}"}
        if not square:
            raise ValueError(f"{operation} needs a square matrix")
        if operation == "Determinant":
            return f"det = {np.linalg.det(a):.6g}\n" + ("Singular: no inverse exists" if abs(np.linalg.det(a)) < 1e-12 else "Invertible")
        if operation == "Inverse":
            return f"Inverse:\n{show(np.linalg.inv(a))}\nCheck A x A^-1 = I:\n{show(a @ np.linalg.inv(a))}"
        if operation == "Square (A x A)":
            return f"A x A:\n{show(a @ a)}"
        if operation == "Eigenvalues":
            values = np.linalg.eigvals(a)
            return "Eigenvalues:\n" + "\n".join(f"  {v:.5g}" for v in values) + f"\nTrace = {np.trace(a):.6g} (sum of eigenvalues)", \
                {"kind": "bar", "labels": [f"l{i + 1}" for i in range(len(values))], "series": [("Real part", [float(v.real) for v in values])], "fmt": "{:.4g}"}
    except np.linalg.LinAlgError as err:
        raise ValueError(f"Cannot do that: {err}") from None
    raise ValueError("Pick an operation")


def set_lab(a_text, b_text):
    a, b = (set(re.split(r"[,;\s]+", t.strip())) - {""} for t in (a_text, b_text))
    if not a and not b:
        raise ValueError("Enter some elements")
    union = a | b
    text = (f"Union ({len(union)}): {sorted(union)}\nIntersection ({len(a & b)}): {sorted(a & b)}\n"
            f"A - B ({len(a - b)}): {sorted(a - b)}\nB - A ({len(b - a)}): {sorted(b - a)}\n"
            f"Symmetric difference ({len(a ^ b)}): {sorted(a ^ b)}\nJaccard similarity: {len(a & b) / len(union):.0%}\n"
            f"Disjoint: {a.isdisjoint(b)}   A subset of B: {a <= b}   B subset of A: {b <= a}")
    return text, {"kind": "bar", "labels": ["Only A", "Both", "Only B"], "series": [("Elements", [len(a - b), len(a & b), len(b - a)])], "fmt": "{:g} elements"}


def statistics_lab(text):
    data = numbers_from(text, 4)
    q1, q2, q3 = statistics.quantiles(data, n=4)
    iqr = q3 - q1
    low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = [x for x in data if x < low or x > high]
    mean, sd = statistics.fmean(data), statistics.stdev(data)
    modes = statistics.multimode(data)
    skew = sum(((x - mean) / sd) ** 3 for x in data) / len(data) if sd else 0
    top = max(data)
    text_out = (f"n = {len(data)}   min {min(data):g}   max {top:g}   range {top - min(data):g}\n"
                f"Mean {mean:.3f}   Median {q2:g}   Mode {modes if len(modes) < len(data) else 'none'}\n"
                f"Std deviation (sample) {sd:.3f}   Variance {sd ** 2:.3f}   Coefficient of variation {sd / mean:.1%}\n"
                f"Quartiles Q1 {q1:g}  Q3 {q3:g}  IQR {iqr:g}   fences [{low:g}, {high:g}]\n"
                f"Outliers (1.5 x IQR rule): {outliers or 'none'}\nSkewness {skew:.2f} ({'right' if skew > 0.3 else 'left' if skew < -0.3 else 'roughly symmetric'})\n"
                f"z-score of the maximum: {(top - mean) / sd:.2f}")
    bins = max(4, min(12, math.ceil(1 + math.log2(len(data)))))
    lo, hi = min(data), top
    width = (hi - lo) / bins or 1
    counts = [0] * bins
    for x in data:
        counts[min(int((x - lo) / width), bins - 1)] += 1
    return text_out, {"kind": "bar", "labels": [f"{lo + i * width:.3g}" for i in range(bins)], "series": [("Count", counts)], "fmt": "{:g} values"}


def regression(x_text, y_text, predict):
    xs, ys = numbers_from(x_text, 3), numbers_from(y_text, 3)
    if len(xs) != len(ys):
        raise ValueError(f"You gave {len(xs)} x values but {len(ys)} y values")
    n, mx, my = len(xs), statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        raise ValueError("All x values are the same")
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys) or 1
    r2 = 1 - ss_res / ss_tot
    p = float(predict)
    text = (f"y = {slope:.4f} x + {intercept:.4f}\nR-squared {r2:.4f} (correlation r = {math.copysign(math.sqrt(max(r2, 0)), slope):.4f})\n"
            f"Standard error of estimate {math.sqrt(ss_res / max(n - 2, 1)):.4f}\n"
            f"Prediction at x = {p:g}:  y = {slope * p + intercept:.4f}   "
            f"({'interpolation' if min(xs) <= p <= max(xs) else 'extrapolation - treat with care'})")
    order = sorted(range(n), key=lambda i: xs[i])
    return text, {"kind": "line", "labels": [f"{xs[i]:g}" for i in order],
                  "series": [("Actual", [ys[i] for i in order]), ("Fitted", [slope * xs[i] + intercept for i in order])], "fmt": "{:,.2f}"}


# ======================= money: loans, investing =======================
def loan_planner(principal, rate, years, extra):
    p, r, y, extra = float(principal), float(rate) / 1200, float(years), float(extra)
    if p <= 0 or y <= 0 or y > 40 or rate and float(rate) < 0 or extra < 0:
        raise ValueError("Use a positive amount, 0-40 years, a rate of 0 or more and a non-negative extra payment")
    n = round(y * 12)
    emi = p / n if r == 0 else p * r * (1 + r) ** n / ((1 + r) ** n - 1)

    def run(extra_pay):
        balance, months, interest, path = p, 0, 0.0, [p]
        while balance > 0.005 and months < 1200:
            charge = balance * r
            pay = min(emi + extra_pay, balance + charge)
            balance, interest, months = balance + charge - pay, interest + charge, months + 1
            if months % 12 == 0:
                path.append(max(balance, 0))
        if months % 12:
            path.append(0.0)
        return months, interest, path
    base_m, base_i, base_path = run(0)
    new_m, new_i, new_path = run(extra)
    text = (f"EMI: Rs {emi:,.0f} per month for {n} months\nTotal interest: Rs {base_i:,.0f}   Total paid: Rs {p + base_i:,.0f} "
            f"(interest is {base_i / p:.0%} of the loan)\n")
    if extra:
        text += (f"With Rs {extra:,.0f} extra every month: loan ends in {new_m // 12}y {new_m % 12}m instead of {base_m // 12}y {base_m % 12}m\n"
                 f"Interest saved: Rs {base_i - new_i:,.0f}")
    else:
        text += "Add an extra monthly payment to see how much interest you can save."
    size = max(len(base_path), len(new_path))
    pad = lambda path: path + [0.0] * (size - len(path))
    series = [("Normal EMI", pad(base_path))] + ([("With extra payment", pad(new_path))] if extra else [])
    return text, {"kind": "line", "labels": [f"Y{i}" for i in range(size)], "series": series, "fmt": "Rs {:,.0f}", "fill": True}


def sip_planner(monthly, annual, years, step_up, inflation):
    sip, rate, y, step, infl = float(monthly), float(annual) / 1200, int(float(years)), float(step_up) / 100, float(inflation) / 100
    if sip <= 0 or not 1 <= y <= 50 or rate < 0:
        raise ValueError("Use a positive SIP, 1-50 years and a rate of 0 or more")
    value = invested = 0.0
    labels, put, grown, real = [], [], [], []
    for year in range(1, y + 1):
        for _ in range(12):
            value = (value + sip) * (1 + rate)
            invested += sip
        labels.append(f"Y{year}")
        put.append(invested)
        grown.append(value)
        real.append(value / (1 + infl) ** year)
        sip *= 1 + step
    text = (f"Invested: Rs {invested:,.0f}\nFinal value: Rs {value:,.0f}   Gain: Rs {value - invested:,.0f} ({(value - invested) / invested:.0%})\n"
            f"In today's money (after {infl:.0%} inflation): Rs {real[-1]:,.0f}\n"
            f"Rule of 72: money doubles about every {72 / (rate * 1200) if rate else float('inf'):.1f} years at this return"
            f"\nFinal monthly SIP after step-ups: Rs {sip / (1 + step):,.0f}")
    return text, {"kind": "line", "labels": labels, "series": [("Invested", put), ("Value", grown), ("Value in today's money", real)], "fmt": "Rs {:,.0f}", "fill": False}


def cgpa_planner(history, target, credits_left):
    rows = []
    for line in history.strip().splitlines():
        m = re.fullmatch(r"\s*([\w .-]+?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s*", line)
        if not m or not 0 <= float(m.group(2)) <= 10:
            raise ValueError(f"Cannot read '{line.strip()}'. Use  Sem1 8.2 22  (name, SGPA out of 10, credits)")
        rows.append((m.group(1), float(m.group(2)), float(m.group(3))))
    if not rows:
        raise ValueError("Enter at least one semester")
    goal, left = float(target), float(credits_left)
    done = sum(c for _, _, c in rows)
    cgpa = sum(s * c for _, s, c in rows) / done
    need = (goal * (done + left) - cgpa * done) / left if left > 0 else None
    verdict = ("n/a" if need is None else "already secured" if need <= 0 else f"{need:.2f} SGPA" + ("  (not possible: above 10)" if need > 10 else ""))
    running, cum = [], []
    td = tp = 0.0
    for _, s, c in rows:
        td, tp = td + c, tp + s * c
        cum.append(tp / td)
    text = (f"Current CGPA {cgpa:.2f} over {done:g} credits\nTarget {goal:.2f} with {left:g} credits left -> you need {verdict} on average\n"
            f"Best semester {max(rows, key=lambda r: r[1])[0]} ({max(r[1] for r in rows):.2f})   trend {cum[-1] - cum[0]:+.2f} since the first semester")
    return text, {"kind": "line", "labels": [r[0] for r in rows], "series": [("SGPA", [r[1] for r in rows]), ("Running CGPA", cum)], "limit": goal, "limit_label": "target", "fmt": "{:.2f}"}


# ======================= tool registry =======================
# (group, name, [fields], function, help); a field is (label, default, kind[, options])
MATRIX_OPS = ["Determinant", "Inverse", "Transpose", "Rank", "Eigenvalues", "Square (A x A)", "Solve Ax = b (last column is b)"]
GROUP_ICONS = {"Converters": "\U0001F504", "Math & Data": "\U0001F9EE", "Geometry": "\U0001F4D0", "Academics": "\U0001F393", "Money": "\U0001F4B0"}
TOOL_ICONS = {"Currency": "\U0001F4B1", "Temperature": "\U0001F321", "Length": "\U0001F4CF", "Inches to cm (list)": "\U0001F4CB",
              "Prime explorer": "\U0001F522", "Combinatorics": "\U0001F3B2", "Fibonacci & golden ratio": "\U0001F41A", "Text analyser": "\U0001F4DD",
              "Number theory": "\U0001F9E9", "Matrix lab": "\U0001F9F1", "Set lab": "\U0001F500", "Statistics lab": "\U0001F4CA",
              "Linear regression": "\U0001F4C8", "Area of a shape": "\U0001F4D0", "Report card & CGPA": "\U0001F4C4", "CGPA planner": "\U0001F3AF",
              "Loan EMI & prepayment": "\U0001F3E6", "SIP planner": "\U0001F331", "Payroll (stipend)": "\U0001F4BC",
              "Salary raise (nested dict)": "\U0001F4B9", "Wallet (bank demo)": "\U0001F45B", "Exception lab": "\U0001F9EA"}
TOOLS = [
    ("Converters", "Currency", [("Amount", "1000", "entry"), ("Direction", "INR to USD", "choice", ["INR to USD", "USD to INR"]),
                                ("Rate (Rs per USD)", str(USD_RATE), "entry")], currency, "Edit the rate to match today's market."),
    ("Converters", "Temperature", [("Value", "37", "entry"), ("From", "Celsius", "choice", ["Celsius", "Fahrenheit", "Kelvin"])], temperature, ""),
    ("Converters", "Length", [("Value", "5", "entry"), ("From", "inch", "choice", list(LENGTHS)), ("To", "centimetre", "choice", list(LENGTHS))], length, ""),
    ("Converters", "Inches to cm (list)", [("Inches (comma separated)", "5, 10, 15", "entry")], inches_to_cm, "Converts a whole list at once using map()."),
    ("Math & Data", "Prime explorer", [("Number (2 to 5,000,000)", "360360", "entry")], prime_explorer,
     "Sieve of Eratosthenes: prime test, factorisation, twin primes, largest gap and a density chart."),
    ("Math & Data", "Combinatorics", [("n", "20", "entry"), ("r", "5", "entry")], combinatorics,
     "Permutations, combinations, derangements, Catalan numbers and a Pascal's-triangle row chart."),
    ("Math & Data", "Fibonacci & golden ratio", [("Terms (2 to 300)", "60", "entry")], fibonacci_golden,
     "Generates the sequence with a while loop and plots how the ratio of neighbours converges to the golden ratio."),
    ("Math & Data", "Text analyser", [("Text", "A man, a plan, a canal: Panama. Never odd or even. Was it a car or a cat I saw?", "text")], text_analyser,
     "Palindrome test, longest palindromic substring, word statistics and a word-frequency chart."),
    ("Math & Data", "Number theory", [("Numbers (comma separated)", "28, 153, 97, 1729, 27, 360", "entry")], number_theory,
     "Digit sums with functools.reduce(), digital roots, perfect / Armstrong numbers, Collatz steps, GCD and LCM."),
    ("Math & Data", "Matrix lab", [("Matrix (one row per line)", "2 1 -1\n-3 -1 2\n-2 1 2", "text"), ("Operation", "Determinant", "choice", MATRIX_OPS)], matrix_lab,
     "NumPy linear algebra. For 'Solve Ax = b' add the right-hand side as the last column."),
    ("Math & Data", "Set lab", [("Set A", "1, 2, 3, 5, 8, 13", "entry"), ("Set B", "2, 3, 5, 7, 11, 13", "entry")], set_lab,
     "Union, intersection, differences, Jaccard similarity and subset tests with Python sets."),
    ("Math & Data", "Statistics lab", [("Data (comma separated)", "62, 71, 68, 75, 90, 55, 73, 66, 98, 70, 69, 64, 72, 31, 74", "entry")], statistics_lab,
     "Mean, median, mode, spread, quartiles, outliers (1.5 x IQR rule), skewness and a histogram."),
    ("Math & Data", "Linear regression", [("x values", "1, 2, 3, 4, 5, 6, 7, 8", "entry"), ("y values", "52, 55, 61, 64, 70, 74, 79, 85", "entry"),
                                          ("Predict y at x =", "10", "entry")], regression,
     "Least-squares line, R-squared, standard error and a prediction, with actual vs fitted chart."),
    ("Geometry", "Area of a shape", [("Shape", "Circle", "choice", ["Circle", "Rectangle", "Triangle"]),
                                      ("Radius / length / 3 sides", "5", "entry"), ("Width (rectangle)", "0", "entry")], area,
     "Triangle: type three sides like 3, 4, 5 (OOP: Polygon -> Triangle, Heron's formula)."),
    ("Academics", "Report card & CGPA", [("Student name", "", "entry"),
                                         ("Marks (Subject score/max [credits])", "Maths 78/100 4\nPhysics 65/100 3\nJava 88/100 4\nDBMS 72/100 3", "text")],
     report_card, "Press Save to store the report card as a text file."),
    ("Academics", "CGPA planner", [("Semesters (name SGPA credits)", "Sem1 7.8 22\nSem2 8.1 24\nSem3 7.6 24\nSem4 8.4 26", "text"),
                                   ("Target CGPA", "8.5", "entry"), ("Credits still to earn", "96", "entry")], cgpa_planner,
     "Shows the SGPA you must average in the remaining semesters to reach your target."),
    ("Money", "Loan EMI & prepayment", [("Loan amount (Rs)", "1500000", "entry"), ("Interest rate (% per year)", "9.5", "entry"),
                                        ("Years", "10", "entry"), ("Extra payment per month (Rs)", "5000", "entry")], loan_planner,
     "EMI formula plus a month-by-month amortisation, with and without extra payments."),
    ("Money", "SIP planner", [("Monthly SIP (Rs)", "5000", "entry"), ("Expected return (% per year)", "12", "entry"), ("Years", "15", "entry"),
                              ("Yearly step-up (%)", "10", "entry"), ("Inflation (% per year)", "6", "entry")], sip_planner,
     "Compound growth of a monthly investment with yearly step-ups, shown in today's money too."),
    ("Money", "Payroll (stipend)", [("Employee ID", "101", "entry"), ("Name", "Intern", "entry"), ("Basic salary", "30000", "entry")], payroll,
     "DA 80%, HRA 40%, PF 12% of basic, tax 5% if gross > 50,000."),
    ("Money", "Salary raise (nested dict)", [("Raise %", "10", "entry")], give_raise, "Three employees stored in a nested dictionary."),
    ("Money", "Wallet (bank demo)", [("Account number (10 digits)", "1234567890", "entry"), ("Holder", "Student", "entry"),
                                      ("Operation", "Deposit", "choice", ["Deposit", "Withdraw"]), ("Amount", "500", "entry")], wallet,
     "Custom exceptions for bad account numbers and insufficient funds; the log is an immutable tuple."),
    ("Money", "Exception lab", [], exception_lab, "Seven different errors, all handled with try / except / else / finally."),
]
NO_AUTORUN = {"Wallet (bank demo)"}


# ======================= GUI =======================
class ToolboxPage(ttk.Frame):
    def __init__(self, parent, ctx):
        super().__init__(parent)
        self.ctx = ctx
        self.vars, self.widgets, self.current, self.chart = [], [], None, None
        self.groups = list(dict.fromkeys(t[0] for t in TOOLS))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        bar = titled_card(self, "TOOLBOX", "Pick a category, then a tool", grid=dict(row=0, column=0, sticky="ew", padx=16, pady=(0, 10)))
        bar.columnconfigure(5, weight=1)
        self.v_group, self.v_tool = tk.StringVar(), tk.StringVar()
        ttk.Label(bar, text="Category", style="CardMuted.TLabel").grid(row=2, column=0, padx=(0, 6))
        self.group_box = ttk.Combobox(bar, textvariable=self.v_group, state="readonly", width=20,
                                      values=[f"{GROUP_ICONS.get(g, '')} {g}" for g in self.groups])
        self.group_box.grid(row=2, column=1, padx=(0, 16))
        self.group_box.bind("<<ComboboxSelected>>", lambda event: self.group_changed())
        ttk.Label(bar, text="Tool", style="CardMuted.TLabel").grid(row=2, column=2, padx=(0, 6))
        self.tool_box = ttk.Combobox(bar, textvariable=self.v_tool, state="readonly", width=34)
        self.tool_box.grid(row=2, column=3, padx=(0, 8))
        self.tool_box.bind("<<ComboboxSelected>>", lambda event: self.tool_changed())
        self.hint_icon = info_icon(bar, lambda: self.hint_text)
        self.hint_icon.grid(row=2, column=4)
        self.hint_text = ""
        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        self.panel = card(body)
        self.panel.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self.panel.columnconfigure(1, weight=1)
        self.result = card(body)
        self.result.grid(row=0, column=1, sticky="nsew")
        self.result.columnconfigure(0, weight=1)
        self.result.rowconfigure(2, weight=1)
        self.result.rowconfigure(3, weight=2)
        self.title = ttk.Label(self.result, text="", style="CardTitle.TLabel")
        self.title.grid(row=0, column=0, sticky="w")
        ttk.Label(self.result, text="RESULT", style="CardEyebrow.TLabel").grid(row=1, column=0, sticky="w")
        self.output = tk.Text(self.result, height=9, wrap="word", font=("Consolas", 10), bd=0, padx=8, pady=6)
        self.output.grid(row=2, column=0, sticky="nsew", pady=(4, 8))
        self.output.config(state="disabled")
        self.chart_box = ttk.Frame(self.result, style="Card.TFrame")
        self.chart_box.grid(row=3, column=0, sticky="nsew")
        self.chart_box.columnconfigure(0, weight=1)
        self.chart_box.rowconfigure(0, weight=1)
        ctx.theme.recolor(self.output)
        self.group_box.current(0)
        self.group_changed()

    # ---------- pickers ----------
    def tools_in_group(self):
        group = self.groups[self.group_box.current()] if self.group_box.current() >= 0 else self.groups[0]
        return [i for i, t in enumerate(TOOLS) if t[0] == group]

    def group_changed(self):
        self.indices = self.tools_in_group()
        self.tool_box.configure(values=[f"{TOOL_ICONS.get(TOOLS[i][1], '')} {TOOLS[i][1]}" for i in self.indices])
        self.tool_box.current(0)
        self.tool_changed()

    def tool_changed(self):
        self.build_panel(self.indices[max(self.tool_box.current(), 0)])

    def build_panel(self, index):
        group, name, fields, func, hint = TOOLS[index]
        for child in self.panel.winfo_children():
            child.destroy()
        self.current, self.vars, self.widgets, self.hint_text = index, [], [], hint
        ttk.Label(self.panel, text="INPUTS", style="CardEyebrow.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(self.panel, text=f"{TOOL_ICONS.get(name, '')} {name}", style="CardTitle.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.title.config(text=f"{TOOL_ICONS.get(name, '')} {name}")
        for row, (label, default, kind, *options) in enumerate(fields, start=2):
            ttk.Label(self.panel, text=label, style="CardMuted.TLabel", wraplength=230, justify="left").grid(row=row, column=0, sticky="nw", padx=(0, 12), pady=4)
            if kind == "choice":
                var = tk.StringVar(value=default)
                widget = ttk.Combobox(self.panel, textvariable=var, values=options[0], state="readonly", width=26)
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                self.vars.append(var.get)
            elif kind == "text":
                widget = tk.Text(self.panel, height=6, width=30, wrap="word", font=(self.ctx.theme.family, 10))
                widget.insert("1.0", default)
                self.ctx.theme.recolor(widget)
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                self.vars.append(lambda w=widget: w.get("1.0", "end"))
            else:
                var = tk.StringVar(value=default)
                widget = ttk.Entry(self.panel, textvariable=var, width=28)
                widget.grid(row=row, column=1, sticky="ew", pady=4)
                widget.bind("<Return>", lambda event: self.run())
                self.vars.append(var.get)
            self.widgets.append(widget)
        buttons = ttk.Frame(self.panel, style="Card.TFrame")
        buttons.grid(row=50, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(buttons, text="Calculate", style="Accent.TButton", command=self.run).pack(side="left")
        if name == "Report card & CGPA":
            ttk.Button(buttons, text="Save as file", command=self.save_output).pack(side="left", padx=8)
        self.show("Press Calculate" if name in NO_AUTORUN else "", None)
        if name not in NO_AUTORUN:
            self.run(quiet=True)

    # ---------- running ----------
    def show(self, text, chart):
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("1.0", text)
        self.output.config(state="disabled")
        if self.chart is not None:
            self.chart.destroy()
            self.chart = None
        if chart:
            spec = dict(chart)
            kind, height = spec.pop("kind"), spec.pop("height", 230)
            self.chart = make_chart(kind, self.chart_box, self.ctx.theme, height=height, **spec)
            self.chart.grid(row=0, column=0, sticky="nsew")

    def run(self, quiet=False):
        group, name, fields, func, hint = TOOLS[self.current]
        try:
            result = func(*(getter() for getter in self.vars))
        except (ValueError, KeyError, ArithmeticError, IndexError, WalletError) as err:
            if quiet:
                return
            return self.ctx.toast(str(err) or "Please check your input", "error")
        text, chart = result if isinstance(result, tuple) else (result, None)
        self.show(text, chart)

    def save_output(self):
        text = self.output.get("1.0", "end").strip()
        if not text:
            return self.ctx.toast("Calculate first", "warning")
        path = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="report_card.txt")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as err:
            self.ctx.toast(f"Could not save: {err}", "error")
        else:
            self.ctx.toast("Saved", "success")
