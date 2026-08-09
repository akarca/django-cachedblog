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
        """Return one lightweight entry per cached blog, across all languages.

        Only `slug` and `release_date` are ever read (by location/lastmod), so
        every other field is dropped as each source page is consumed. Keeping
        the full dicts would hold every blog of every language — including the
        rendered HTML of `content` — in memory at once, which costs hundreds of
        MB per sitemap request on a multi-language site.
        """
        items = []
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
                items.extend(
                    {"slug": b.get("slug", ""), "release_date": b.get("release_date", "")}
                    for b in blogs
                )
                if page >= data.get("pages", 1):
                    break
                page += 1
        return items

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
