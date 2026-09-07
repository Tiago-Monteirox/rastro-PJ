from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.cartography.services.queries import (
    MapQueryError,
    bootstrap_payload,
    location_details_payload,
    locations_payload,
    map_page_context,
)
from apps.registry.cnpj import parse_cnpj_basic
from apps.registry.models import Company

from .models import Watchlist
from .services import (
    company_detail_context,
    dashboard_context,
    event_list_context,
    import_list_context,
    search_company_context,
    watchlist_context,
)


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable", "database": "error"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


@require_GET
def home(request):
    return render(request, "portal/home.html", dashboard_context(request.GET))


def company_search(request):
    return render(
        request,
        "portal/company_search.html",
        search_company_context(request.GET.get("q", ""), request.GET),
    )


def company_detail(request, cnpj_basic):
    return render(
        request,
        "portal/company_detail.html",
        company_detail_context(cnpj_basic, request.user),
    )


def event_list(request):
    filters = {
        key: request.GET.get(key, "").strip()
        for key in ("event_type", "entity_type", "competence", "cnpj")
    }
    return render(request, "portal/event_list.html", event_list_context(filters))


@login_required
def import_list(request):
    return render(request, "portal/import_list.html", import_list_context())


@login_required
def watchlist_list(request):
    return render(
        request,
        "portal/watchlist.html",
        watchlist_context(request.user, request.GET.get("q", "")),
    )


@login_required
@require_POST
def watchlist_toggle(request, cnpj_basic):
    company = get_object_or_404(Company, cnpj_basic=parse_cnpj_basic(cnpj_basic) or "")
    if request.POST.get("action") == "remove":
        Watchlist.objects.filter(user=request.user, company=company).delete()
    else:
        Watchlist.objects.get_or_create(user=request.user, company=company)
    if request.POST.get("return_to") == "watchlist":
        return redirect("portal:watchlist")
    return redirect("portal:company-detail", cnpj_basic=company.cnpj_basic)


@login_required
@require_GET
def establishment_map(request):
    context = map_page_context()
    configured_token = settings.MAPBOX_PUBLIC_TOKEN.strip()
    public_token = configured_token if configured_token.startswith("pk.") else ""
    initial_payload = None
    page_error = ""
    if context["projection"] is not None:
        try:
            initial_payload = bootstrap_payload(request.GET)
        except MapQueryError as exc:
            page_error = str(exc)
            initial_payload = bootstrap_payload({})
    context.update(
        {
            "mapbox_public_token": public_token,
            "mapbox_token_invalid": bool(configured_token and not public_token),
            "mapbox_style_url": settings.MAPBOX_STYLE_URL,
            "initial_payload": initial_payload,
            "page_error": page_error,
        }
    )
    return render(request, "portal/establishment_map.html", context)


@login_required
@require_GET
def map_bootstrap(request):
    return _map_json_response(bootstrap_payload, request.GET)


@login_required
@require_GET
def map_locations(request):
    return _map_json_response(locations_payload, request.GET)


@login_required
@require_GET
def map_location_details(request):
    return _map_json_response(location_details_payload, request.GET)


def _map_json_response(provider, filters):
    try:
        return JsonResponse(provider(filters))
    except MapQueryError as exc:
        status = 503 if "ainda não foi preparada" in str(exc) else 400
        return JsonResponse({"error": str(exc)}, status=status)
