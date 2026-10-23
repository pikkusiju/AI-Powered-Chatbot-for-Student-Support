# Dashboard Data Fix

The dashboard already reads attendance and recent activity from SQLite.
A fresh SQLite database is empty, so the attendance card correctly showed
"No attendance data available".

## What was changed

- The dashboard now shows a real account-created activity when there is no
  chat, assignment, or note activity yet.
- Added `seed_demo_data.py` for optional college-expo demo attendance data.
- Existing attendance is never overwritten.

## Add demo attendance

After registering a student, from the project root run:

```powershell
python seed_demo_data.py
```

Select the student's email when prompted.

The script adds these sample subjects only if they do not already exist:

- Data Structures — 18/22
- Database Management — 20/24
- Python Programming — 17/20
- Web Development — 21/25

These are demo values. Replace them with real academic records for an actual deployment.

Then restart Flask if needed and refresh `/dashboard`.
