"""
Cache helpers for blog data.

Two-layer cache:
1. Blog detail  — key: cachedblog:detail:<slug>    — set via push API
2. Blog listing — key: cachedblog:list:<lang>:<page> — fetched from aiblog API
                  key: cachedblog:langs              — set of known languages
                  key: cachedblog:list_pages:<lang>   — max page count per lang

On push/delete, listings for ALL known languages are proactively refreshed
in a background thread — no user request needed to warm the cache.
"""

import hashlib
import json
import logging
import threading
import urllib.request
import urllib.error

import mistune
from django.core.cache import caches

from . import settings as app_settings

_md = mistune.create_markdown()

logger = logging.getLogger("cachedblog")


def _cache():
    return caches[app_settings.CACHE_ALIAS]


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------

def _detail_key(slug):
    return f"cachedblog:detail:{slug}"


def _list_key(lang, page):
    return f"cachedblog:list:{lang}:{page}"


def _langs_key():
    return "cachedblog:langs"


def _list_pages_key(lang):
    return f"cachedblog:list_pages:{lang}"


def _hashes_key():
    return "cachedblog:hashes"


# ---------------------------------------------------------------------------
# Known languages tracking
# ---------------------------------------------------------------------------

def _track_lang(lang):
    """Add lang to the set of known languages."""
    c = _cache()
    raw = c.get(_langs_key())
    langs = set(json.loads(raw)) if raw else set()
    if lang not in langs:
        langs.add(lang)
        c.set(_langs_key(), json.dumps(sorted(langs)), None)


def _get_known_langs():
    """Return set of known languages."""
    raw = _cache().get(_langs_key())
    return set(json.loads(raw)) if raw else set()


def _get_max_pages(lang):
    """Return last known max page count for a language."""
    v = _cache().get(_list_pages_key(lang))
    return int(v) if v else 1


# ---------------------------------------------------------------------------
# Detail cache (individual blog posts)
# ---------------------------------------------------------------------------

def blog_hash(data):
    """Compute md5 hash for a blog dict. Must match aiblog's push.blog_hash()."""
    parts = [
        data.get("slug", ""),
        data.get("title", ""),
        data.get("summary", ""),
        data.get("content", ""),
        data.get("photo_url", ""),
        data.get("lang", ""),
        data.get("release_date", ""),
        json.dumps(data.get("tags", []), sort_keys=True),
        json.dumps(data.get("lang_slugs", {}), sort_keys=True),
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def get_all_hashes():
    """Return {slug: md5_hash} for all cached blogs."""
    raw = _cache().get(_hashes_key())
    if raw is None:
        return {}
    return json.loads(raw) if isinstance(raw, str) else raw


def _update_hash(slug, data):
    """Update the hash for a single blog slug."""
    c = _cache()
    hashes = get_all_hashes()
    hashes[slug] = blog_hash(data)
    c.set(_hashes_key(), json.dumps(hashes), None)  # never expires


def _remove_hash(slug):
    """Remove hash for a deleted slug."""
    c = _cache()
    hashes = get_all_hashes()
    hashes.pop(slug, None)
    c.set(_hashes_key(), json.dumps(hashes), None)


def _render_markdown_fields(data):
    """Render markdown in summary and content fields to HTML (in-place)."""
    summary = data.get("summary")
    if summary and "<p>" not in summary:
        data["summary"] = _md(summary).strip()
    content = data.get("content")
    if content and "<p>" not in content:
        data["content"] = _md(content).strip()
    return data


def get_blog(slug):
    """Return blog dict from cache or None."""
    data = _cache().get(_detail_key(slug))
    if data is None:
        return None
    return json.loads(data) if isinstance(data, str) else data


def set_blog(slug, data, refresh=True):
    """Store blog dict in cache. Triggers background list refresh unless refresh=False."""
    _render_markdown_fields(data)
    _cache().set(
        _detail_key(slug),
        json.dumps(data, ensure_ascii=False),
        app_settings.CACHE_TIMEOUT,
    )
    _update_hash(slug, data)
    lang = data.get("lang")
    if lang:
        _track_lang(lang)
    if refresh:
        _refresh_all_lists_async()


def delete_blog(slug):
    """Remove blog from cache and trigger background list refresh."""
    _cache().delete(_detail_key(slug))
    _remove_hash(slug)
    _refresh_all_lists_async()


# ---------------------------------------------------------------------------
# List cache (paginated blog listing, per language)
# ---------------------------------------------------------------------------

def get_list_page(lang, page=1, tag=None):
    """
    Get paginated blog listing for a specific language.
    Returns from cache — should already be warm from proactive refresh.
    Falls back to source fetch if cold.

    Returns: {"blogs": [...], "page": N, "total": N, "pages": N, "items": N}
    """
    c = _cache()
    cache_key = _list_key(lang, page) if not tag else f"cachedblog:list:{lang}:{tag}:{page}"
    cached_data = c.get(cache_key)

    if cached_data:
        return json.loads(cached_data) if isinstance(cached_data, str) else cached_data

    # Cold cache — fetch from source (first request or after cache eviction)
    _track_lang(lang)
    fresh = _fetch_list_from_source(lang, page, tag=tag)
    if fresh is not None:
        if tag:
            c.set(cache_key, json.dumps(fresh, ensure_ascii=False), app_settings.CACHE_TIMEOUT)
            for blog_data in fresh.get("blogs", []):
                _render_markdown_fields(blog_data)
                slug = blog_data.get("slug")
                if slug:
                    c.set(_detail_key(slug), json.dumps(blog_data, ensure_ascii=False), app_settings.CACHE_TIMEOUT)
            c.set(cache_key, json.dumps(fresh, ensure_ascii=False), app_settings.CACHE_TIMEOUT)
        else:
            _store_list_page(lang, page, fresh)
        return fresh

    return {"blogs": [], "page": page, "total": 0, "pages": 0, "items": app_settings.LIST_ITEMS}


def _store_list_page(lang, page, data):
    """Write a single list page to cache + cache each blog's detail."""
    c = _cache()
    c.set(_list_key(lang, page), json.dumps(data, ensure_ascii=False), app_settings.CACHE_TIMEOUT)
    # Remember max pages for this lang
    total_pages = data.get("pages", 1)
    c.set(_list_pages_key(lang), total_pages, app_settings.CACHE_TIMEOUT)
    # Render markdown and warm detail cache for every blog in the page
    for blog_data in data.get("blogs", []):
        _render_markdown_fields(blog_data)
        slug = blog_data.get("slug")
        if slug:
            c.set(
                _detail_key(slug),
                json.dumps(blog_data, ensure_ascii=False),
                app_settings.CACHE_TIMEOUT,
            )
    # Re-store list page with rendered markdown
    c.set(_list_key(lang, page), json.dumps(data, ensure_ascii=False), app_settings.CACHE_TIMEOUT)


# ---------------------------------------------------------------------------
# Proactive refresh (background thread, deduplicated)
# ---------------------------------------------------------------------------

_refresh_lock = threading.Lock()
_refresh_running = False


def _refresh_all_lists_async():
    """Spawn a background thread to refresh listing cache. Skips if already running."""
    global _refresh_running
    with _refresh_lock:
        if _refresh_running:
            return
        _refresh_running = True
    t = threading.Thread(target=_refresh_all_lists_guarded, daemon=True)
    t.start()


def _refresh_all_lists_guarded():
    """Wrapper that resets the running flag when done."""
    global _refresh_running
    try:
        _refresh_all_lists()
    finally:
        with _refresh_lock:
            _refresh_running = False


def _refresh_all_lists():
    """Fetch fresh listings for every known language, all pages."""
    langs = _get_known_langs()
    if not langs:
        return

    for lang in langs:
        max_pages = _get_max_pages(lang)
        for page in range(1, max_pages + 1):
            try:
                fresh = _fetch_list_from_source(lang, page)
                if fresh is not None:
                    _store_list_page(lang, page, fresh)
                    # Update max_pages in case total changed
                    new_max = fresh.get("pages", 1)
                    if new_max > max_pages:
                        max_pages = new_max
                    logger.info("Refreshed listing cache: lang=%s page=%d/%d", lang, page, max_pages)
                else:
                    logger.warning("Failed to refresh listing: lang=%s page=%d", lang, page)
                    break  # Source down, stop trying this lang
            except Exception as e:
                logger.error("Error refreshing listing lang=%s page=%d: %s", lang, page, e)
                break


# ---------------------------------------------------------------------------
# Source fetch
# ---------------------------------------------------------------------------

def _fetch_list_from_source(lang, page, tag=None):
    """Fetch paginated blog list from aiblog API."""
    base = app_settings.SOURCE_URL.rstrip("/")
    site = app_settings.SOURCE_SITE
    token = app_settings.SOURCE_TOKEN
    items = app_settings.LIST_ITEMS

    if not all([base, site, token]):
        logger.debug("Source not configured, skipping fetch")
        return None

    url = f"{base}/api/blogs/{site}/?lang={lang}&page={page}&items={items}"
    if tag:
        from urllib.parse import quote
        url += f"&tag={quote(tag)}"

    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        logger.error("Failed to fetch from source %s: %s", url, e)
        return None
