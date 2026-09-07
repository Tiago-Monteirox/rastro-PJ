from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.home, name="home"),
    path("empresas/", views.company_search, name="company-search"),
    path("empresas/<str:cnpj_basic>/", views.company_detail, name="company-detail"),
    path("eventos/", views.event_list, name="event-list"),
    path("importacoes/", views.import_list, name="import-list"),
    path("monitoradas/", views.watchlist_list, name="watchlist"),
    path("mapa/", views.establishment_map, name="establishment-map"),
    path("mapa/api/resumo/", views.map_bootstrap, name="map-bootstrap"),
    path("mapa/api/localizacoes/", views.map_locations, name="map-locations"),
    path(
        "mapa/api/estabelecimentos/",
        views.map_location_details,
        name="map-location-details",
    ),
    path(
        "monitoradas/<str:cnpj_basic>/",
        views.watchlist_toggle,
        name="watchlist-toggle",
    ),
    path(
        "entrar/",
        auth_views.LoginView.as_view(template_name="portal/login.html"),
        name="login",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("health/", views.health, name="health"),
]
