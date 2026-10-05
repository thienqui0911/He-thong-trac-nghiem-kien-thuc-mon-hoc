from flask import Flask, render_template, request, session
from groq import Groq
from dotenv import load_dotenv
from database import create_tables, get_connection
import webbrowser
import os
import json
import time


# =========================
# 1. ĐỌC FILE .env
# =========================

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")


# =========================
# 2. KIỂM TRA API KEY
# =========================

if not api_key:
    raise ValueError(
        "Không tìm thấy GEMINI_API_KEY trong file .env"
    )


# =========================
# 3. TẠO GEMINI CLIENT
# =========================
client = Groq(
    api_key=api_key
)


# =========================
# 4. TẠO FLASK APP
# =========================

app = Flask(__name__)
app.secret_key = "ai-quiz-secret-key"

# =========================
# 5. TRANG CHỦ
# =========================

@app.route("/")
def home():

    return render_template("index.html")


# =========================
# 6. TẠO BÀI KIỂM TRA
# =========================

@app.route("/create-quiz", methods=["POST"])
def create_quiz():

    subject = request.form["subject"]
    knowledge_type = request.form["knowledge_type"]
    number_questions = int(request.form["number_questions"])
    difficulty = request.form["difficulty"]
    if knowledge_type == "Tất cả":
       knowledge_instruction = """
Hãy tạo câu hỏi trắc nghiệm bao quát tất cả nội dung của môn học.
Các câu hỏi cần đa dạng, không chỉ tập trung vào một loại kiến thức mà phải bao gồm : khái niệm, định lý, tính chất và bài tập.
"""
    else:
       knowledge_instruction = f"""
Hãy tập trung vào loại kiến thức: {knowledge_type}
"""
    # ==========================================
    # HÀM TẠO MỘT NHÓM CÂU HỎI
    # ==========================================

    def generate_questions(batch_size, existing_questions):

        prompt = f"""
Bạn là một giáo viên đang tạo bài kiểm tra trắc nghiệm.
Bạn là một giáo sư về lĩnh vực {subject}.
Gọi học sinh là bạn.

Hãy tạo ĐÚNG {batch_size} câu hỏi trắc nghiệm về:

Môn học: {subject}

Loại kiến thức: {knowledge_type}
Độ khó: {difficulty}

Đây là các câu hỏi đã được tạo trước đó:

{json.dumps(existing_questions, ensure_ascii=False, indent=2)}

YÊU CẦU:

- Tất cả câu hỏi phải bằng TIẾNG VIỆT.
- Tất cả đáp án phải bằng TIẾNG VIỆT.
- Không viết câu hỏi bằng tiếng Anh.
- Không viết đáp án bằng tiếng Anh, trừ thuật ngữ chuyên ngành bắt buộc.
- Câu hỏi phải rõ ràng, tự nhiên và phù hợp với học sinh Việt Nam.
- Không được tạo câu hỏi trùng với các câu hỏi đã có.
- Mỗi câu có đúng 4 đáp án.
- Chỉ có 1 đáp án đúng.

Mỗi câu hỏi phải có trường "knowledge".

"knowledge" là tên kiến thức cụ thể mà câu hỏi đang kiểm tra.

Nếu nhiều câu cùng kiểm tra một kiến thức thì sử dụng cùng một tên "knowledge".

Không dùng các tên quá chung như:
- "Kiến thức"
- "Bài tập"
- "Lý thuyết"

BẮT BUỘC tạo ĐÚNG {batch_size} câu.

Không tạo ít hơn.
Không tạo nhiều hơn.
Không được trùng lặp.
Mỗi câu hỏi chỉ có 1 đáp án đúng.
Câu hỏi và kết quả phải rõ ràng và chính xác.
Trả kết quả DUY NHẤT dưới dạng JSON:

{{
    "questions": [
        {{
            "question": "Câu hỏi bằng tiếng Việt",
            "knowledge": "Tên kiến thức cụ thể được kiểm tra",
            "options": [
                "Đáp án A",
                "Đáp án B",
                "Đáp án C",
                "Đáp án D"
            ],
            "answer": 0
        }}
    ]
}}

Trong đó:

answer = 0 nếu A đúng
answer = 1 nếu B đúng
answer = 2 nếu C đúng
answer = 3 nếu D đúng
"""

        # ==========================================
        # THỬ GỌI AI TỐI ĐA 3 LẦN
        # ==========================================

        for attempt in range(3):

            try:

                response = client.chat.completions.create(

                    model="openai/gpt-oss-120b",

                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],

                    temperature=0.7,

                    response_format={
                        "type": "json_object"
                    }
                )

                text = response.choices[0].message.content

                data = json.loads(text)

                questions = data.get("questions", [])

                # Kiểm tra đủ số câu
                if len(questions) != batch_size:

                    print(
                        f"Lần {attempt + 1}: "
                        f"AI tạo {len(questions)}/{batch_size} câu"
                    )

                    continue

                # ==================================
                # KIỂM TRA TỪNG CÂU
                # ==================================

                valid = True

                for question in questions:

                    if "question" not in question:
                        valid = False
                        break

                    if "knowledge" not in question:
                        valid = False
                        break

                    if "options" not in question:
                        valid = False
                        break

                    if "answer" not in question:
                        valid = False
                        break

                    if len(question["options"]) != 4:
                        valid = False
                        break

                    if question["answer"] not in [0, 1, 2, 3]:
                        valid = False
                        break

                if valid:
                    return questions

            except Exception as e:

                print(
                    f"Lần {attempt + 1} lỗi:"
                )

                print(e)

                if attempt < 2:
                    time.sleep(3)

        return None

    # ==========================================
    # TẠO ĐỦ SỐ CÂU
    # ==========================================

    all_questions = []

    while len(all_questions) < number_questions:

        remaining = number_questions - len(all_questions)

        # Mỗi lần tối đa 10 câu
        batch_size = min(10, remaining)

        print(
            f"Đang tạo {batch_size} câu..."
        )

        new_questions = generate_questions(
            batch_size,
            all_questions
        )

        # Nếu AI không tạo được
        if new_questions is None:

            return f"""
            <div style="font-family:Arial; padding:40px">

                <h2>
                    AI không thể tạo đủ câu hỏi
                </h2>

                <p>
                    Đã tạo được:
                    {len(all_questions)}/{number_questions}
                    câu
                </p>

                <p>
                    Vui lòng thử lại.
                </p>

                <a href="/">
                    Quay lại tạo bài
                </a>

            </div>
            """

        all_questions.extend(new_questions)

    # ==========================================
    # CẮT ĐÚNG SỐ CÂU YÊU CẦU
    # ==========================================

    questions = all_questions[:number_questions]

    # ==========================================
    # KIỂM TRA CUỐI CÙNG
    # ==========================================

    if len(questions) != number_questions:

        return f"""
        <div style="font-family:Arial; padding:40px">

            <h2>
                Không thể tạo đủ số câu hỏi
            </h2>

            <p>
                Yêu cầu: {number_questions} câu
            </p>

            <p>
                Đã tạo: {len(questions)} câu
            </p>

            <a href="/">
                Quay lại tạo bài
            </a>

        </div>
        """

    # ==========================================
    # LƯU SESSION
    # ==========================================

    session["questions"] = questions
    session["subject"] = subject
    session["difficulty"] = difficulty
    session["knowledge_type"] = knowledge_type

    return render_template(
        "quiz.html",
        questions=questions,
        subject=subject,
        difficulty=difficulty
    )

@app.route("/submit-quiz", methods=["POST"])
def submit_quiz():

    questions = session.get("questions", [])
    subject = session.get("subject", "")
    knowledge_type = session.get("knowledge_type", "")

    if not questions:
        return """
        <div style="font-family:Arial; padding:40px">
            <h2>Không tìm thấy bài kiểm tra</h2>
            <p>Có thể phiên làm bài đã hết.</p>
            <a href="/">Tạo bài kiểm tra mới</a>
        </div>
        """

    correct = 0
    details = []

    for i, question in enumerate(questions):

        user_answer = request.form.get(f"question{i}")
        correct_answer = question["answer"]

        is_correct = False

        if user_answer is not None:
            try:
                user_answer_number = int(user_answer)

                if user_answer_number == correct_answer:
                    is_correct = True
                    correct += 1

            except ValueError:
                is_correct = False

        if user_answer is not None:
            try:
                user_answer_number = int(user_answer)
                user_answer_text = question["options"][user_answer_number]

            except (ValueError, IndexError):
                user_answer_text = "Không hợp lệ"

        else:
            user_answer_text = "Chưa trả lời"

        correct_answer_text = question["options"][correct_answer]

        details.append({
            "question": question["question"],
            "knowledge": question.get("knowledge", knowledge_type),
            "user_answer": user_answer_text,
            "correct_answer": correct_answer_text,
            "is_correct": is_correct
    })

    total = len(questions)

    score = round(correct / total * 10,2)

    # ==============================
    # LƯU KẾT QUẢ VÀO DATABASE
    # ==============================

    conn = get_connection()

    cursor = conn.execute("""
        INSERT INTO quiz_results
        (subject, knowledge_type, score, correct, total)
        VALUES (?, ?, ?, ?, ?)
    """, (
        subject,
        knowledge_type,
        score,
        correct,
        total
    ))

    quiz_id = cursor.lastrowid

    # Lưu kết quả từng câu
    for item in details:
        conn.execute("""
            INSERT INTO question_results
            (quiz_id, knowledge, question, is_correct)
            VALUES (?, ?, ?, ?)
        """, (
            quiz_id,
            knowledge_type,
            item["question"],
            1 if item["is_correct"] else 0
        ))

    conn.commit()
    conn.close()


    # =========================
    # AI PHÂN TÍCH NGẦM
    # =========================

    prompt = f"""
Hãy nhận xét bài kiểm tra của học sinh bằng tiếng Việt.
Gọi học sinh là bạn.
Môn học: {subject}
Loại kiến thức: {knowledge_type}
Điểm: {score}/10
Số câu đúng: {correct}/{total}

Chi tiết bài làm:

{json.dumps(details, ensure_ascii=False, indent=2)}

Hãy nhận xét theo các nội dung:

1. Nhận xét tổng quan
2. Kiến thức học sinh làm tốt
3. Kiến thức còn yếu hoặc dễ nhầm
4. Nội dung cần ôn lại
5. Đề xuất cách học tiếp theo

YÊU CẦU:

- Tất cả nội dung phải bằng tiếng Việt.
- Viết rõ ràng, dễ hiểu.
- Mỗi ý xuống dòng riêng.
- Không tạo bảng Markdown.
- Không sử dụng ký hiệu |.
- Không sử dụng **.
"""

    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.7
        )

        analysis = response.choices[0].message.content

        # Xóa Markdown nếu AI lỡ tạo
        analysis = analysis.replace("**", "")

    except Exception as e:

        print("Lỗi AI:", e)

        analysis = "Không thể tạo nhận xét AI lúc này."

    # =========================
    # LƯU KẾT QUẢ
    # =========================

    session["result_details"] = details
    session["result_correct"] = correct
    session["result_total"] = total
    session["result_score"] = score
    session["ai_analysis"] = analysis
    # LƯU NHẬN XÉT AI
    session["ai_analysis"] = analysis

    return render_template(
        "result.html",
        subject=subject,
        correct=correct,
        total=total,
        score=score,
        details=details
    )
@app.route("/ai-review")
def ai_review():

    analysis = session.get("ai_analysis","Chưa có nhận xét AI.")

    subject = session.get("subject","")

    score = session.get("result_score", 0)

    return render_template(
        "ai_review.html",
        analysis=analysis,
        subject=subject,
        score=score
    )
@app.route("/knowledge")
def knowledge():

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            knowledge,
            COUNT(*) AS total_questions,
            SUM(is_correct) AS correct_questions
        FROM question_results
        GROUP BY knowledge
        ORDER BY knowledge
    """).fetchall()

    conn.close()

    knowledge_data = []

    for row in rows:

        total = row["total_questions"]
        correct = row["correct_questions"]

        percentage = round(correct / total * 100, 1)

        knowledge_data.append({
            "knowledge": row["knowledge"],
            "total": total,
            "correct": correct,
            "percentage": percentage
        })

    return render_template(
        "knowledge.html",
        knowledge_data=knowledge_data
    )
@app.route("/knowledge-ai")
def knowledge_ai():

    conn = get_connection()

    rows = conn.execute("""
        SELECT
            knowledge,
            COUNT(*) AS total_questions,
            SUM(is_correct) AS correct_questions
        FROM question_results
        GROUP BY knowledge
        ORDER BY knowledge
    """).fetchall()

    conn.close()

    if not rows:
        return "Chưa có dữ liệu để AI phân tích."

    data = []

    for row in rows:

        total = row["total_questions"]
        correct = row["correct_questions"]

        percentage = round(correct / total * 100, 1)

        data.append({
            "knowledge": row["knowledge"],
            "total": total,
            "correct": correct,
            "percentage": percentage
        })

    prompt = f"""
Bạn là giáo viên phân tích quá trình học tập của học sinh.

Gọi học sinh là bạn.

Dưới đây là kết quả của học sinh qua nhiều bài kiểm tra:

{json.dumps(data, ensure_ascii=False, indent=2)}

Hãy phân tích từng kiến thức.

Với mỗi kiến thức hãy cho biết:

1. Mức độ nắm kiến thức.
2. Kết quả qua nhiều bài kiểm tra.
3. Kiến thức nào đang yếu.
4. Kiến thức nào đang tiến bộ hoặc ổn định.
5. Học sinh nên ôn tập gì tiếp theo.

YÊU CẦU:

- Viết hoàn toàn bằng tiếng Việt.
- Dễ hiểu.
- Nhận xét dựa trên dữ liệu được cung cấp.
- Không bịa thêm kết quả.
- Không sử dụng bảng Markdown.
- Không sử dụng ký hiệu **.
- Mỗi kiến thức nên được trình bày riêng.
"""

    try:

        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7
        )

        analysis = response.choices[0].message.content

        analysis = analysis.replace("**", "")

    except Exception as e:

        print("Lỗi AI:", e)

        analysis = "Không thể tạo phân tích AI lúc này."

    return render_template(
        "knowledge_ai.html",
        analysis=analysis
    )
if __name__ == "__main__":
    create_tables()
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True, use_reloader=False)