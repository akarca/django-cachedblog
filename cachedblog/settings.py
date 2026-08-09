"""
Default settings for cachedblog app.

Override in your project's settings.py:

    CACHEDBLOG_TEMPLATE = "myapp/blog_detail.html"
    CACHEDBLOG_LIST_TEMPLATE = "myapp/blog_list.html"
    CACHEDBLOG_API_TOKEN = "your-secret-token"       # token for incoming push requests
    CACHEDBLOG_CACHE_ALIAS = "default"
    CACHEDBLOG_CACHE_TIMEOUT = None                   # None = forever

    # aiblog source (for fetching listing data)
    CACHEDBLOG_SOURCE_URL = "https://aiblog.nameocean.org"
    CACHEDBLOG_SOURCE_SITE = "techsciverse"           # site slug on aiblog
    CACHEDBLOG_SOURCE_TOKEN = "aiblog-api-token"      # Site.api_token on aiblog
    CACHEDBLOG_LIST_ITEMS = 10                        # items per page

    # Minimum seconds between two full listing refreshes (0 = no throttling)
    CACHEDBLOG_REFRESH_MIN_INTERVAL = 900
"""

from django.conf import settings

TEMPLATE = getattr(settings, "CACHEDBLOG_TEMPLATE", "cachedblog/blog_detail.html")
LIST_TEMPLATE = getattr(settings, "CACHEDBLOG_LIST_TEMPLATE", "cachedblog/blog_list.html")
API_TOKEN = getattr(settings, "CACHEDBLOG_API_TOKEN", "")
CACHE_ALIAS = getattr(settings, "CACHEDBLOG_CACHE_ALIAS", "default")
CACHE_TIMEOUT = getattr(settings, "CACHEDBLOG_CACHE_TIMEOUT", None)

SOURCE_URL = getattr(settings, "CACHEDBLOG_SOURCE_URL", "")
SOURCE_SITE = getattr(settings, "CACHEDBLOG_SOURCE_SITE", "")
SOURCE_TOKEN = getattr(settings, "CACHEDBLOG_SOURCE_TOKEN", "")
LIST_ITEMS = getattr(settings, "CACHEDBLOG_LIST_ITEMS", 10)
REFRESH_MIN_INTERVAL = getattr(settings, "CACHEDBLOG_REFRESH_MIN_INTERVAL", 900)
