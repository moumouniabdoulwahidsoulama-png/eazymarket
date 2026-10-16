from django.shortcuts import redirect
from django.urls import reverse

from .utils import set_country


def choose_country(request, code):
    """Change le pays affiché et revient sur la page précédente."""
    set_country(request, code)
    return redirect(request.META.get("HTTP_REFERER") or reverse("home"))
