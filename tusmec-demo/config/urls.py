from django.contrib import admin
from django.urls import include, path

from frontend.views import index, roi_page

urlpatterns = [
    path("", index),
    path("roi", roi_page),
    path("api/", include("api.urls")),
    path("admin/", admin.site.urls),
]
