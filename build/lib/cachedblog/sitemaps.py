"""
Sitemap for cached blogs.

Usage in your project's urls.py:

    from django.contrib.sitemaps.views import sitemap
    from cachedblog.sitemaps import CachedBlogSitemap

    sitemaps = {
        "blogs": CachedBlogSitemap,
    }

    urlpatterns = [
        path("sitemap.xml", sitemap, {"sitemaps": sitemaps}),
        # or as a separate sitemap index section:
        path("sitemap-blogs.xml", sitemap, {"sitemaps": {"blogs": CachedBlogSitemap}}),
    ]
"""

from datetime import datetime

from django.contrib.sitemaps import Sitemap
from django.utils import timezone

from .cache import get_list_page, _get_known_langs


class CachedBlogSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        """Return all cached blog dicts across all known languages."""
        all_blogs = []
        langs = _get_known_langs()
        if not langs:
            langs = {"en"}
        for lang in langs:
            page = 1
            while True:
                data = get_list_page(lang, page=page)
                blogs = data.get("blogs", [])
                if not blogs:
                    break
                all_blogs.extend(blogs)
                if page >= data.get("pages", 1):
                    break
                page += 1
        return all_blogs

    def location(self, item):
        return f"/{item.get('slug', '')}/"

    def lastmod(self, item):
        rd = item.get("release_date", "")
        if rd:
            try:
                dt = datetime.fromisoformat(rd)
                if dt.tzinfo is None:
                    dt = timezone.make_aware(dt)
                return dt
            except (ValueError, TypeError):
                pass
        return None
