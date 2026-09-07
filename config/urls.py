from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Administração Rastro PJ"
admin.site.site_title = "Rastro PJ"
admin.site.index_title = "Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("conta/", include("django.contrib.auth.urls")),
    path("", include("apps.portal.urls")),
]
