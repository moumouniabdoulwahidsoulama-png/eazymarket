"""Défenses de la connexion : anti-force-brute et double authentification.

Tout passe par la base (le modèle LogConnexion) : aucune dépendance externe,
et ça fonctionne sur l'hébergement mutualisé sans cache configuré.
"""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

# Réglages, surchargeables dans le .env
MAX_ECHECS = int(getattr(settings, "LOGIN_MAX_ECHECS", 5))
FENETRE_MINUTES = int(getattr(settings, "LOGIN_FENETRE_MINUTES", 15))
BLOCAGE_MINUTES = int(getattr(settings, "LOGIN_BLOCAGE_MINUTES", 15))
CODE_VALIDITE_MINUTES = 10


def adresse_ip(request):
    """IP réelle du visiteur, même derrière le proxy de l'hébergeur."""
    transmis = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if transmis:
        return transmis.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def user_agent(request):
    return request.META.get("HTTP_USER_AGENT", "")[:300]


def journaliser(request, identifiant, succes, utilisateur=None):
    from .models import LogConnexion

    LogConnexion.objects.create(
        utilisateur=utilisateur,
        identifiant_saisi=identifiant[:254],
        adresse_ip=adresse_ip(request),
        user_agent=user_agent(request),
        succes=succes,
    )


def echecs_recents(ip):
    from .models import LogConnexion

    depuis = timezone.now() - timedelta(minutes=FENETRE_MINUTES)
    return LogConnexion.objects.filter(
        adresse_ip=ip, succes=False, date__gte=depuis
    ).count()


def est_bloque(request):
    """True si cette IP a trop échoué récemment.

    On regarde la dernière tentative : le blocage dure BLOCAGE_MINUTES après
    le dernier échec, pas indéfiniment.
    """
    from .models import LogConnexion

    ip = adresse_ip(request)
    if echecs_recents(ip) < MAX_ECHECS:
        return False, 0

    derniere = (
        LogConnexion.objects.filter(adresse_ip=ip, succes=False)
        .order_by("-date").first()
    )
    if not derniere:
        return False, 0

    fin = derniere.date + timedelta(minutes=BLOCAGE_MINUTES)
    reste = fin - timezone.now()
    if reste.total_seconds() <= 0:
        return False, 0
    return True, int(reste.total_seconds() // 60) + 1


# ---------------------------------------------------------------------
# Double authentification : code à usage unique
# ---------------------------------------------------------------------
def _empreinte(code):
    """On ne garde jamais le code en clair dans la session."""
    return hashlib.sha256(f"{settings.SECRET_KEY}:{code}".encode()).hexdigest()


def generer_code():
    return f"{secrets.randbelow(1000000):06d}"


def envoyer_code(user):
    """Crée un code, l'envoie, et renvoie ce qu'il faut stocker en session.

    Renvoie (empreinte, expiration_iso, canal) ou None si aucun canal
    d'envoi n'est disponible (ni e-mail ni numéro).
    """
    from notifications.services import notifier

    profil = getattr(user, "profile", None)
    canal = getattr(profil, "two_factor_channel", "email")

    if canal == "email" and not user.email:
        canal = "sms"
    if canal == "sms" and not (profil and (profil.whatsapp or profil.phone)):
        canal = "email" if user.email else None
    if canal is None:
        return None

    code = generer_code()
    message = (
        f"Votre code de connexion {settings.EAZYMARKET['SITE_NAME']} : {code}. "
        f"Valable {CODE_VALIDITE_MINUTES} minutes. Ne le communiquez à personne."
    )

    if canal == "email" and user.email:
        from django.core.mail import send_mail
        try:
            send_mail(
                f"Code de connexion {settings.EAZYMARKET['SITE_NAME']}",
                message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=True,
            )
        except Exception:  # noqa: BLE001
            pass
    else:
        # Passe par le SMS quand une passerelle est branchée ; sinon le
        # message est au moins tracé dans les notifications de l'utilisateur.
        notifier(user, "Code de connexion", message, urgent=True, sms_texte=message)

    expiration = timezone.now() + timedelta(minutes=CODE_VALIDITE_MINUTES)
    return _empreinte(code), expiration.isoformat(), canal


def code_valide(code_saisi, empreinte, expiration_iso):
    from django.utils.dateparse import parse_datetime

    if not empreinte or not expiration_iso:
        return False
    expiration = parse_datetime(expiration_iso)
    if expiration and timezone.now() > expiration:
        return False
    return secrets.compare_digest(_empreinte(code_saisi.strip()), empreinte)
