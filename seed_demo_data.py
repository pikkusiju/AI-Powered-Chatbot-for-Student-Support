"""Create clearly-labelled sample attendance data for a college demo.
Run this once after registering a demo student:
    python seed_demo_data.py
"""
from database.database import get_db_connection

SUBJECTS = [
    ("Data Structures", 22, 18),
    ("Database Management", 24, 20),
    ("Python Programming", 20, 17),
    ("Web Development", 25, 21),
]


def main():
    conn = get_db_connection()
    try:
        students = conn.execute(
            "SELECT id, fullname, email FROM students ORDER BY id"
        ).fetchall()

        if not students:
            print("No students found. Register a student first.")
            return

        print("Students:")
        for s in students:
            print(f"  {s['id']}: {s['fullname']} ({s['email']})")

        email = input("Enter the demo student's email: ").strip()
        student = conn.execute(
            "SELECT id, fullname FROM students WHERE email=?",
            (email,),
        ).fetchone()

        if not student:
            print("Student not found.")
            return

        # Only seed subjects that are not already present for this student.
        inserted = 0
        for subject, total, attended in SUBJECTS:
            exists = conn.execute(
                "SELECT id FROM attendance WHERE student_id=? AND subject=?",
                (student["id"], subject),
            ).fetchone()
            if not exists:
                conn.execute(
                    """
                    INSERT INTO attendance
                    (student_id, subject, total_classes, attended_classes)
                    VALUES (?, ?, ?, ?)
                    """,
                    (student["id"], subject, total, attended),
                )
                inserted += 1

        conn.commit()
        print(f"Added {inserted} sample attendance records for {student['fullname']}.")
        print("Refresh the student dashboard to see the Attendance Overview.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

