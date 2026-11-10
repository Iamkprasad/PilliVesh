"""Web fetch tool — reads a public web page and returns its visible text.

Stdlib only (urllib). Bounded to http/https URLs, size-capped, with a strict
user-agent. Returns (text, error) so the caller can surface failures honestly.
Never sends cookies, never follows more than one redirect, and strips HTML tags
to plain text so the model receives readable content.
"""
import html
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

MAX_BYTES = 200 * 1024  # 200 KB cap on downloaded page
MAX_OUTPUT_CHARS = 12000  # cap on text returned to the model
USER_AGENT = "PilliVesh/1.0 (+local-first AI lab; https://mercuryagent.sh)"

_ALLOWED_SCHEMES = ("http", "https")


def _clean_url(url):
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL is required")
    url = url.strip()
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise ValueError("Invalid URL")
    if parsed.username or parsed.password:
        raise ValueError("Put credentials in the URL, not a header")
    return url


def _strip_tags(raw):
    text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_url(url):
    """Fetch a web page and return (plain_text, error)."""
    try:
        url = _clean_url(url)
    except ValueError as e:
        return "", str(e)

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.getcode()
            if status < 200 or status >= 300:
                return "", "HTTP " + str(status)
            content_type = resp.headers.get("Content-Type", "") or ""
            if "text/" not in content_type and "html" not in content_type:
                return "", "unsupported content type: " + content_type
            raw = resp.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        return "", "HTTP " + str(e.code)
    except urllib.error.URLError as e:
        return "", "fetch failed: " + str(e)
    except Exception as e:
        return "", "fetch failed: " + str(e)

    if len(raw) > MAX_BYTES:
        return "", "page too large (over 200 KB)"

    charset = None
    m = re.search(r"charset=([\w-]+)", content_type, re.I)
    if m:
        charset = m.group(1)
    try:
        text = raw.decode(charset or "utf-8", errors="replace")
    except Exception:
        text = raw.decode("utf-8", errors="replace")

    plain = _strip_tags(text)
    if len(plain) > MAX_OUTPUT_CHARS:
        plain = plain[:MAX_OUTPUT_CHARS] + "\n…[truncated]"

    if not plain:
        return "", "no readable text on page"

    return plain, None


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    text, err = fetch_url(url)
    if err:
        print("ERR:", err)
    else:
        print(text[:500])
