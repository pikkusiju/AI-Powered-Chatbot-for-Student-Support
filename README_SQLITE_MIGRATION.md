# SQLite conversion patch

These files convert the project database from MySQL to SQLite while keeping the existing Flask routes and UI structure.

## Replace

1. Replace your current `app.py` with `app.py` from this patch.
2. Replace `database/database.py` with the supplied SQLite version.
3. Put `database/schema.sql` inside your project's `database/` folder.
4. Add `.env.example`, `.gitignore`, and `requirements.txt` as appropriate.

## Important

- The SQLite database is created automatically at `instance/ai_student_chatbot.db`.
- Do not copy the generated `.db` file to GitHub. It is ignored by `.gitignore`.
- Your existing `templates/`, `static/`, `uploads/`, and `chatbot/` folders can remain unchanged.
- Keep your current working `chatbot/gemini.py` because the project uses Ollama/Llama 3.2 there.
- If you have important data in MySQL, export/backup it before switching. This patch starts a fresh SQLite database; it does not migrate existing MySQL records.

## Run

```powershell
python app.py
```

The database and required tables will be created automatically on startup/import.
