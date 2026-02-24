"""xiaoclaw Web Tools - real web_search and web_fetch implementations"""
import re
import logging
from typing import Dict, List
from urllib.parse import quote_plus

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger("xiaoclaw.Web")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; xiaoclaw/0.2; +https://github.com/upsightx/xiaoclaw)"
}


def web_search(query: str, count: int = 5, **kw) -> str:
    """Search via DuckDuckGo HTML (no API key needed)."""
    if not HAS_REQUESTS:
        return "[Error: requests not installed]"
    if not query.strip():
        return "[Error: empty query]"

    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

        results = []
        # Parse result snippets from DDG HTML
        blocks = re.findall(
            r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'<a class="result__snippet"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL
        )
        for href, title, snippet in blocks[:count]:
            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            if title:
                results.append(f"[{title}]({href})\n{snippet}")

        if not results:
            # Fallback: try extracting any links with text
            links = re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]+)</a>', resp.text)
            for href, title in links[:count]:
                title = title.strip()
                if title and len(title) > 5 and 'duckduckgo' not in href:
                    results.append(f"[{title}]({href})")

        return "\n\n".join(results) if results else f"No results for: {query}"

    except Exception as e:
        logger.error(f"web_search error: {e}")
        return f"[Search error: {e}]"


def web_fetch(url: str, max_chars: int = 8000, **kw) -> str:
    """Fetch a URL and extract readable text content."""
    if not HAS_REQUESTS:
        return "[Error: requests not installed]"
    if not url.strip():
        return "[Error: empty URL]"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        if "json" in content_type:
            return resp.text[:max_chars]

        # HTML → extract text
        text = resp.text
        # Remove script/style
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Decode entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')

        return text[:max_chars] if text else "[Empty page]"

    except Exception as e:
        logger.error(f"web_fetch error: {e}")
        return f"[Fetch error: {e}]"


def test_web():
    """Quick self-test."""
    # Test search
    r = web_search("python programming")
    assert len(r) > 10, f"Search returned too little: {r[:100]}"
    print(f"  ✓ web_search: {len(r)} chars")

    # Test fetch
    r = web_fetch("https://httpbin.org/get")
    assert "origin" in r or "headers" in r, f"Fetch unexpected: {r[:100]}"
    print(f"  ✓ web_fetch: {len(r)} chars")

    print("  ✓ web.py tests passed")


if __name__ == "__main__":
    test_web()
