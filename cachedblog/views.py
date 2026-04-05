import json

import mistune
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import translation
from django.utils.translation import get_language
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import settings as app_settings
from .cache import delete_blog, get_all_hashes, get_blog, get_list_page, set_blog, _refresh_all_lists_async


def _check_token(request):
    """Validate API token from Authorization header."""
    token = app_settings.API_TOKEN
    if not token:
        return False
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:] == token
    return auth == token


# ---------------------------------------------------------------------------
# Public views
# ---------------------------------------------------------------------------


@require_GET
def blog_detail(request, slug):
    """
    Serve a single blog post from cache.

    - Activates the blog's language via translation.activate()
    - Renders markdown content to HTML
    - Passes lang_slugs for language switcher
    """
    blog = get_blog(slug)
    if blog is None:
        raise Http404("Blog not found")

    lang = blog.get("lang", "en")
    translation.activate(lang)

    # Content is already rendered to HTML in cache layer (_render_markdown_fields)
    # Fallback rendering for any content that wasn't pre-rendered
    content_html = blog.get("content", "")
    if content_html and "<p>" not in content_html:
        md = mistune.create_markdown()
        content_html = md(content_html)

    lang_slugs = blog.get("lang_slugs", {})

    # Parse release_date string to datetime for template |date filter
    release_date = None
    if blog.get("release_date"):
        from django.utils.dateparse import parse_datetime
        release_date = parse_datetime(blog["release_date"])

    return render(request, app_settings.TEMPLATE, {
        "blog": blog,
        "content_html": content_html,
        "release_date": release_date,
        "title": blog.get("title", ""),
        "description": blog.get("summary", ""),
        "lang_slugs": lang_slugs,
        "lang_slugs_json": json.dumps(lang_slugs),
    })


@require_GET
def blog_list(request):
    """
    Paginated blog listing page.

    Language is determined by Django's i18n (URL prefix / session / cookie).
    Include this URL inside i18n_patterns for automatic language detection.

    Query params:
        page — page number (default 1)
    """
    lang = get_language() or "en"
    page = int(request.GET.get("page", 1))
    data = get_list_page(lang, page)
    blogs = data.get("blogs", [])
    total_pages = data.get("pages", 1)

    return render(
        request,
        app_settings.LIST_TEMPLATE,
        {
            "blogs": blogs,
            "lang": lang,
            "page": page,
            "total_pages": total_pages,
            "total": data.get("total", 0),
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "previous_page": page - 1,
            "next_page": page + 1,
        },
    )


# ---------------------------------------------------------------------------
# API endpoints (called by aiblog project)
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def api_push(request):
    """
    Receive blog data from aiblog and store in cache.

    Expected JSON body:
    {
        "slug": "my-blog-post",
        "title": "My Blog Post",
        "summary": "...",
        "content": "...",
        "lang": "en",
        "photo_url": "https://...",
        "release_date": "2025-01-01T00:00:00Z",
        "tags": ["tag1", "tag2"],
        "lang_slugs": {"en": "my-blog-post", "tr": "blog-yazim"},
        "social_media_post": "..."
    }

    If same slug exists, it will be overwritten.
    Triggers background cache refresh for all known languages.
    """
    if not _check_token(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    slug = data.get("slug")
    if not slug:
        return JsonResponse({"error": "slug is required"}, status=400)

    set_blog(slug, data)
    return JsonResponse({"status": "ok", "slug": slug})


@csrf_exempt
@require_POST
def api_bulk_push(request):
    """
    Receive multiple blogs in one request.

    Expected JSON body:
    {
        "blogs": [
            {"slug": "...", "title": "...", ...},
            ...
        ]
    }
    """
    if not _check_token(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    blogs = data.get("blogs", [])
    if not isinstance(blogs, list):
        return JsonResponse({"error": "blogs must be a list"}, status=400)

    saved = 0
    for blog_data in blogs:
        slug = blog_data.get("slug")
        if slug:
            set_blog(slug, blog_data, refresh=False)
            saved += 1

    # Single refresh after all blogs are stored
    if saved:
        _refresh_all_lists_async()

    return JsonResponse({"status": "ok", "saved": saved})


@csrf_exempt
@require_POST
def api_delete(request):
    """
    Delete a blog from cache.

    Expected JSON body:
    {
        "slug": "my-blog-post"
    }
    """
    if not _check_token(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    slug = data.get("slug")
    if not slug:
        return JsonResponse({"error": "slug is required"}, status=400)

    delete_blog(slug)
    return JsonResponse({"status": "ok", "slug": slug})


@require_GET
def api_hashes(request):
    """
    Return md5 hashes for all cached blogs.

    Response: {"hashes": {"slug1": "md5...", "slug2": "md5...", ...}}

    Used by aiblog's push_blogs --site X to diff and push only changed blogs.
    """
    if not _check_token(request):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    return JsonResponse({"hashes": get_all_hashes()})
