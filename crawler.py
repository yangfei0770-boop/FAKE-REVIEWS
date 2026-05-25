import asyncio
import os
import threading
from pathlib import Path

import requests
from bs4 import BeautifulSoup

X_COOKIES_FILE = Path(__file__).parent / "x_cookies.json"
_x_lock = threading.Lock()

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ── Bluesky: news source via trending feed ────────────────────────────────────

BLUESKY_FEEDS = [
    "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot",
    "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/hot-classic",
    "at://did:plc:tenurhgjptubkk5zf5qhi3og/app.bsky.feed.generator/catch-up",
    "at://did:plc:wqowuobffl66jv3zn5bpbhbs/app.bsky.feed.generator/the-algorithm",
    "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/bsky-team",
]

# Keywords that signal relevant content
RELEVANT_KEYWORDS = [
    "politic", "sanction", "war", "election", "government", "congress", "senate",
    "china", "russia", "iran", "taiwan", "ukraine", "nato",
    "women", "gender", "abortion", "rights", "protest",
    "tech", "ai", "chip", "nuclear", "climate", "economy", "inflation",
    "trump", "biden", "court", "supreme", "law", "bill", "vote",
    "killed", "attack", "bomb", "military", "army", "troops",
    "immigrant", "refugee", "border", "detention",
]

SKIP_DOMAINS = [
    "reddit.com", "youtube.com", "spotify.com", "twitch.tv",
    "instagram.com", "tiktok.com", "patreon.com",
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
            title = external.get("title", "")
            if not url.startswith("http") or url in seen:
                continue
            # Skip non-news domains
            if any(d in url for d in SKIP_DOMAINS):
                continue
            # Only keep articles with relevant keywords in title
            title_lower = title.lower()
            post_text = record.get("text", "").lower()
            combined = title_lower + " " + post_text
            if not any(kw in combined for kw in RELEVANT_KEYWORDS):
                continue
            seen.add(url)
            results.append({
                "url": url,
                "title": title,
                "likes": post.get("likeCount", 0),
            })

    results.sort(key=lambda x: x["likes"], reverse=True)
    return results


# ── X (Twitter) search via twikit ─────────────────────────────────────────────

def _fetch_x_tweets(keyword: str, max_results: int = 10) -> list:
    """Search X for recent tweets. Returns list of text strings."""
    username = os.environ.get("X_USERNAME", "")
    email = os.environ.get("X_EMAIL", "")
    password = os.environ.get("X_PASSWORD", "")
    if not (username and password):
        return []

    try:
        from twikit import Client
    except ImportError:
        print("twikit not installed")
        return []

    async def _run():
        client = Client("en-US")
        with _x_lock:
            if X_COOKIES_FILE.exists():
                client.load_cookies(str(X_COOKIES_FILE))
            else:
                await client.login(
                    auth_info_1=username,
                    auth_info_2=email,
                    password=password,
                )
                client.save_cookies(str(X_COOKIES_FILE))

        try:
            tweets = await client.search_tweet(keyword[:100], "Latest", count=25)
        except Exception:
            # Cookies may have expired — re-login once
            X_COOKIES_FILE.unlink(missing_ok=True)
            await client.login(
                auth_info_1=username,
                auth_info_2=email,
                password=password,
            )
            client.save_cookies(str(X_COOKIES_FILE))
            tweets = await client.search_tweet(keyword[:100], "Latest", count=25)

        snippets = []
        for t in tweets:
            text = t.text.strip()
            # skip retweets and very short posts
            if len(text) > 40 and not text.startswith("RT @"):
                snippets.append(text)
        return snippets[:max_results]

    try:
        return asyncio.run(_run())
    except Exception as e:
        print(f"X search error: {e}")
        return []


def fetch_social_reactions(keyword: str, max_results: int = 8) -> str:
    """
    Fetch social reactions to a news topic.
    Priority: X (twikit) → Reddit → Bluesky search
    """
    # 1. X via twikit
    snippets = _fetch_x_tweets(keyword, max_results=max_results)
    if snippets:
        print(f"[social] X returned {len(snippets)} tweets")
        return "\n---\n".join(snippets)

    # 2. Reddit (free, no auth)
    try:
        resp = requests.get(
            "https://www.reddit.com/search.json",
            params={"q": keyword[:100], "sort": "new", "limit": 15, "type": "comment,link"},
            headers={**HEADERS, "User-Agent": "news-corrector/1.0"},
            timeout=12,
        )
        if resp.ok:
            children = resp.json().get("data", {}).get("children", [])
            snippets = []
            for c in children:
                d = c.get("data", {})
                text = d.get("body") or d.get("selftext") or d.get("title") or ""
                text = text.strip()
                if len(text) > 40 and len(text) < 600:
                    snippets.append(text)
            if snippets:
                print(f"[social] Reddit returned {len(snippets)} posts")
                return "\n---\n".join(snippets[:max_results])
    except Exception as e:
        print(f"Reddit search error: {e}")

    # 3. Bluesky search (sort=latest, no auth)
    try:
        resp = requests.get(
            "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
            params={"q": keyword[:80], "limit": 10, "sort": "latest"},
            timeout=10,
        )
        if resp.ok:
            posts = resp.json().get("posts", [])
            snippets = [p.get("record", {}).get("text", "").strip() for p in posts]
            snippets = [s for s in snippets if len(s) > 30][:max_results]
            if snippets:
                print(f"[social] Bluesky returned {len(snippets)} posts")
                return "\n---\n".join(snippets)
    except Exception as e:
        print(f"Bluesky fallback error: {e}")

    return ""


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
        x_comments = fetch_social_reactions(keyword)

        articles.append({
            **article,
            "source": "bluesky",
            "x_comments": x_comments,
        })
        print(f"[crawl] OK: {article['title'][:60]}")

        if len(articles) >= max_articles:
            break

    return articles
