from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    session,
    send_from_directory
)

import os
import json
import re

from werkzeug.utils import secure_filename

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

from database.database import get_db_connection

from chatbot.gemini import (
    ask_gemini,
    generate_quiz_with_ollama
)


app = Flask(__name__)


# ==========================================================
# CONFIGURATION
# ==========================================================

app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me")

UPLOAD_FOLDER = "uploads/notes"
ASSIGNMENT_FOLDER = "uploads/assignments"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ASSIGNMENT_FOLDER"] = ASSIGNMENT_FOLDER


# Create folders automatically
os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    ASSIGNMENT_FOLDER,
    exist_ok=True
)


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ==========================================================
# REGISTER
# ==========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        fullname = request.form["fullname"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        INSERT INTO students
        (fullname, email, password)
        VALUES (?, ?, ?)
        """

        cursor.execute(
            sql,
            (
                fullname,
                email,
                password
            )
        )

        conn.commit()

        cursor.close()
        conn.close()

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()

        sql = """
        SELECT *
        FROM students
        WHERE email=?
        AND password=?
        """

        cursor.execute(
            sql,
            (
                email,
                password
            )
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:

            session["student_id"] = user["id"]

            session["student_name"] = user[
                "fullname"
            ]

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid Email or Password!"
        )

    return render_template(
        "login.html"
    )


# ==========================================================
# DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    if "student_id" not in session:

        return redirect(
            url_for("login")
        )

    student_id = session[
        "student_id"
    ]

    conn = get_db_connection()

    cursor = conn.cursor()


    # ------------------------------------------------------
    # Student
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE id=?
        """,
        (student_id,)
    )

    user = cursor.fetchone()


    # ------------------------------------------------------
    # Total Chats
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total_chats
        FROM chat_history
        WHERE student_id=?
        """,
        (student_id,)
    )

    total_chats = cursor.fetchone()[
        "total_chats"
    ]


    # ------------------------------------------------------
    # Total Notes
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total_notes
        FROM notes
        """
    )

    total_notes = cursor.fetchone()[
        "total_notes"
    ]


    # ------------------------------------------------------
    # Total Assignments
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total_assignments
        FROM assignment_tasks a
        LEFT JOIN assignment_submissions s
            ON s.assignment_id = a.id
           AND s.student_id = ?
        WHERE a.assigned_student_id IS NULL
           OR a.assigned_student_id = ?
        """,
        (student_id, student_id)
    )

    total_assignments = cursor.fetchone()[
        "total_assignments"
    ]


    # ------------------------------------------------------
    # Overall Attendance
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT
            COALESCE(
                SUM(total_classes),
                0
            ) AS total_classes,

            COALESCE(
                SUM(attended_classes),
                0
            ) AS attended_classes

        FROM attendance

        WHERE student_id=?
        """,
        (student_id,)
    )

    attendance_summary = cursor.fetchone()


    total_classes = attendance_summary[
        "total_classes"
    ]

    attended_classes = attendance_summary[
        "attended_classes"
    ]


    if total_classes:

        overall_attendance = round(
            (
                attended_classes
                / total_classes
            ) * 100,
            1
        )

    else:

        overall_attendance = 0


    # ------------------------------------------------------
    # Subject Attendance
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT
            subject,
            total_classes,
            attended_classes

        FROM attendance

        WHERE student_id=?

        ORDER BY subject
        """,
        (student_id,)
    )

    attendance_data = cursor.fetchall()


    for row in attendance_data:

        if row["total_classes"]:

            row["percentage"] = round(
                (
                    row["attended_classes"]
                    / row["total_classes"]
                ) * 100,
                1
            )

        else:

            row["percentage"] = 0


    # ------------------------------------------------------
    # Recent Chats
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT

            question AS activity,

            created_at AS activity_time,

            'chat' AS activity_type

        FROM chat_history

        WHERE student_id=?

        ORDER BY created_at DESC

        LIMIT 5
        """,
        (student_id,)
    )

    recent_chats = cursor.fetchall()


    # ------------------------------------------------------
    # Recent Assignments
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT
            'Submitted: ' || a.title AS activity,
            s.submitted_at AS activity_time,
            'assignment' AS activity_type
        FROM assignment_submissions s
        JOIN assignment_tasks a ON a.id = s.assignment_id
        WHERE s.student_id=?
        ORDER BY s.submitted_at DESC
        LIMIT 5
        """,
        (student_id,)
    )

    recent_assignments = cursor.fetchall()


    # ------------------------------------------------------
    # Recent Notes
    # ------------------------------------------------------

    cursor.execute(
        """
        SELECT

            'New note: ' || title AS activity,

            uploaded_at AS activity_time,

            'note' AS activity_type

        FROM notes

        ORDER BY uploaded_at DESC

        LIMIT 5
        """
    )

    recent_notes = cursor.fetchall()


    # ------------------------------------------------------
    # Combine Activity
    # ------------------------------------------------------

    recent_activity = (
        recent_chats
        + recent_assignments
        + recent_notes
    )


    recent_activity.sort(
        key=lambda x: x["activity_time"],
        reverse=True
    )


    recent_activity = recent_activity[:6]

    # If the student has not performed any activity yet, show a real
    # account-created event instead of an empty dashboard.
    if not recent_activity and user:
        recent_activity = [{
            "activity": "Welcome! Your student account was created.",
            "activity_time": user["created_at"],
            "activity_type": "account"
        }]


    cursor.close()
    conn.close()


    return render_template(

        "dashboard.html",

        user=user,

        total_chats=total_chats,

        total_notes=total_notes,

        total_assignments=total_assignments,

        overall_attendance=overall_attendance,

        attendance_data=attendance_data,

        recent_activity=recent_activity
    )


# ==========================================================
# CHAT PAGE
# ==========================================================

@app.route("/chat")
def chat():
    if "student_id" not in session:
        return redirect(url_for("login"))

    note_id = request.args.get("note_id", type=int)
    selected_note = None

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT question, answer
            FROM chat_history
            WHERE student_id=?
            ORDER BY created_at ASC
        """, (session["student_id"],))
        chats = cursor.fetchall()

        if note_id:
            cursor.execute("""
                SELECT id, subject, title, filename
                FROM notes
                WHERE id=?
            """, (note_id,))
            selected_note = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()

    return render_template(
        "chat.html",
        chats=chats,
        selected_note=selected_note
    )


@app.route(
    "/ask",
    methods=["POST"]
)
def ask():

    if "student_id" not in session:
        return jsonify({"answer": "Please login first."}), 401

    try:
        data = request.get_json()

        if not data:
            return jsonify({"answer": "Invalid request."}), 400

        question = data.get("message", "").strip()
        note_id = data.get("note_id")

        if not question:
            return jsonify({"answer": "Please enter a question."}), 400

        try:
            note_id = int(note_id) if note_id not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            note_id = None

        student_id = session["student_id"]
        q = question.lower()

        # Fetch only the data needed for this question.
        attendance_words = [
            "attendance", "attend", "present", "absent",
            "classes", "class percentage"
        ]
        assignment_words = [
            "assignment", "assignments", "submitted",
            "submission", "submit"
        ]
        notes_words = [
            "note", "notes", "study material",
            "materials", "available notes"
        ]
        profile_words = [
            "my name", "who am i", "my email",
            "my profile", "student name"
        ]

        wants_attendance = any(w in q for w in attendance_words)
        wants_assignments = any(w in q for w in assignment_words)
        wants_notes = any(w in q for w in notes_words)
        wants_profile = any(w in q for w in profile_words)

        conn = get_db_connection()
        cursor = conn.cursor()
        context_parts = []

        if wants_profile:
            cursor.execute("""
                SELECT fullname, email
                FROM students
                WHERE id=?
            """, (student_id,))
            student = cursor.fetchone()

            if student:
                context_parts.append(
                    f"Student name: {student['fullname']}\n"
                    f"Student email: {student['email']}"
                )

        if wants_attendance:
            cursor.execute("""
                SELECT subject, total_classes, attended_classes
                FROM attendance
                WHERE student_id=?
                ORDER BY subject
            """, (student_id,))

            rows = cursor.fetchall()

            if rows:
                lines = []
                total_classes = 0
                attended_classes = 0

                for row in rows:
                    total = row["total_classes"] or 0
                    attended = row["attended_classes"] or 0
                    total_classes += total
                    attended_classes += attended

                    percentage = (
                        round((attended / total) * 100, 1)
                        if total else 0
                    )

                    lines.append(
                        f"{row['subject']}: "
                        f"{attended}/{total} ({percentage}%)"
                    )

                overall = (
                    round((attended_classes / total_classes) * 100, 1)
                    if total_classes else 0
                )

                context_parts.append(
                    "Attendance:\n"
                    + "\n".join(lines)
                    + f"\nOverall attendance: {overall}%"
                )
            else:
                context_parts.append("No attendance records are available.")

        if wants_assignments:
            cursor.execute("""
                SELECT a.subject, a.title, s.submitted_at
                FROM assignment_submissions s
                JOIN assignment_tasks a ON a.id = s.assignment_id
                WHERE s.student_id=?
                ORDER BY s.submitted_at DESC
                LIMIT 10
            """, (student_id,))

            rows = cursor.fetchall()

            if rows:
                lines = [
                    f"{row['subject']}: {row['title']} "
                    f"(submitted {row['submitted_at']})"
                    for row in rows
                ]
                context_parts.append(
                    "Student assignment submissions:\n"
                    + "\n".join(lines)
                )
            else:
                context_parts.append(
                    "No assignment submissions are available."
                )

        if wants_notes:
            cursor.execute("""
                SELECT subject, title
                FROM notes
                ORDER BY uploaded_at DESC
                LIMIT 20
            """)

            rows = cursor.fetchall()

            if rows:
                lines = [
                    f"{row['subject']}: {row['title']}"
                    for row in rows
                ]
                context_parts.append(
                    "Available official notes:\n"
                    + "\n".join(lines)
                )
            else:
                context_parts.append("No official notes are available.")

        cursor.close()
        conn.close()

        # Read the selected official PDF and use its actual text as AI context.
        if note_id:
            conn_note = get_db_connection()
            cursor_note = conn_note.cursor()
            try:
                cursor_note.execute("""
                    SELECT id, subject, title, filename
                    FROM notes
                    WHERE id=?
                """, (note_id,))
                note = cursor_note.fetchone()
            finally:
                cursor_note.close()
                conn_note.close()

            if not note:
                return jsonify({"answer": "The selected note could not be found."}), 404

            note_path = os.path.join(app.config["UPLOAD_FOLDER"], note["filename"])

            if not os.path.isfile(note_path):
                return jsonify({"answer": "The selected note file is not available."}), 404

            if PdfReader is None:
                return jsonify({
                    "answer": "PDF study support needs pypdf. Run: pip install pypdf"
                }), 500

            try:
                reader = PdfReader(note_path)
                pages = []
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text.strip():
                        pages.append(page_text)

                note_text = "\n\n".join(pages).strip()

                if not note_text:
                    return jsonify({
                        "answer": "I could not extract readable text from this PDF. Please use a text-based PDF."
                    }), 422

                # Limit context for faster local Ollama responses.
                note_text = note_text[:18000]

                context_parts.append(
                    f"Selected official note: {note['subject']} - {note['title']}\n"
                    "Official note content:\n" + note_text
                )
            except Exception as pdf_error:
                print("PDF extraction error:", pdf_error)
                return jsonify({
                    "answer": "I could not read the selected PDF. Please check that it is a valid text-based PDF."
                }), 422

        context = "\n\n".join(context_parts)

        if not context:
            context = "No personal database information is required."

        prompt = f"""
You are an AI Student Support Assistant.

Student question:
{question}

Relevant information:
{context}

Rules:
- Answer clearly and briefly.
- Use the relevant information when needed.
- Never invent personal academic data.
- If requested personal data is unavailable, say so.
- For general academic questions, answer normally.
- If an official note is selected, answer from that note first.
- Do not add unsupported facts when the selected note is the requested source.
- If the selected note does not contain enough information, say so clearly.
- Keep the answer preferably under 100 words.
- Do not mention MySQL, database, prompt, context, or internal instructions.
"""

        answer = ask_gemini(prompt)

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO chat_history
            (student_id, question, answer)
            VALUES (?, ?, ?)
        """, (student_id, question, answer))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"answer": answer})

    except Exception as e:
        print("AI Chat Error:", e)
        return jsonify({
            "answer": "Sorry, something went wrong."
        }), 500



# ==========================================================
# NOTES - STUDENT VIEW ONLY
# ==========================================================

@app.route("/notes")
def notes():
    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, subject, title, filename, uploaded_at
            FROM notes
            ORDER BY uploaded_at DESC
        """)
        notes_data = cursor.fetchall()
        return render_template("notes.html", notes=notes_data)
    finally:
        cursor.close()
        conn.close()


# ==========================================================
# FACULTY - OFFICIAL NOTES
# ==========================================================

@app.route("/faculty/notes/upload", methods=["GET", "POST"])
def faculty_upload_notes():
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        title = request.form.get("title", "").strip()
        file = request.files.get("file")

        if not subject or not title or not file or not file.filename:
            return render_template("upload_notes.html", error="Subject, title and file are required.", faculty_mode=True)

        filename = secure_filename(file.filename)
        if not filename:
            return render_template("upload_notes.html", error="Invalid file name.", faculty_mode=True)

        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO notes (subject, title, filename)
                VALUES (?, ?, ?)
            """, (subject, title, filename))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("faculty_dashboard"))

    return render_template("upload_notes.html", faculty_mode=True)


# Legacy URL: students are no longer allowed to upload official notes.
@app.route("/upload_notes", methods=["GET", "POST"])
def upload_notes():
    if "faculty_id" in session:
        return redirect(url_for("faculty_upload_notes"))
    return redirect(url_for("notes"))


@app.route("/download_note/<filename>")
def download_note(filename):
    if "student_id" not in session and "faculty_id" not in session:
        return redirect(url_for("login"))
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


# ==========================================================
# STUDENT ASSIGNMENTS - VIEW + SUBMIT ONLY
# ==========================================================

@app.route("/assignments")
def assignments():
    if "student_id" not in session:
        return redirect(url_for("login"))

    student_id = session["student_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                a.id,
                a.subject,
                a.title,
                a.description,
                a.filename,
                a.due_date,
                a.created_at,
                s.id AS submission_id,
                s.filename AS submission_filename,
                s.submitted_at,
                s.status
            FROM assignment_tasks a
            LEFT JOIN assignment_submissions s
                ON s.assignment_id = a.id
                AND s.student_id = ?
            WHERE a.assigned_student_id IS NULL
               OR a.assigned_student_id = ?
            ORDER BY a.due_date IS NULL, a.due_date ASC, a.created_at DESC
        """, (student_id, student_id))
        assignment_data = cursor.fetchall()
        return render_template("assignments.html", assignments=assignment_data)
    finally:
        cursor.close()
        conn.close()


@app.route("/assignment/<int:assignment_id>/download")
def download_assignment_task(assignment_id):
    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT filename
            FROM assignment_tasks
            WHERE id=?
              AND (assigned_student_id IS NULL OR assigned_student_id=?)
        """, (assignment_id, session["student_id"]))
        row = cursor.fetchone()
        if not row:
            return "Assignment not found or not assigned to you.", 404
        return send_from_directory(app.config["ASSIGNMENT_FOLDER"], row["filename"], as_attachment=True)
    finally:
        cursor.close()
        conn.close()


@app.route("/assignment/<int:assignment_id>/submit", methods=["POST"])
def submit_assignment(assignment_id):
    if "student_id" not in session:
        return redirect(url_for("login"))

    file = request.files.get("file")
    if not file or not file.filename:
        return redirect(url_for("assignments"))

    student_id = session["student_id"]
    filename = secure_filename(file.filename)
    if not filename:
        return redirect(url_for("assignments"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id FROM assignment_tasks
            WHERE id=?
              AND (assigned_student_id IS NULL OR assigned_student_id=?)
        """, (assignment_id, student_id))
        task = cursor.fetchone()
        if not task:
            return "Assignment not found or not assigned to you.", 404

        # Keep student submissions separate from faculty assignment files.
        safe_name = f"student_{student_id}_assignment_{assignment_id}_{filename}"
        os.makedirs(app.config["ASSIGNMENT_FOLDER"], exist_ok=True)
        file.save(os.path.join(app.config["ASSIGNMENT_FOLDER"], safe_name))

        cursor.execute("""
            INSERT INTO assignment_submissions
                (assignment_id, student_id, filename, status)
            VALUES (?, ?, ?, 'Submitted')
            ON CONFLICT(assignment_id, student_id) DO UPDATE SET
                filename=excluded.filename,
                submitted_at=CURRENT_TIMESTAMP,
                status='Resubmitted'
        """, (assignment_id, student_id, safe_name))
        conn.commit()
        return redirect(url_for("assignments"))
    finally:
        cursor.close()
        conn.close()


# Legacy student upload route is intentionally blocked.
@app.route("/upload_assignment", methods=["GET", "POST"])
def upload_assignment():
    if "faculty_id" in session:
        return redirect(url_for("faculty_create_assignment"))
    return redirect(url_for("assignments"))


@app.route("/download_assignment/<filename>")
def download_assignment(filename):
    if "student_id" not in session and "faculty_id" not in session:
        return redirect(url_for("login"))
    return send_from_directory(app.config["ASSIGNMENT_FOLDER"], filename, as_attachment=True)


# ==========================================================
# ATTENDANCE
# ==========================================================

@app.route("/attendance")
def attendance():
    if "student_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM attendance
            WHERE student_id=?
            ORDER BY subject
        """, (session["student_id"],))
        attendance_data = cursor.fetchall()
        for row in attendance_data:
            total = row.get("total_classes") or 0
            attended = row.get("attended_classes") or 0
            row["percentage"] = round(attended / total * 100, 1) if total else 0
        return render_template("attendance.html", attendance=attendance_data)
    finally:
        cursor.close()
        conn.close()

# ==========================================================
# AI QUIZ PAGE
# ==========================================================

@app.route("/quiz")
def quiz():

    if "student_id" not in session:

        return redirect(
            url_for("login")
        )


    return render_template(
        "quiz.html"
    )


# ==========================================================
# AI QUIZ GENERATOR
# ==========================================================

@app.route(
    "/quiz/generate",
    methods=["POST"]
)
def generate_quiz():

    if "student_id" not in session:

        return jsonify({
            "error":
            "Please login first."
        }), 401


    try:

        data = request.get_json()


        if not data:

            return jsonify({
                "error":
                "Invalid request."
            }), 400


        subject = data.get(
            "subject",
            ""
        ).strip()


        topic = data.get(
            "topic",
            ""
        ).strip()


        difficulty = data.get(
            "difficulty",
            "Medium"
        ).strip()


        try:

            num_questions = int(
                data.get(
                    "num_questions",
                    5
                )
            )

        except:

            num_questions = 5


        # Keep quiz between 3 and 10
        num_questions = max(
            3,
            min(
                num_questions,
                10
            )
        )


        # --------------------------------------------------
        # Validate
        # --------------------------------------------------

        if not subject:

            return jsonify({
                "error":
                "Please select a subject."
            }), 400


        if not topic:

            return jsonify({
                "error":
                "Please enter a topic."
            }), 400


        # --------------------------------------------------
        # Call Ollama
        # --------------------------------------------------

        quiz_text = generate_quiz_with_ollama(

            subject,

            topic,

            difficulty,

            num_questions
        )


        print()
        print(
            "========== OLLAMA QUIZ RESPONSE =========="
        )
        print(quiz_text)
        print(
            "=========================================="
        )
        print()


        # --------------------------------------------------
        # Clean response
        # --------------------------------------------------

        quiz_text = quiz_text.strip()


        # Remove Markdown code fences
        quiz_text = re.sub(
            r"```json",
            "",
            quiz_text,
            flags=re.IGNORECASE
        )


        quiz_text = re.sub(
            r"```",
            "",
            quiz_text
        )


        quiz_text = quiz_text.strip()


        # --------------------------------------------------
        # Find JSON object
        # --------------------------------------------------

        start = quiz_text.find("{")

        end = quiz_text.rfind("}")


        if start == -1 or end == -1:

            raise ValueError(
                "Ollama did not return JSON."
            )


        quiz_text = quiz_text[
            start:end + 1
        ]


        # --------------------------------------------------
        # Parse JSON
        # --------------------------------------------------

        quiz_object = json.loads(
            quiz_text
        )


        # --------------------------------------------------
        # Extract questions
        # --------------------------------------------------

        quiz_data = quiz_object.get(
            "questions"
        )


        if not isinstance(
            quiz_data,
            list
        ):

            raise ValueError(
                "Questions array missing."
            )


        # --------------------------------------------------
        # Validate question count
        # --------------------------------------------------

        if len(quiz_data) != num_questions:

            raise ValueError(
                f"Ollama returned {len(quiz_data)} "
                f"questions instead of {num_questions}."
            )


        # --------------------------------------------------
        # Validate every question
        # --------------------------------------------------

        for question in quiz_data:


            if not isinstance(
                question,
                dict
            ):

                raise ValueError(
                    "Invalid question object."
                )


            if not question.get(
                "question"
            ):

                raise ValueError(
                    "Question text missing."
                )


            options = question.get(
                "options"
            )


            if not isinstance(
                options,
                list
            ):

                raise ValueError(
                    "Options must be a list."
                )


            if len(options) != 4:

                raise ValueError(
                    "Every question needs exactly 4 options."
                )


            answer = question.get(
                "answer"
            )


            # Sometimes models return "0" instead of 0
            try:

                answer = int(answer)

            except:

                raise ValueError(
                    "Invalid answer."
                )


            if answer not in [
                0,
                1,
                2,
                3
            ]:

                raise ValueError(
                    "Answer must be 0, 1, 2 or 3."
                )


            question["answer"] = answer


        # --------------------------------------------------
        # Return to browser
        # --------------------------------------------------

        return jsonify({

            "success": True,

            "quiz": quiz_data

        })


    except json.JSONDecodeError as e:

        print(
            "Quiz JSON Error:",
            e
        )


        return jsonify({

            "error":
            "Ollama returned an invalid quiz format. "
            "Please try again."

        }), 500


    except Exception as e:

        print(
            "Quiz generation error:",
            e
        )


        return jsonify({

            "error":
            str(e)

        }), 500





# ==========================================================
# FACULTY PORTAL
# ==========================================================

@app.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if email == "faculty@college.com" and password == "faculty123":
            session["faculty_id"] = 1
            session["faculty_name"] = "Faculty"
            session.pop("student_id", None)
            return redirect(url_for("faculty_dashboard"))
        return render_template("faculty_login.html", error="Invalid Email or Password!")
    return render_template("faculty_login.html")


@app.route("/faculty/dashboard")
def faculty_dashboard():
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) AS total_notes FROM notes")
        total_notes = cursor.fetchone()["total_notes"]
        cursor.execute("SELECT COUNT(*) AS total_assignments FROM assignment_tasks")
        total_assignments = cursor.fetchone()["total_assignments"]
        cursor.execute("SELECT COUNT(*) AS total_students FROM students")
        total_students = cursor.fetchone()["total_students"]
        cursor.execute("SELECT COUNT(*) AS total_submissions FROM assignment_submissions")
        total_submissions = cursor.fetchone()["total_submissions"]
        cursor.execute("""
            SELECT subject, title, filename, uploaded_at
            FROM notes ORDER BY uploaded_at DESC LIMIT 5
        """)
        recent_notes = cursor.fetchall()
        cursor.execute("""
            SELECT a.id, a.subject, a.title, a.due_date, a.created_at,
                   COUNT(s.id) AS submission_count
            FROM assignment_tasks a
            LEFT JOIN assignment_submissions s ON s.assignment_id=a.id
            GROUP BY a.id, a.subject, a.title, a.due_date, a.created_at
            ORDER BY a.created_at DESC LIMIT 5
        """)
        recent_assignments = cursor.fetchall()
        return render_template("faculty_dashboard.html",
                               total_notes=total_notes,
                               total_assignments=total_assignments,
                               total_students=total_students,
                               total_submissions=total_submissions,
                               recent_notes=recent_notes,
                               recent_assignments=recent_assignments)
    finally:
        cursor.close()
        conn.close()


@app.route("/faculty/notes")
def faculty_notes():
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))
    return redirect(url_for("faculty_dashboard"))


@app.route("/faculty/assignments/create", methods=["GET", "POST"])
def faculty_create_assignment():
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip() or None
        assigned_student_id = request.form.get("assigned_student_id", "").strip() or None
        file = request.files.get("file")

        if not subject or not title or not file or not file.filename:
            return render_template("faculty_create_assignment.html", error="Subject, title and assignment file are required.")

        filename = secure_filename(file.filename)
        if not filename:
            return render_template("faculty_create_assignment.html", error="Invalid file name.")

        if assigned_student_id:
            try:
                assigned_student_id = int(assigned_student_id)
            except ValueError:
                assigned_student_id = None

        os.makedirs(app.config["ASSIGNMENT_FOLDER"], exist_ok=True)
        file.save(os.path.join(app.config["ASSIGNMENT_FOLDER"], filename))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO assignment_tasks
                    (subject, title, description, filename, due_date, assigned_student_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (subject, title, description, filename, due_date, assigned_student_id))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("faculty_dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, fullname, email FROM students ORDER BY fullname")
        students = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
    return render_template("faculty_create_assignment.html", students=students)


@app.route("/faculty/submissions")
def faculty_submissions():
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.id, s.filename, s.submitted_at, s.status,
                   a.subject, a.title,
                   st.fullname, st.email
            FROM assignment_submissions s
            JOIN assignment_tasks a ON a.id=s.assignment_id
            JOIN students st ON st.id=s.student_id
            ORDER BY s.submitted_at DESC
        """)
        submissions = cursor.fetchall()
        return render_template("faculty_submissions.html", submissions=submissions)
    finally:
        cursor.close()
        conn.close()


@app.route("/faculty/submission/<int:submission_id>/download")
def faculty_download_submission(submission_id):
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT filename FROM assignment_submissions WHERE id=?", (submission_id,))
        row = cursor.fetchone()
        if not row:
            return "Submission not found.", 404
        return send_from_directory(app.config["ASSIGNMENT_FOLDER"], row["filename"], as_attachment=True)
    finally:
        cursor.close()
        conn.close()


@app.route("/faculty/ai")
def faculty_ai():
    if "faculty_id" not in session:
        return redirect(url_for("faculty_login"))
    return render_template("faculty_ai.html")


@app.route("/faculty/ai/generate", methods=["POST"])
def faculty_ai_generate():
    if "faculty_id" not in session:
        return jsonify({"error": "Please login as faculty first."}), 401
    try:
        data = request.get_json(silent=True) or {}
        tool = data.get("tool", "").strip()
        prompt_text = data.get("prompt", "").strip()
        if not prompt_text:
            return jsonify({"error": "Please enter a topic or instruction."}), 400
        tool_names = {
            "assignment": "Create a clear academic assignment",
            "question_paper": "Create an academic question paper",
            "quiz": "Create useful multiple-choice quiz questions",
            "notes": "Create structured study notes",
            "summary": "Summarize the supplied academic material",
            "important_questions": "Generate important exam-oriented questions",
            "performance": "Give a practical student performance analysis",
            "doubt_faq": "Generate common student doubts and answers",
            "announcement": "Write a professional college announcement",
            "study_plan": "Create a realistic student study plan"
        }
        instruction = tool_names.get(tool, "Help the faculty member with this academic task")
        final_prompt = f"""
You are an AI Faculty Assistant inside a college academic management system.
Task: {instruction}
Faculty request:
{prompt_text}
Return a useful, professional response with clear headings and bullet points.
Do not invent student records, marks, attendance percentages, or database facts.
"""
        answer = ask_gemini(final_prompt)
        return jsonify({"success": True, "answer": answer})
    except Exception as e:
        print("Faculty AI error:", e)
        return jsonify({"error": "AI generation failed. Please check that Ollama is running."}), 500


@app.route("/faculty/logout")
def faculty_logout():
    session.pop("faculty_id", None)
    session.pop("faculty_name", None)
    return redirect(url_for("faculty_login"))


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)