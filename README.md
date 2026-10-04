# Student Hub

A desktop app for the things a student juggles every week: deadlines, exams, study time, notes, money and books. It is built with Python and Tkinter, runs locally, and keeps your data on your own computer.

**Live project page:** https://25ds31-droid.github.io/Student_hub/

## Features

| Page | What it does |
|---|---|
| Home | Dashboard with upcoming exams, task counts, study summary and spending |
| Tasks | Quick-add deadlines from plain text, week view with hover details, workload charts |
| Exam Scheduler | Clash detection, a calendar, and a day-by-day study plan built from your syllabus progress |
| Study Tracker | Log sessions with a live timer, track goals and streaks, plan your time budget |
| Notes Lab | Tagged notes, text tools, a NumPy lab and a Pandas CSV explorer |
| Expense Tracker | Type `Lunch 250 upi` to log an expense. Budgets, forecasts, analytics and a split-bill settler |
| Toolbox | Prime explorer, matrix lab, statistics, regression, loan EMI, SIP planner and more |
| Book Finder | Search the web for books on a topic and keep a reading library |
| Profile | Account details and settings |

Other highlights:
- Login and registration, with a separate data folder for each user
- Light and dark theme toggle
- Pages load the first time you open them, so startup stays fast

## Tech stack

- Python 3.9 or newer
- Tkinter (GUI)
- SQLite (local storage)
- pandas, NumPy, Matplotlib

## Getting started

1. **Clone the repository**
   ```bash
   git clone https://github.com/25ds31-droid/Student_hub.git
   cd Student_hub
   ```

2. **(Optional) Create a virtual environment**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS / Linux
   source venv/bin/activate
   ```

3. **Install the dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app**
   ```bash
   python main.py
   ```

Register an account on the first screen, then sign in.

### Troubleshooting

- `No module named 'tkinter'` on Linux: run `sudo apt install python3-tk`
- `'python' is not recognized` on Windows: reinstall Python with "Add to PATH" ticked, or use `py main.py`
- `No module named 'pandas'`: activate your virtual environment and run `pip install -r requirements.txt` again

## Project structure

```
main.py              Launcher, login, sidebar and home dashboard
hub_auth.py          User accounts and per-user data folders
hub_theme.py         Theme, widgets and shared UI helpers
hub_charts.py        Chart widgets (bar, donut, line and more)
task_manager.py      Tasks page
exam_scheduler.py    Exam Scheduler page
study_tracker.py     Study Tracker page
notes_lab.py         Notes Lab page
expense_tracker.py   Expense Tracker page
toolbox.py           Toolbox page
book_finder.py       Book Finder page
requirements.txt     Python dependencies
index.html           Project showcase page (GitHub Pages)
```

## Notes

- Data is stored locally in SQLite files inside each user's folder. Nothing is sent to a server.
- Book Finder is the only page that needs an internet connection.

## Author

Amaan, second-year engineering student.
GitHub: [@25ds31-droid](https://github.com/25ds31-droid)[README (1).md](https://github.com/user-attachments/files/33025531/README.1.md)
