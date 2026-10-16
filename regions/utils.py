"""Résolution du pays actif pour la requête en cours."""

from .models import Country

SESSION_KEY = "pays"


def current_country(request=None):
    """Pays actif : choix explicite → pays du profil → pays par défaut."""
    country = None

    if request is not None:
        code = request.session.get(SESSION_KEY)
        if code:
            country = Country.objects.filter(code=code, is_active=True).first()

        if country is None:
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated:
                profile = getattr(user, "profile", None)
                if profile is not None and profile.country_id:
                    country = profile.country

    return country or Country.default()


def set_country(request, code):
    country = Country.objects.filter(code=code.upper(), is_active=True).first()
    if country:
        request.session[SESSION_KEY] = country.code
    return country
