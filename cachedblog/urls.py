from django.urls import path

from . import views

app_name = "cachedblog"

urlpatterns = [
    # API (called by aiblog)
    path("api/push/", views.api_push, name="api_push"),
    path("api/bulk-push/", views.api_bulk_push, name="api_bulk_push"),
    path("api/delete/", views.api_delete, name="api_delete"),
    # Public — listing per language, detail by slug
    path("<str:lang>/", views.blog_list, name="blog_list"),
    path("<slug:slug>/", views.blog_detail, name="blog_detail"),
]
