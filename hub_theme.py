"""
Theme manager and small UI helpers shared by every page of Student Hub.

* Two palettes (light / dark) applied to ttk through one Style object
* recolour() walks the widget tree so plain tk widgets (Text, Listbox, Canvas ...) follow the theme
* Toast notifications, cards, tables and a themed bar chart
"""
import json
import os
import tkinter as tk
from tkinter import ttk, font as tkfont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "hub_settings.json")

PALETTES = {
    "light": dict(bg="#f1f5fa", surface="#ffffff", surface2="#e9eef6", input="#ffffff", text="#0f1b33",
                  muted="#5b6a84", primary="#0f5cad", primary_hover="#0b4a8c", on_primary="#ffffff",
                  border="#d6deea", success="#16895a", warning="#c77a0a", danger="#cf3a3a",
                  sidebar="#0a2347", sidebar_hover="#12336a", sidebar_active="#1a4a93", sidebar_text="#c3d0ea",
                  hero="#0f4c89", topbar="#ffffff",
                  ok_bg="#ddf5e8", ok_fg="#14804f", warn_bg="#fdeed7", warn_fg="#b45309",
                  bad_bg="#fde2e2", bad_fg="#b91c1c", info_bg="#dbeafe", info_fg="#1d4ed8"),
    "dark": dict(bg="#0a1226", surface="#101a33", surface2="#172445", input="#0c1630", text="#e8eefb",
                 muted="#8b9ab9", primary="#3b8cf0", primary_hover="#5aa0f5", on_primary="#ffffff",
                 border="#233256", success="#34c58a", warning="#f0a93a", danger="#f26b6b",
                 sidebar="#071022", sidebar_hover="#0f1d3d", sidebar_active="#17407f", sidebar_text="#a9b8d8",
                 hero="#10407a", topbar="#0d1730",
                 ok_bg="#12392b", ok_fg="#4ade9a", warn_bg="#3d2c12", warn_fg="#f5b25a",
                 bad_bg="#432020", bad_fg="#fb8a8a", info_bg="#16325c", info_fg="#7db4ff"),
}

UI_FONT = "Segoe UI"                               # updated by Theme.apply to a font that exists


class Theme:
    def __init__(self):
        self.name = self._load()
        self.family = "Helvetica"

    @property
    def colors(self):
        return PALETTES[self.name]

    def _load(self):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as fh:
                value = json.load(fh).get("theme", "light")
        except (OSError, ValueError, AttributeError):
            return "light"
        return value if value in PALETTES else "light"

    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
                json.dump({"theme": self.name}, fh)
        except OSError:
            pass                                       # a settings file must never crash the app

    def toggle(self, root):
        self.name = "dark" if self.name == "light" else "light"
        self.apply(root)
        self.save()

    # ------------------------------------------------------------------ ttk styles
    def apply(self, root):
        c = self.colors
        families = set(tkfont.families(root))
        self.family = next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans",
                                        "DejaVu Sans", "Arial") if f in families), "Helvetica")
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(name).configure(family=self.family, size=10)
        global UI_FONT
        UI_FONT = self.family
        fam = self.family
        style = ttk.Style(root)
        style.theme_use("clam")
        root.configure(bg=c["bg"])
        root.option_add("*TCombobox*Listbox.background", c["input"])
        root.option_add("*TCombobox*Listbox.foreground", c["text"])
        root.option_add("*TCombobox*Listbox.selectBackground", c["primary"])
        root.option_add("*TCombobox*Listbox.selectForeground", c["on_primary"])

        style.configure(".", background=c["bg"], foreground=c["text"], fieldbackground=c["input"],
                        bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                        troughcolor=c["surface2"], focuscolor=c["primary"], font=(fam, 10))
        # frames and labels
        style.configure("TFrame", background=c["bg"])
        style.configure("Card.TFrame", background=c["surface"], relief="solid", borderwidth=1, bordercolor=c["border"])
        style.configure("Sidebar.TFrame", background=c["sidebar"])
        style.configure("TLabel", background=c["bg"], foreground=c["text"])
        style.configure("Muted.TLabel", foreground=c["muted"])
        style.configure("Title.TLabel", font=(fam, 20, "bold"))
        style.configure("Heading.TLabel", font=(fam, 12, "bold"))
        style.configure("Card.TLabel", background=c["surface"])
        style.configure("CardMuted.TLabel", background=c["surface"], foreground=c["muted"])
        style.configure("CardTitle.TLabel", background=c["surface"], font=(fam, 12, "bold"))
        style.configure("Stat.TLabel", background=c["surface"], font=(fam, 24, "bold"))
        style.configure("CardError.TLabel", background=c["surface"], foreground=c["danger"])
        style.configure("CardOk.TLabel", background=c["surface"], foreground=c["success"])
        style.configure("Sidebar.TLabel", background=c["sidebar"], foreground=c["sidebar_text"])
        style.configure("SidebarTitle.TLabel", background=c["sidebar"], foreground="#ffffff", font=(fam, 18, "bold"))
        # buttons
        style.configure("TButton", background=c["surface2"], foreground=c["text"], padding=(12, 6),
                        borderwidth=1, relief="flat", bordercolor=c["border"])
        style.map("TButton", background=[("active", c["border"]), ("disabled", c["surface2"])],
                  foreground=[("disabled", c["muted"])])
        style.configure("Accent.TButton", background=c["primary"], foreground=c["on_primary"], bordercolor=c["primary"])
        style.map("Accent.TButton", background=[("active", c["primary_hover"]), ("disabled", c["surface2"])])
        style.configure("Danger.TButton", background=c["danger"], foreground="#ffffff", bordercolor=c["danger"])
        style.map("Danger.TButton", background=[("active", c["danger"])])
        style.configure("Nav.TButton", background=c["sidebar"], foreground=c["sidebar_text"], anchor="w",
                        padding=(18, 10), borderwidth=0, bordercolor=c["sidebar"], font=(fam, 10))
        style.map("Nav.TButton", background=[("active", c["sidebar_hover"])], foreground=[("active", "#ffffff")])
        style.configure("NavActive.TButton", background=c["sidebar_active"], foreground=c["on_primary"], anchor="w",
                        padding=(18, 10), borderwidth=0, bordercolor=c["sidebar_active"], font=(fam, 10, "bold"))
        style.map("NavActive.TButton", background=[("active", c["sidebar_active"])])
        # inputs
        style.configure("TEntry", padding=6, fieldbackground=c["input"], foreground=c["text"], insertcolor=c["text"])
        style.map("TEntry", bordercolor=[("focus", c["primary"])])
        style.configure("TSpinbox", padding=5, fieldbackground=c["input"], foreground=c["text"],
                        arrowcolor=c["muted"], background=c["surface2"], insertcolor=c["text"])
        style.configure("TCombobox", padding=5, arrowcolor=c["muted"], background=c["surface2"],
                        foreground=c["text"], fieldbackground=c["input"])
        style.map("TCombobox", fieldbackground=[("readonly", c["input"])], foreground=[("readonly", c["text"])],
                  selectbackground=[("readonly", c["input"])], selectforeground=[("readonly", c["text"])])
        for prefix, bg in (("", c["bg"]), ("Card.", c["surface"])):
            style.configure(prefix + "TCheckbutton", background=bg, foreground=c["text"], indicatorcolor=c["input"])
            style.map(prefix + "TCheckbutton", indicatorcolor=[("selected", c["primary"])], background=[("active", bg)])
            style.configure(prefix + "TRadiobutton", background=bg, foreground=c["text"], indicatorcolor=c["input"])
            style.map(prefix + "TRadiobutton", indicatorcolor=[("selected", c["primary"])], background=[("active", bg)])
        # containers and lists
        style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=(0, 4, 0, 0))
        style.configure("TNotebook.Tab", background=c["surface2"], foreground=c["muted"], padding=(16, 8), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", c["surface"])], foreground=[("selected", c["primary"])])
        style.configure("TLabelframe", background=c["bg"], bordercolor=c["border"])
        style.configure("TLabelframe.Label", background=c["bg"], foreground=c["muted"])
        style.configure("Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["text"],
                        rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=c["surface2"], foreground=c["text"], relief="flat",
                        font=(fam, 10, "bold"), padding=(8, 6))
        style.map("Treeview", background=[("selected", c["primary"])], foreground=[("selected", c["on_primary"])])
        style.map("Treeview.Heading", background=[("active", c["border"])])
        # Tk 8.6.9 ignores row tags unless these two options are filtered (known bug)
        def fixed(option):
            return [e for e in style.map("Treeview", query_opt=option) if e[:2] != ("!disabled", "!selected")]
        style.map("Treeview", foreground=fixed("foreground"), background=fixed("background"))
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar", background=c["surface2"], troughcolor=c["bg"],
                            bordercolor=c["bg"], arrowcolor=c["muted"])
        style.configure("Horizontal.TProgressbar", troughcolor=c["surface2"], background=c["primary"],
                        bordercolor=c["surface2"], lightcolor=c["primary"], darkcolor=c["primary"])
        style.configure("Success.Horizontal.TProgressbar", troughcolor=c["surface2"], background=c["success"],
                        bordercolor=c["surface2"], lightcolor=c["success"], darkcolor=c["success"])
        style.configure("TSeparator", background=c["border"])
        # TourismFlowX-style extras: eyebrow captions, top bar, hero banner, link buttons
        style.configure("Eyebrow.TLabel", foreground=c["primary"], font=(fam, 8, "bold"))
        style.configure("CardEyebrow.TLabel", background=c["surface"], foreground=c["primary"], font=(fam, 8, "bold"))
        style.configure("Topbar.TFrame", background=c["topbar"])
        style.configure("Topbar.TLabel", background=c["topbar"])
        style.configure("TopbarTitle.TLabel", background=c["topbar"], font=(fam, 18, "bold"))
        style.configure("TopbarMuted.TLabel", background=c["topbar"], foreground=c["muted"])
        style.configure("Hero.TFrame", background=c["hero"])
        style.configure("Hero.TLabel", background=c["hero"], foreground="#e3eeff")
        style.configure("HeroEyebrow.TLabel", background=c["hero"], foreground="#9cc4f5", font=(fam, 8, "bold"))
        style.configure("HeroValue.TLabel", background=c["hero"], foreground="#ffffff", font=(fam, 15, "bold"))
        style.configure("HeroMuted.TLabel", background=c["hero"], foreground="#bcd3f0")
        style.configure("StatPrimary.TLabel", background=c["surface"], foreground=c["primary"], font=(fam, 24, "bold"))
        style.configure("CardLink.TButton", background=c["surface"], foreground=c["primary"], borderwidth=0,
                        padding=(0, 2), font=(fam, 10, "bold"))
        style.map("CardLink.TButton", background=[("active", c["surface"])], foreground=[("active", c["primary_hover"])])
        self.recolor(root)
        self._matplotlib()

    # ------------------------------------------------------------------ plain tk widgets
    def recolor(self, widget):
        c = self.colors
        if isinstance(widget, (tk.Tk, tk.Toplevel, tk.Frame)):
            widget.configure(bg=c["bg"])
        elif isinstance(widget, tk.Label) and hasattr(widget, "badge_kind"):
            widget.configure(bg=c[widget.badge_kind + "_bg"], fg=c[widget.badge_kind + "_fg"])
        elif isinstance(widget, (tk.Text, tk.Listbox)):
            widget.configure(bg=c["input"], fg=c["text"], insertbackground=c["text"],
                             selectbackground=c["primary"], selectforeground=c["on_primary"],
                             highlightbackground=c["border"], highlightcolor=c["primary"],
                             highlightthickness=1, relief="flat", borderwidth=0)
        elif isinstance(widget, tk.Canvas):
            widget.configure(bg=c[getattr(widget, "bg_key", "surface")], highlightthickness=0)
            if hasattr(widget, "redraw"):
                widget.redraw()
        elif isinstance(widget, ttk.Treeview):
            widget.tag_configure("odd", background=c["surface"])
            widget.tag_configure("even", background=c["surface2"])
            widget.tag_configure("danger", foreground=c["danger"])
            widget.tag_configure("warning", foreground=c["warning"])
            widget.tag_configure("success", foreground=c["success"])
            widget.tag_configure("done", foreground=c["muted"])
        for child in widget.winfo_children():
            self.recolor(child)

    def _matplotlib(self):
        """Charts created after a theme change use the new colours."""
        try:
            import matplotlib
            from cycler import cycler
        except ImportError:
            return
        c = self.colors
        matplotlib.rcParams.update({
            "figure.facecolor": c["surface"], "axes.facecolor": c["surface"], "savefig.facecolor": c["surface"],
            "axes.edgecolor": c["border"], "axes.labelcolor": c["text"], "text.color": c["text"],
            "xtick.color": c["muted"], "ytick.color": c["muted"], "grid.color": c["border"],
            "legend.facecolor": c["surface"], "legend.edgecolor": c["border"],
            "axes.prop_cycle": cycler(color=[c["primary"], c["success"], c["warning"], c["danger"],
                                             "#9b6bff", "#2bb3c0", "#e86ab0", "#8f9bb3"]),
        })


# ====================================================================== helpers
def card(parent, padding=14, **kw):
    return ttk.Frame(parent, style="Card.TFrame", padding=padding, **kw)


def add_field(parent, row, label, widget, col=0, label_style="CardMuted.TLabel"):
    ttk.Label(parent, text=label, style=label_style).grid(row=row, column=col, sticky="w", padx=(0, 10), pady=4)
    widget.grid(row=row, column=col + 1, sticky="ew", pady=4)
    return widget


def make_table(parent, columns, height=10, selectmode="browse"):
    """columns = [(key, heading, width, anchor)] -> (frame, tree). Pack/grid the frame yourself."""
    frame = ttk.Frame(parent)
    tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", height=height, selectmode=selectmode)
    for key, heading, width, anchor in columns:
        tree.heading(key, text=heading)
        tree.column(key, width=width, anchor=anchor, stretch=True)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    return frame, tree


def insert_row(tree, values, tag=None, iid=None):
    """Insert with alternating row colours (and an optional status tag)."""
    n = len(tree.get_children())
    tags = ("odd" if n % 2 else "even",) + ((tag,) if tag else ())
    return tree.insert("", "end", values=values, tags=tags, iid=iid)


def clear_table(tree):
    tree.delete(*tree.get_children())


class ChartCanvas(tk.Canvas):
    """Small themed bar chart drawn on a Canvas (redraws itself on resize and on theme change)."""
    bg_key = "surface"

    def __init__(self, parent, theme, height=190):
        super().__init__(parent, height=height, highlightthickness=0, bd=0)
        self.theme, self.labels, self.values, self.goal = theme, [], [], None
        self.bind("<Configure>", lambda event: self.redraw())

    def set(self, labels, values, goal=None):
        self.labels, self.values, self.goal = list(labels), list(values), goal
        self.redraw()

    def redraw(self):
        c, fam = self.theme.colors, self.theme.family
        self.delete("all")
        w, h = max(self.winfo_width(), 320), max(self.winfo_height(), 150)
        pad_l, pad_r, pad_t, pad_b = 36, 12, 16, 26
        top = max(max(self.values or [0]), self.goal or 0, 1) * 1.15
        n = max(len(self.values), 1)
        slot = (w - pad_l - pad_r) / n
        bar_w = slot * 0.55
        plot_h = h - pad_t - pad_b
        for i in range(4):
            y = pad_t + plot_h * i / 3
            self.create_line(pad_l, y, w - pad_r, y, fill=c["border"])
            self.create_text(pad_l - 6, y, text=f"{top * (3 - i) / 3:.0f}", anchor="e", fill=c["muted"], font=(fam, 8))
        for i, (label, value) in enumerate(zip(self.labels, self.values)):
            x0 = pad_l + i * slot + (slot - bar_w) / 2
            y1 = h - pad_b
            y0 = y1 - plot_h * value / top
            colour = c["success"] if self.goal and value >= self.goal else c["primary"]
            if value:
                self.create_rectangle(x0, y0, x0 + bar_w, y1, fill=colour, outline="")
                self.create_text(x0 + bar_w / 2, y0 - 8, text=f"{value:.1f}", fill=c["text"], font=(fam, 8))
            self.create_text(x0 + bar_w / 2, y1 + 12, text=label, fill=c["muted"], font=(fam, 8))
        if self.goal:
            y = h - pad_b - plot_h * self.goal / top
            self.create_line(pad_l, y, w - pad_r, y, fill=c["warning"], dash=(5, 3), width=2)


class Toast:
    """Non-blocking pop-up message in the bottom-right corner."""

    def __init__(self, root, theme):
        self.root, self.theme, self.label, self.job = root, theme, None, None

    def show(self, message, kind="info", ms=2800):
        c = self.theme.colors
        colour = {"info": c["primary"], "success": c["success"], "error": c["danger"], "warning": c["warning"]}[kind]
        if self.label is not None:
            self.label.destroy()
        if self.job is not None:
            self.root.after_cancel(self.job)
        self.label = tk.Label(self.root, text=message, bg=colour, fg="#ffffff", padx=18, pady=10,
                              font=(self.theme.family, 10, "bold"), wraplength=420, justify="left")
        self.label.place(relx=0.985, rely=0.975, anchor="se")
        self.label.lift()
        self.job = self.root.after(ms, self.hide)

    def hide(self):
        if self.label is not None:
            self.label.destroy()
            self.label = None


# ====================================================================== tooltips, badges, pickers
def blend(c1, c2, t):
    """Mix two #rrggbb colours: t=0 gives c1, t=1 gives c2."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * max(0.0, min(1.0, t))) for x, y in zip(a, b))


class Tooltip:
    """Small pop-up that appears when the mouse rests on a widget. `text` may be a function."""

    def __init__(self, widget, text, delay=300):
        self.widget, self.text, self.delay = widget, text, delay
        self.tip = self.job = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._leave, add="+")
        widget.bind("<ButtonPress>", self._leave, add="+")

    def _enter(self, _event=None):
        self._cancel()
        self.job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self.job is not None:
            self.widget.after_cancel(self.job)
            self.job = None

    def _show(self):
        text = self.text() if callable(self.text) else self.text
        if not text:
            return
        self._hide()
        x, y = self.widget.winfo_pointerx() + 14, self.widget.winfo_pointery() + 18
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=text, bg="#101828", fg="#ffffff", justify="left", padx=10, pady=6,
                 wraplength=340, font=(UI_FONT, 9), bd=0).pack()

    def _hide(self):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None

    def _leave(self, _event=None):
        self._cancel()
        self._hide()


def info_icon(parent, text, style="CardMuted.TLabel"):
    """A small (i) symbol; the explanation or example appears when you hover over it."""
    label = ttk.Label(parent, text="\u24d8", style=style, cursor="question_arrow")
    Tooltip(label, text)
    return label


def badge(parent, theme, text, kind="info"):
    """Coloured pill. kind: ok | warn | bad | info."""
    c = theme.colors
    label = tk.Label(parent, text=text, bg=c[kind + "_bg"], fg=c[kind + "_fg"], padx=9, pady=2,
                     font=(theme.family, 8, "bold"))
    label.badge_kind = kind
    return label


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class DatePicker(ttk.Frame):
    """Day / month / year drop-downs instead of typing a date."""

    def __init__(self, parent, value=None, years_back=1, years_ahead=4, style="Card.TFrame", command=None):
        super().__init__(parent, style=style)
        import datetime as _dt
        today = _dt.date.today()
        value = self._coerce(value) or today
        self.d = tk.StringVar(value=f"{value.day:02d}")
        self.m = tk.StringVar(value=MONTHS[value.month - 1])
        self.y = tk.StringVar(value=str(value.year))
        years = [str(y) for y in range(today.year - years_back, today.year + years_ahead + 1)]
        boxes = [(self.d, [f"{i:02d}" for i in range(1, 32)], 4), (self.m, MONTHS, 5), (self.y, years, 6)]
        for var, values, width in boxes:
            box = ttk.Combobox(self, textvariable=var, values=values, width=width, state="readonly")
            box.pack(side="left", padx=(0, 4))
            if command:
                box.bind("<<ComboboxSelected>>", lambda event: command())

    @staticmethod
    def _coerce(value):
        import datetime as _dt
        if isinstance(value, _dt.datetime):
            return value.date()
        if isinstance(value, _dt.date):
            return value
        if isinstance(value, str) and value:
            try:
                return _dt.date.fromisoformat(value)
            except ValueError:
                return None
        return None

    def get(self):
        import calendar
        import datetime as _dt
        y, m = int(self.y.get()), MONTHS.index(self.m.get()) + 1
        return _dt.date(y, m, min(int(self.d.get()), calendar.monthrange(y, m)[1]))

    def iso(self):
        return self.get().isoformat()

    def set(self, value):
        value = self._coerce(value)
        if value:
            self.d.set(f"{value.day:02d}")
            self.m.set(MONTHS[value.month - 1])
            self.y.set(str(value.year))


class TimePicker(ttk.Frame):
    """Hour / minute drop-downs."""

    def __init__(self, parent, value="09:00", style="Card.TFrame"):
        super().__init__(parent, style=style)
        hh, mm = (value.split(":") + ["00"])[:2]
        self.h, self.mi = tk.StringVar(value=hh), tk.StringVar(value=mm)
        ttk.Combobox(self, textvariable=self.h, values=[f"{i:02d}" for i in range(24)], width=4,
                     state="readonly").pack(side="left")
        ttk.Label(self, text=":", style="Card.TLabel" if "Card" in style else "TLabel").pack(side="left", padx=2)
        ttk.Combobox(self, textvariable=self.mi, values=[f"{i:02d}" for i in range(0, 60, 5)], width=4,
                     state="readonly").pack(side="left")

    def get(self):
        return f"{self.h.get()}:{self.mi.get()}"

    def set(self, value):
        hh, mm = (value.split(":") + ["00"])[:2]
        self.h.set(hh)
        self.mi.set(mm)


class ThemeToggle(tk.Canvas):
    """Round sun / moon button for the top-right corner."""
    bg_key = "topbar"

    def __init__(self, parent, theme, command, size=40):
        super().__init__(parent, width=size, height=size, highlightthickness=0, bd=0, cursor="hand2")
        self.theme, self.command, self.size = theme, command, size
        self.bind("<Button-1>", lambda event: self.command())
        Tooltip(self, lambda: "Switch to light mode" if self.theme.name == "dark" else "Switch to dark mode")
        self.redraw()

    def redraw(self):
        c, s = self.theme.colors, self.size
        cx = cy = s / 2
        self.delete("all")
        self.create_oval(2, 2, s - 2, s - 2, fill=c["surface2"], outline=c["border"])
        if self.theme.name == "dark":                                   # dark now -> show a sun
            r = s * 0.16
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#f5a623", outline="")
            for k in range(8):
                import math
                a = k * math.pi / 4
                self.create_line(cx + math.cos(a) * r * 1.5, cy + math.sin(a) * r * 1.5,
                                 cx + math.cos(a) * r * 2.1, cy + math.sin(a) * r * 2.1, fill="#f5a623", width=2)
        else:                                                           # light now -> show a moon
            r = s * 0.26
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#f2b94a", outline="")
            self.create_oval(cx - r * 0.25, cy - r * 1.1, cx + r * 1.45, cy + r * 0.65, fill=c["surface2"], outline="")


class TriStrip(tk.Canvas):
    """Thin saffron / white / green accent bar along the very top of the window."""
    bg_key = "topbar"

    def __init__(self, parent, height=4):
        super().__init__(parent, height=height, highlightthickness=0, bd=0)
        self.bind("<Configure>", lambda event: self.redraw())

    def redraw(self):
        self.delete("all")
        w, h = max(self.winfo_width(), 300), int(self.cget("height") or 4)
        third = w / 3
        for i, colour in enumerate(("#ff9933", "#ffffff", "#138808")):
            self.create_rectangle(i * third, 0, (i + 1) * third + 1, h, fill=colour, outline="")



def titled_card(parent, eyebrow, title, grid=None, **kw):
    """Card with a small blue caption and a heading, like the TourismFlowX panels. Content goes from row 2."""
    box = card(parent, **kw)
    if grid:
        box.grid(**grid)
    ttk.Label(box, text=eyebrow, style="CardEyebrow.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
    ttk.Label(box, text=title, style="CardTitle.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 8))
    return box
