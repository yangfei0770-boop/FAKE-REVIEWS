import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ── Bluesky: news source via trending feed ────────────────────────────────────

BLUESKY_FEEDS = [
    "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot",
    "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/hot-classic",
    "at://did:plc:tenurhgjptubkk5zf5qhi3og/app.bsky.feed.generator/catch-up",
    "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/with-friends",
]

def get_bluesky_news(limit: int = 30) -> list[dict]:
    """Fetch trending posts from Bluesky, return those with article links."""
    results = []
    seen = set()

    for feed_uri in BLUESKY_FEEDS:
        try:
            resp = requests.get(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.getFeed",
                params={"feed": feed_uri, "limit": limit},
                timeout=15,
            )
            if not resp.ok:
                continue
            items = resp.json().get("feed", [])
        except Exception as e:
            print(f"Bluesky feed error: {e}")
            continue

        for item in items:
            post = item.get("post", {})
            record = post.get("record", {})
            embed = record.get("embed", {}) or post.get("embed", {})
            if not embed:
                continue
            external = embed.get("external") or embed.get("media", {}).get("external", {})
            if not external:
                continue
            url = external.get("uri", "")
            if not url.startswith("http") or url in seen:
                continue
            seen.add(url)
            results.append({
                "url": url,
                "title": external.get("title", ""),
                "likes": post.get("likeCount", 0),
            })

    results.sort(key=lambda x: x["likes"], reverse=True)
    return results


# ── X comments via DuckDuckGo HTML ────────────────────────────────────────────

def fetch_x_comments(keyword: str, max_results: int = 8) -> str:
    """Search X posts about a topic via DuckDuckGo HTML (no API key needed)."""
    # Try full title first, then stripped-down keyword
    queries = [
        f"site:x.com {keyword}",
        f"site:twitter.com {keyword}",
        f"site:x.com {' '.join(keyword.split()[:5])}",  # first 5 words only
    ]
    for query in queries:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=HEADERS,
                timeout=15,
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            snippets = [el.get_text(strip=True) for el in soup.select(".result__snippet")]
            snippets = [s for s in snippets if len(s) > 30][:max_results]
            if snippets:
                return "\n---\n".join(snippets)
        except Exception as e:
            print(f"X search error ({query[:40]}): {e}")
    return "No X comments found."


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
                text = " ".join(
                    p.get_text(strip=True) for p in paragraphs
                    if len(p.get_text(strip=True)) > 40
                )
                if len(text) > 200:
                    content = text[:3000]
                    break

        if not content or not title:
            return None
        return {"title": title, "content": content, "url": url}
    except Exception as e:
        print(f"Fetch error {url[:60]}: {e}")
        return None


# ── Main crawl ────────────────────────────────────────────────────────────────

def crawl(max_articles: int = 10) -> list[dict]:
    """
    Pull trending news from Bluesky, fetch article content,
    get X comments. Returns list of article dicts.
    """
    from database import url_exists

    posts = get_bluesky_news(limit=50)
    print(f"[crawl] Bluesky returned {len(posts)} posts with links")

    articles = []
    for post in posts:
        url = post["url"]
        if url_exists(url):
            continue

        article = fetch_article(url)
        if not article:
            continue

        keyword = article["title"][:80]
        x_comments = fetch_x_comments(keyword)

        articles.append({
            **article,
            "source": "bluesky",
            "x_comments": x_comments,
        })
        print(f"[crawl] OK: {article['title'][:60]}")

        if len(articles) >= max_articles:
            break

    return articles
