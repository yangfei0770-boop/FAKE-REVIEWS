import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

BSKY_API = "https://public.api.bsky.app/xrpc"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; news-corrector/1.0)"}

SEARCH_QUERIES = {
    "en": ["news politics", "breaking news", "china tech sanctions", "women rights", "war conflict"],
    "zh": ["中国 新闻", "政治 事件", "女性 权利", "科技 制裁", "战争 冲突"],
}

# ── Bluesky: news source ──────────────────────────────────────────────────────

def search_bluesky(query: str, limit: int = 20) -> list[dict]:
    try:
        resp = requests.get(
            f"{BSKY_API}/app.bsky.feed.searchPosts",
            params={"q": query, "limit": limit, "sort": "top"},
            timeout=10,
        )
        resp.raise_for_status()
        posts = resp.json().get("posts", [])
    except Exception as e:
        print(f"Bluesky search error: {e}")
        return []

    results = []
    for post in posts:
        record = post.get("record", {})
        embed = record.get("embed", {}) or post.get("embed", {})
        url = None
        if embed:
            external = embed.get("external") or embed.get("media", {}).get("external", {})
            if external:
                url = external.get("uri")
        if url and url.startswith("http"):
            results.append({"url": url, "likes": post.get("likeCount", 0)})

    results.sort(key=lambda x: x["likes"], reverse=True)
    return results


# ── X: fake review source ─────────────────────────────────────────────────────

def fetch_x_comments(keyword: str, max_results: int = 10) -> str:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(f"site:x.com {keyword}", max_results=max_results):
                snippet = r.get("body", "").strip()
                if snippet:
                    results.append(snippet)
    except Exception as e:
        print(f"X search error: {e}")
    return "\n---\n".join(results) if results else "No X comments found."


# ── Article fetcher ───────────────────────────────────────────────────────────

def fetch_article(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        title = ""
        if soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)
        elif soup.find("title"):
            title = soup.find("title").get_text(strip=True)

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
            tag.decompose()

        content = ""
        for selector in ["article", "main", '[class*="article"]', '[class*="content"]', "body"]:
            el = soup.select_one(selector)
            if el:
                paragraphs = el.find_all("p")
                text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 40)
                if len(text) > 200:
                    content = text[:3000]
                    break

        if not content or not title:
            return None
        return {"title": title, "content": content, "url": url}
    except Exception as e:
        print(f"Fetch error {url}: {e}")
        return None


# ── Main crawl ────────────────────────────────────────────────────────────────

def crawl(lang: str = "en", max_articles: int = 5) -> list[dict]:
    """
    Find news via Bluesky, get fake review comments from X.
    Returns list of {title, content, url, source, lang, x_comments}
    """
    from database import url_exists

    queries = SEARCH_QUERIES.get(lang, SEARCH_QUERIES["en"])
    seen_urls = set()
    articles = []

    for query in queries:
        posts = search_bluesky(query, limit=15)
        for post in posts:
            url = post["url"]
            if url in seen_urls or url_exists(url):
                continue
            seen_urls.add(url)

            article = fetch_article(url)
            if not article:
                continue

            # X comments about this article as fake review source
            x_comments = fetch_x_comments(article["title"][:80], max_results=10)

            articles.append({
                **article,
                "lang": lang,
                "source": "bluesky",
                "x_comments": x_comments,
            })
            print(f"  Crawled: {article['title'][:60]}")

            if len(articles) >= max_articles:
                return articles

    return articles
