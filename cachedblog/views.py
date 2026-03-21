import json

from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from . import settings as app_settings
from .cache import get_blog, set_blog, delete_blog, get_list_page


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
    """Serve a single blog post from cache."""
    blog = get_blog(slug)
    if blog is None:
        raise Http404("Blog not found")
    return render(request, app_settings.TEMPLATE, {"blog": blog})


@require_GET
def blog_list(request, lang):
    """
    Paginated blog listing page for a specific language.

    URL: /<lang>/
    Query params:
        page — page number (default 1)
    """
    page = int(request.GET.get("page", 1))
    data = get_list_page(lang, page)
    blogs = data.get("blogs", [])
    total_pages = data.get("pages", 1)

    return render(request, app_settings.LIST_TEMPLATE, {
        "blogs": blogs,
        "lang": lang,
        "page": page,
        "total_pages": total_pages,
        "total": data.get("total", 0),
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page": page - 1,
        "next_page": page + 1,
    })


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
        "social_media_post": "..."
    }

    If same slug exists, it will be overwritten.
    Also bumps list version → listing cache is invalidated.
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
            set_blog(slug, blog_data)
            saved += 1

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
