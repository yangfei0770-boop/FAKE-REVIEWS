import os
import threading
from pathlib import Path

# Load .env if present
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from flask import Flask, render_template, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from database import init_db, save_article, get_articles, get_article, save_example
from crawler import crawl, fetch_x_comments
from corrector import correct

app = Flask(__name__)

# ── Crawl job ─────────────────────────────────────────────────────────────────

def run_crawl():
    print("[crawl] Starting...")
    articles = crawl(max_articles=10)
    for a in articles:
        result = correct(a["content"], a["x_comments"])
        save_article(
            url=a["url"], title=a["title"], content=a["content"],
            source=a["source"], lang="en",
            bluesky_comments=a.get("x_comments", ""),
            fake_review=result["fake_review"],
            correction=result["correction"],
            fake_review_zh=result.get("fake_review_zh", ""),
            correction_zh=result.get("correction_zh", ""),
        )
    print(f"[crawl] Done — {len(articles)} articles saved.")

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    articles = get_articles(limit=40)
    return render_template("index.html", articles=articles)

@app.route("/article/<int:article_id>")
def article_detail(article_id):
    a = get_article(article_id)
    return jsonify(a) if a else ("Not found", 404)

@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.json
    news = data.get("news", "").strip()
    if not news:
        return jsonify({"error": "Missing news content"}), 400
    x_comments = fetch_x_comments(news[:80])
    result = correct(news, x_comments)
    return jsonify(result)

@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.json
    save_example(
        lang="en",
        wrong=data.get("wrong", ""),
        correct=data.get("correct", ""),
        reason=data.get("reason", ""),
    )
    return jsonify({"ok": True})

@app.route("/crawl", methods=["POST"])
def trigger_crawl():
    threading.Thread(target=run_crawl, daemon=True).start()
    return jsonify({"ok": True})

# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_crawl, "interval", hours=6)
    scheduler.start()
    threading.Thread(target=run_crawl, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
