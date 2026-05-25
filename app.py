import threading
from pathlib import Path
# Load .env if present
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            import os; os.environ.setdefault(k.strip(), v.strip())
from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from database import init_db, save_article, get_articles, get_article, save_example
from crawler import crawl
from corrector import correct

app = Flask(__name__)

# ── Background crawl job ──────────────────────────────────────────────────────

def run_crawl(lang="en"):
    print(f"[crawl] Starting {lang}...")
    articles = crawl(lang=lang, max_articles=5)
    for a in articles:
        print(f"[crawl] Processing: {a['title'][:60]}")
        result = correct(a["content"], a["x_comments"], lang=lang)
        save_article(
            url=a["url"],
            title=a["title"],
            content=a["content"],
            source=a["source"],
            lang=lang,
            bluesky_comments=a.get("x_comments", ""),
            fake_review=result["fake_review"],
            correction=result["correction"],
        )
    print(f"[crawl] Done {lang}, {len(articles)} articles.")

def crawl_all():
    threading.Thread(target=run_crawl, args=("en",), daemon=True).start()
    threading.Thread(target=run_crawl, args=("zh",), daemon=True).start()

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    lang = request.args.get("lang", "all")
    articles = get_articles(lang=lang if lang != "all" else None, limit=30)
    return render_template("index.html", articles=articles, lang=lang)

@app.route("/article/<int:article_id>")
def article(article_id):
    a = get_article(article_id)
    if not a:
        return "Not found", 404
    return render_template("article.html", article=a)

@app.route("/analyze", methods=["POST"])
def analyze():
    """Manual submission"""
    data = request.json
    news = data.get("news", "").strip()
    lang = data.get("lang", "en")
    if not news:
        return jsonify({"error": "Missing news"}), 400
    from crawler import fetch_x_comments
    x_comments = fetch_x_comments(news[:80], max_results=10)
    result = correct(news, x_comments, lang)
    return jsonify(result)

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    save_example(
        lang=data.get("lang", "en"),
        wrong=data.get("wrong", ""),
        correct=data.get("correct", ""),
        reason=data.get("reason", ""),
    )
    return jsonify({"ok": True})

@app.route("/crawl", methods=["POST"])
def trigger_crawl():
    """Manually trigger crawl"""
    threading.Thread(target=crawl_all, daemon=True).start()
    return jsonify({"ok": True, "message": "Crawl started"})

# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    scheduler = BackgroundScheduler()
    scheduler.add_job(crawl_all, "interval", hours=6, id="crawl")
    scheduler.start()

    # Initial crawl on startup
    threading.Thread(target=crawl_all, daemon=True).start()

    app.run(debug=False, port=5000)
