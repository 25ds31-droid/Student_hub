"""
Charts for Student Hub, drawn on a plain Tk Canvas (no matplotlib needed).

BarChart (grouped or stacked) | LineChart (multi-series, filled) | DonutChart | HBarChart (rankings / progress)
Gauge (semicircle score) | CalendarHeat (month grid)

Every chart follows the light / dark theme and shows a tooltip when you hover over a bar, dot or slice.
Use make_chart(kind, parent, theme, **spec) to build one from a small dictionary.
"""
import math
import tkinter as tk

from hub_theme import blend


def series_colors(theme):
    c = theme.colors
    return [c["primary"], c["success"], c["warning"], c["danger"], "#9b6bff", "#2bb3c0", "#e86ab0", "#8f9bb3"]


def nice_max(value):
    if value <= 0:
        return 1.0
    base = 10 ** math.floor(math.log10(value))
    for m in (1, 2, 2.5, 5, 10):
        if value <= m * base:
            return m * base
    return 10 * base


def short(value):
    """1234 -> 1.2k, 2500000 -> 2.5M"""
    a = abs(value)
    if a >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if a >= 10_000:
        return f"{value / 1000:.0f}k"
    if a >= 1000:
        return f"{value / 1000:.1f}k".replace(".0k", "k")
    return f"{value:g}" if a >= 10 or float(value).is_integer() else f"{value:.1f}"


class BaseChart(tk.Canvas):
    bg_key = "surface"

    def __init__(self, parent, theme, height=220):
        super().__init__(parent, height=height, highlightthickness=0, bd=0)
        self.theme, self.base_height = theme, height
        self.bind("<Configure>", lambda event: self.redraw())

    def redraw(self):
        self.delete("all")
        self.draw(max(self.winfo_width(), 320), max(self.winfo_height(), 150))

    def draw(self, w, h):                                            # overridden
        pass

    def empty(self, w, h, message="No data yet - add some entries"):
        self.create_text(w / 2, h / 2, text=message, fill=self.theme.colors["muted"], font=(self.theme.family, 10))

    # ---- hover tooltips drawn as canvas items (no extra windows) ----
    def hover(self, item, text):
        self.tag_bind(item, "<Enter>", lambda e, t=text: self._tip(e, t))
        self.tag_bind(item, "<Motion>", lambda e, t=text: self._tip(e, t))
        self.tag_bind(item, "<Leave>", lambda e: self.delete("tip"))

    def _tip(self, event, text):
        self.delete("tip")
        fam = self.theme.family
        label = self.create_text(event.x + 12, event.y - 12, text=text, anchor="sw", fill="#ffffff",
                                 font=(fam, 9), tags="tip")
        x0, y0, x1, y1 = self.bbox(label)
        shift = min(0, self.winfo_width() - 8 - (x1 + 6))
        if y0 - 4 < 0:
            self.move(label, 0, (4 - y0) + 24)
        self.move(label, shift, 0)
        x0, y0, x1, y1 = self.bbox(label)
        box = self.create_rectangle(x0 - 6, y0 - 4, x1 + 6, y1 + 4, fill="#101828", outline="", tags="tip")
        self.tag_raise(label, box)

    # ---- shared axis drawing ----
    def axes(self, w, h, top, pad_l, pad_r, pad_t, pad_b, steps=4):
        c, fam = self.theme.colors, self.theme.family
        for i in range(steps + 1):
            y = pad_t + (h - pad_t - pad_b) * i / steps
            self.create_line(pad_l, y, w - pad_r, y, fill=c["border"])
            self.create_text(pad_l - 6, y, text=short(top * (steps - i) / steps), anchor="e", fill=c["muted"],
                             font=(fam, 8))

    def legend(self, names, colors, x=14, y=10):
        c, fam = self.theme.colors, self.theme.family
        for name, colour in zip(names, colors):
            self.create_rectangle(x, y - 4, x + 9, y + 5, fill=colour, outline="")
            t = self.create_text(x + 14, y, text=name, anchor="w", fill=c["muted"], font=(fam, 8))
            x = self.bbox(t)[2] + 14


# ============================================================================ bar chart
class BarChart(BaseChart):
    def __init__(self, parent, theme, height=220):
        super().__init__(parent, theme, height)
        self.labels, self.series, self.stacked, self.goal, self.fmt, self.goal_label = [], [], False, None, "{:,.0f}", ""

    def set(self, labels, series, stacked=False, goal=None, fmt="{:,.0f}", goal_label=""):
        """series = [(name, [values]), ...]  (a bare list of numbers is accepted for one series)"""
        if series and not isinstance(series[0], (tuple, list)):
            series = [("", list(series))]
        self.labels, self.series, self.stacked, self.goal, self.fmt, self.goal_label = (
            list(labels), [(s[0], [v or 0 for v in s[1]]) for s in series], stacked, goal, fmt, goal_label)
        self.redraw()

    def draw(self, w, h):
        c, fam, cols = self.theme.colors, self.theme.family, series_colors(self.theme)
        n = len(self.labels)
        if not n or not self.series:
            return self.empty(w, h)
        legend = len(self.series) > 1
        pad_l, pad_r, pad_t, pad_b = 44, 14, 30 if legend else 16, 28
        if self.stacked:
            top = max(sum(s[1][i] for s in self.series) for i in range(n))
        else:
            top = max(max(s[1]) for s in self.series if s[1])
        top = nice_max(max(top, self.goal or 0, 1e-9) * 1.05)
        self.axes(w, h, top, pad_l, pad_r, pad_t, pad_b)
        plot_h, slot = h - pad_t - pad_b, (w - pad_l - pad_r) / n
        group = slot * 0.7
        k = len(self.series)
        step = max(1, math.ceil(n / max(1, (w - pad_l) // 46)))
        for i, label in enumerate(self.labels):
            x_left = pad_l + i * slot + (slot - group) / 2
            base = 0.0
            for j, (name, values) in enumerate(self.series):
                v = values[i] or 0
                if self.stacked:
                    y1, y0 = h - pad_b - plot_h * base / top, h - pad_b - plot_h * (base + v) / top
                    xa, xb = x_left, x_left + group
                    base += v
                else:
                    bw = group / k
                    y1, y0 = h - pad_b, h - pad_b - plot_h * v / top
                    xa, xb = x_left + j * bw, x_left + (j + 1) * bw - 1
                if v > 0:
                    bar = self.create_rectangle(xa, y0, xb, y1, fill=cols[j % len(cols)], outline="")
                    self.hover(bar, f"{label}  {name + ': ' if name else ''}{self.fmt.format(v)}")
                if k == 1 and v > 0 and group > 26 and not self.stacked:
                    self.create_text((xa + xb) / 2, y0 - 8, text=short(v), fill=c["text"], font=(fam, 8))
            if i % step == 0:
                self.create_text(pad_l + i * slot + slot / 2, h - pad_b + 13, text=label, fill=c["muted"], font=(fam, 8))
        if self.goal:
            y = h - pad_b - plot_h * self.goal / top
            self.create_line(pad_l, y, w - pad_r, y, fill=c["warning"], dash=(5, 3), width=2)
            if self.goal_label:
                self.create_text(w - pad_r, y - 8, text=self.goal_label, anchor="e", fill=c["warning"], font=(fam, 8, "bold"))
        if legend:
            self.legend([s[0] for s in self.series], cols)


# ============================================================================ line chart
class LineChart(BaseChart):
    def __init__(self, parent, theme, height=220):
        super().__init__(parent, theme, height)
        self.labels, self.series, self.fmt, self.fill, self.limit, self.limit_label = [], [], "{:,.0f}", False, None, ""

    def set(self, labels, series, fmt="{:,.0f}", fill=False, limit=None, limit_label=""):
        if series and not isinstance(series[0], (tuple, list)):
            series = [("", list(series))]
        self.labels, self.series, self.fmt, self.fill, self.limit, self.limit_label = (
            list(labels), [(s[0], list(s[1])) for s in series], fmt, fill, limit, limit_label)
        self.redraw()

    def draw(self, w, h):
        c, fam, cols = self.theme.colors, self.theme.family, series_colors(self.theme)
        n = len(self.labels)
        if n < 1 or not self.series:
            return self.empty(w, h)
        legend = len(self.series) > 1
        pad_l, pad_r, pad_t, pad_b = 44, 18, 30 if legend else 16, 28
        top = max((v for s in self.series for v in s[1] if v is not None), default=0)
        top = nice_max(max(top, self.limit or 0, 1e-9) * 1.05)
        self.axes(w, h, top, pad_l, pad_r, pad_t, pad_b)
        plot_h = h - pad_t - pad_b
        span = max(n - 1, 1)
        xs = [pad_l + (w - pad_l - pad_r) * (i / span if n > 1 else 0.5) for i in range(n)]
        step = max(1, math.ceil(n / max(1, (w - pad_l) // 46)))
        for i, label in enumerate(self.labels):
            if i % step == 0:
                self.create_text(xs[i], h - pad_b + 13, text=label, fill=c["muted"], font=(fam, 8))
        for j, (name, values) in enumerate(self.series):
            colour = cols[j % len(cols)]
            pts = [(xs[i], h - pad_b - plot_h * v / top, i, v) for i, v in enumerate(values) if v is not None]
            if self.fill and j == 0 and len(pts) > 1:
                poly = [pts[0][0], h - pad_b] + [q for p in pts for q in p[:2]] + [pts[-1][0], h - pad_b]
                self.create_polygon(*poly, fill=blend(c["surface"], colour, 0.18), outline="")
            if len(pts) > 1:
                self.create_line(*[q for p in pts for q in p[:2]], fill=colour, width=2, smooth=False)
            for x, y, i, v in pts:
                if n <= 40 or i == len(values) - 1:
                    dot = self.create_oval(x - 3.5, y - 3.5, x + 3.5, y + 3.5, fill=colour, outline=c["surface"], width=1)
                    self.hover(dot, f"{self.labels[i]}  {name + ': ' if name else ''}{self.fmt.format(v)}")
        if self.limit:
            y = h - pad_b - plot_h * self.limit / top
            self.create_line(pad_l, y, w - pad_r, y, fill=c["danger"], dash=(5, 3), width=2)
            if self.limit_label:
                self.create_text(w - pad_r, y - 8, text=self.limit_label, anchor="e", fill=c["danger"], font=(fam, 8, "bold"))
        if legend:
            self.legend([s[0] for s in self.series], cols)


# ============================================================================ donut chart
class DonutChart(BaseChart):
    def __init__(self, parent, theme, height=220):
        super().__init__(parent, theme, height)
        self.items, self.center, self.sub, self.fmt = [], "", "", "{:,.0f}"

    def set(self, items, center="", sub="", fmt="{:,.0f}"):
        items = sorted(((l, float(v)) for l, v in items if v and float(v) > 0), key=lambda p: -p[1])
        if len(items) > 8:
            items = items[:7] + [("Other", sum(v for _, v in items[7:]))]
        self.items, self.center, self.sub, self.fmt = items, center, sub, fmt
        self.redraw()

    def draw(self, w, h):
        c, fam, cols = self.theme.colors, self.theme.family, series_colors(self.theme)
        total = sum(v for _, v in self.items)
        if not total:
            return self.empty(w, h)
        d = min(h - 20, w * 0.46)
        cx, cy, thick = 16 + d / 2, h / 2, max(14, d * 0.17)
        box = (cx - d / 2 + thick / 2, cy - d / 2 + thick / 2, cx + d / 2 - thick / 2, cy + d / 2 - thick / 2)
        acc = 0.0
        for i, (label, v) in enumerate(self.items):
            extent = min(v / total * 360, 359.99)
            arc = self.create_arc(*box, start=90 - (acc + extent), extent=extent, style="arc", width=thick,
                                  outline=cols[i % len(cols)])
            self.hover(arc, f"{label}: {self.fmt.format(v)}  ({v / total:.0%})")
            acc += v / total * 360
        self.create_text(cx, cy - (8 if self.sub else 0), text=self.center, fill=c["text"], font=(fam, 15, "bold"))
        if self.sub:
            self.create_text(cx, cy + 14, text=self.sub, fill=c["muted"], font=(fam, 8))
        x, row = cx + d / 2 + 24, min(24, (h - 20) / max(len(self.items), 1))
        y = h / 2 - row * len(self.items) / 2 + row / 2
        for i, (label, v) in enumerate(self.items):
            self.create_rectangle(x, y - 5, x + 10, y + 5, fill=cols[i % len(cols)], outline="")
            self.create_text(x + 16, y, text=f"{label}", anchor="w", fill=c["text"], font=(fam, 9))
            self.create_text(w - 12, y, text=f"{v / total:.0%}", anchor="e", fill=c["muted"], font=(fam, 9))
            y += row


# ============================================================================ horizontal bars
class HBarChart(BaseChart):
    def __init__(self, parent, theme, height=200):
        super().__init__(parent, theme, height)
        self.items, self.fmt, self.max_value = [], "{:,.0f}", None

    def set(self, items, fmt="{:,.0f}", max_value=None):
        """items = [(label, value[, colour[, hover note]]), ...]"""
        self.items, self.fmt, self.max_value = list(items), fmt, max_value
        self.configure(height=max(self.base_height, 30 * len(self.items) + 16))
        self.redraw()

    def draw(self, w, h):
        c, fam, cols = self.theme.colors, self.theme.family, series_colors(self.theme)
        if not self.items:
            return self.empty(w, h)
        label_w = min(170, max(70, max(len(str(i[0])) for i in self.items) * 7))
        top = self.max_value or max(max(i[1] for i in self.items), 1e-9)
        row = min(34, (h - 12) / len(self.items))
        x0, x1 = label_w + 10, w - 70
        for k, item in enumerate(self.items):
            label, v = item[0], item[1]
            colour = item[2] if len(item) > 2 and item[2] else cols[0]
            note = item[3] if len(item) > 3 and item[3] else f"{label}: {self.fmt.format(v)}"
            y = 8 + k * row + row / 2
            self.create_text(label_w, y, text=str(label), anchor="e", fill=c["text"], font=(fam, 9))
            self.create_rectangle(x0, y - 7, x1, y + 7, fill=c["surface2"], outline="")
            width = (x1 - x0) * max(0.0, min(v / top, 1.0))
            if width > 0:
                bar = self.create_rectangle(x0, y - 7, x0 + width, y + 7, fill=colour, outline="")
                self.hover(bar, note)
            self.create_text(x1 + 8, y, text=self.fmt.format(v), anchor="w", fill=c["muted"], font=(fam, 9))


# ============================================================================ gauge
class Gauge(BaseChart):
    def __init__(self, parent, theme, height=170):
        super().__init__(parent, theme, height)
        self.value, self.label, self.caption = 0.0, "", ""

    def set(self, value, label="", caption=""):
        self.value, self.label, self.caption = max(0.0, min(100.0, float(value))), label, caption
        self.redraw()

    def draw(self, w, h):
        c, fam = self.theme.colors, self.theme.family
        r = min(w / 2 - 20, h - 40)
        cx, cy = w / 2, h - 34
        box = (cx - r, cy - r, cx + r, cy + r)
        thick = max(12, r * 0.2)
        inner = (box[0] + thick / 2, box[1] + thick / 2, box[2] - thick / 2, box[3] - thick / 2)
        self.create_arc(*inner, start=0, extent=180, style="arc", width=thick, outline=c["surface2"])
        colour = c["danger"] if self.value < 40 else c["warning"] if self.value < 70 else c["success"]
        if self.value > 0:
            arc = self.create_arc(*inner, start=180, extent=-max(self.value * 1.8, 1), style="arc", width=thick, outline=colour)
            self.hover(arc, f"{self.label or 'Score'}: {self.value:.0f}%")
        self.create_text(cx, cy - r * 0.32, text=f"{self.value:.0f}%", fill=c["text"], font=(fam, 20, "bold"))
        self.create_text(cx, cy + 12, text=self.label, fill=c["text"], font=(fam, 10, "bold"))
        if self.caption:
            self.create_text(cx, cy + 28, text=self.caption, fill=c["muted"], font=(fam, 8))


# ============================================================================ calendar heat-map
class CalendarHeat(BaseChart):
    def __init__(self, parent, theme, height=260):
        super().__init__(parent, theme, height)
        self.year = self.month = None
        self.data = {}

    def set(self, year, month, data):
        """data = {day: (intensity 0..1, tooltip text[, ring colour])}"""
        self.year, self.month, self.data = year, month, data
        self.redraw()

    def draw(self, w, h):
        import calendar
        c, fam = self.theme.colors, self.theme.family
        if not self.year:
            return self.empty(w, h, "Pick a month")
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        cell = min((w - 16) / 7, (h - 34) / max(len(weeks), 1))
        x0 = (w - cell * 7) / 2
        for i, name in enumerate("MTWTFSS"):
            self.create_text(x0 + cell * i + cell / 2, 12, text=name, fill=c["muted"], font=(fam, 8, "bold"))
        for r, week in enumerate(weeks):
            for i, day in enumerate(week):
                if not day:
                    continue
                entry = self.data.get(day, (0, "", None))
                value, tip = entry[0], entry[1]
                ring = entry[2] if len(entry) > 2 else None
                xa, ya = x0 + cell * i + 2, 26 + r * cell + 2
                fill = blend(c["surface2"], c["primary"], value) if value else c["surface2"]
                rect = self.create_rectangle(xa, ya, xa + cell - 4, ya + cell - 4, fill=fill,
                                             outline=ring or c["border"], width=3 if ring else 1)
                self.create_text(xa + 6, ya + 6, text=str(day), anchor="nw", fill="#ffffff" if value > 0.55 else c["text"],
                                 font=(fam, 8, "bold"))
                if tip:
                    self.hover(rect, tip)


KINDS = {"bar": BarChart, "line": LineChart, "donut": DonutChart, "hbar": HBarChart, "gauge": Gauge}


def make_chart(kind, parent, theme, height=220, **spec):
    """make_chart('line', frame, theme, labels=[...], series=[('Sales', [1, 2, 3])])"""
    chart = KINDS[kind](parent, theme, height=height)
    chart.set(**spec)
    return chart
