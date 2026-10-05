import sqlite3


DATABASE = "quiz_history.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            knowledge_type TEXT NOT NULL,
            score REAL NOT NULL,
            correct INTEGER NOT NULL,
            total INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS question_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL,
            knowledge TEXT NOT NULL,
            question TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            FOREIGN KEY (quiz_id) REFERENCES quiz_results(id)
        )
    """)

    conn.commit()
    conn.close()