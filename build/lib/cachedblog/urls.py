from django.urls import path

from . import views

app_name = "cachedblog"

# API endpoints (called by aiblog)
api_urlpatterns = [
    path("api/push/", views.api_push, name="api_push"),
    path("api/bulk-push/", views.api_bulk_push, name="api_bulk_push"),
    path("api/delete/", views.api_delete, name="api_delete"),
    path("api/hashes/", views.api_hashes, name="api_hashes"),
]

# i18n-aware — include inside i18n_patterns in your project
i18n_urlpatterns = [
    path("blog/", views.blog_list, name="blog_list"),
]

# Slug-based detail — include as catch-all (last in urlpatterns)
detail_urlpatterns = [
    path("<slug:slug>/", views.blog_detail, name="blog_detail"),
]

# Default: only API (backward compatible)
urlpatterns = api_urlpatterns
