import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "news.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT,
                source TEXT,
                lang TEXT DEFAULT 'en',
                bluesky_comments TEXT,
                fake_review TEXT,
                correction TEXT,
                fake_review_zh TEXT,
                correction_zh TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Migrate existing tables
        for col in ["fake_review_zh", "correction_zh"]:
            try:
                conn.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT")
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lang TEXT,
                wrong TEXT,
                correct TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

def save_article(url, title, content, source, lang, bluesky_comments, fake_review, correction, fake_review_zh="", correction_zh=""):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO articles
            (url, title, content, source, lang, bluesky_comments, fake_review, correction, fake_review_zh, correction_zh)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (url, title, content, source, lang, bluesky_comments, fake_review, correction, fake_review_zh, correction_zh))

def url_exists(url):
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM articles WHERE url=?", (url,)).fetchone()
        return row is not None

def get_articles(lang=None, limit=30):
    with get_conn() as conn:
        if lang:
            rows = conn.execute(
                "SELECT * FROM articles WHERE lang=? ORDER BY created_at DESC LIMIT ?",
                (lang, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM articles ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

def get_article(article_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        return dict(row) if row else None

def save_example(lang, wrong, correct, reason=""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO examples (lang, wrong, correct, reason) VALUES (?, ?, ?, ?)",
            (lang, wrong, correct, reason)
        )

def get_examples(lang, limit=5):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM examples WHERE lang=? ORDER BY created_at DESC LIMIT ?",
            (lang, limit)
        ).fetchall()
        return [dict(r) for r in rows]
