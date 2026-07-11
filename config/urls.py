from django.contrib import admin
from django.urls import include, path

from frontend.views import index

urlpatterns = [
    path("", index),
    path("api/", include("api.urls")),
    path("admin/", admin.site.urls),
]
