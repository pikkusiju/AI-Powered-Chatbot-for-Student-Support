
import sqlite3
from pathlib import Path

db_path = (
    Path(__file__).resolve().parent
    / "instance"
    / "ai_student_chatbot.db"
)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type = 'table'
      AND name NOT LIKE 'sqlite_%'
    ORDER BY name
""")

tables = [row[0] for row in cursor.fetchall()]

print("Available tables:")
for i, table in enumerate(tables, start=1):
    print(f"{i}. {table}")

choice = int(input("\nEnter table number: "))

if 1 <= choice <= len(tables):
    table = tables[choice - 1]

    cursor.execute(f'SELECT * FROM "{table}"')
    rows = cursor.fetchall()

    columns = [col[0] for col in cursor.description]
    print("\nColumns:", columns)
    print("Total records:", len(rows))

    for row in rows:
        print(row)
else:
    print("Invalid table number.")

conn.close()
