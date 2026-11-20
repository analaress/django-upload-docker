from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("admin/", admin.site.urls), path("", include("envios.urls"))]

handler404 = "config.views.erro_404"
handler500 = "config.views.erro_500"
