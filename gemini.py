from ollama import chat
from pypdf import PdfReader


# ==========================================================
# NORMAL AI CHAT
# ==========================================================

def ask_gemini(question):

    response = chat(
        model="llama3.2",
        messages=[
            {
                "role": "system",
                "content": """
You are an AI Student Support Chatbot.

Rules:
- Answer in simple English.
- Keep answers between 80 and 120 words.
- Use bullet points whenever possible.
- Give one real-life example if applicable.
- If the question is about programming,
  include a short code example.
- Do not use Markdown symbols like ** or ##.
- Be friendly and concise.
"""
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )

    return response.message.content


# ==========================================================
# EXTRACT TEXT FROM PDF
# ==========================================================

def extract_text_from_pdf(pdf_path):

    try:
        reader = PdfReader(pdf_path)

        extracted_text = ""

        for page in reader.pages:
            page_text = page.extract_text()

            if page_text:
                extracted_text += page_text + "\n"

        return extracted_text.strip()

    except Exception as e:
        print("PDF extraction error:", e)
        return ""


# ==========================================================
# AI CHAT USING PDF NOTES
# ==========================================================

def ask_from_notes(question, pdf_path):

    notes_text = extract_text_from_pdf(pdf_path)

    if not notes_text:
        return "Sorry, I could not extract readable text from this PDF."

    # Limit context to avoid sending an excessively large prompt
    max_characters = 12000
    notes_context = notes_text[:max_characters]

    prompt = f"""
You are an AI Student Study Assistant.

Answer the student's question using the supplied study notes.

Rules:
- Use the study notes as the primary source.
- Explain the answer in simple English.
- Do not invent information that is not supported by the notes.
- If the notes do not contain the answer, clearly say:
  "This information is not available in the selected notes."
- Use bullet points where useful.
- Give an example only when supported by the notes.
- Do not use Markdown symbols like ** or ##.
- Keep the answer clear and concise.

STUDY NOTES:
{notes_context}

STUDENT QUESTION:
{question}
"""

    try:

        response = chat(
            model="llama3.2",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful academic study assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.message.content

    except Exception as e:
        print("Notes AI error:", e)
        return "Sorry, the AI could not process your question."


# ==========================================================
# AI QUIZ GENERATOR
# ==========================================================

def generate_quiz_with_ollama(
    subject,
    topic,
    difficulty,
    num_questions
):

    prompt = f"""
Create exactly {num_questions}
multiple-choice questions.

Subject: {subject}

Topic: {topic}

Difficulty: {difficulty}

IMPORTANT:

Return ONLY one JSON object.

The JSON object MUST have this structure:

{{
    "questions": [
        {{
            "question": "Question text",
            "options": [
                "Option A",
                "Option B",
                "Option C",
                "Option D"
            ],
            "answer": 0
        }}
    ]
}}

Rules:

1. Generate exactly {num_questions} questions.
2. Every question must have exactly 4 options.
3. Only one option is correct.
4. The answer must be a number.
5. 0 = Option A.
6. 1 = Option B.
7. 2 = Option C.
8. 3 = Option D.
9. Questions must be related to the topic.
10. Questions must match the selected difficulty.
11. Do not repeat questions.
12. Do not include explanations.
13. Do not include Markdown.
14. Do not include code fences.
15. Do not write anything outside the JSON object.
"""

    response = chat(
        model="llama3.2",
        messages=[
            {
                "role": "system",
                "content": """
You are a quiz-generation AI.

Your job is ONLY to generate
multiple-choice questions.

Always follow the requested
JSON structure.

Never add explanations,
Markdown or extra text.
"""
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        format="json"
    )