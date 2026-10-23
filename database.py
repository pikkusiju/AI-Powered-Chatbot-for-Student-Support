import sqlite3
from pathlib import Path

# Store the SQLite database locally inside the Flask project's instance folder.
BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "ai_student_chatbot.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class DictRowFactory:
    """Return normal dictionaries so existing templates/routes keep working."""

    @staticmethod
    def create(cursor, row):
        columns = [column[0] for column in cursor.description]
        return {columns[index]: row[index] for index in range(len(columns))}


def get_db_connection():
    """Create a SQLite connection for the application."""
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=10,
        check_same_thread=False,
    )

    connection.row_factory = DictRowFactory.create
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")

    return connection


def initialize_database():
    """Create all required tables if they do not already exist."""
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")

        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        connection.executescript(schema)
        connection.commit()
    finally:
        connection.close()


initialize_database()
