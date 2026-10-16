"""
Envoi des notifications, tous canaux.

Une seule fonction à appeler dans le reste de l'application : `notifier()`.
Elle écrit la notification dans l'application, et pour ce qui est urgent
— une commande à confirmer, un paiement reçu — envoie aussi un SMS.

L'e-mail n'est jamais le canal principal : au Burkina Faso, un commerçant
lit ses SMS, pas sa boîte mail.
"""

import logging

from django.conf import settings

from .models import Notification
from .providers import get_sms_provider

logger = logging.getLogger("notifications")


def _numero_de(user):
    profil = getattr(user, "profile", None)
    if profil is None:
        return ""
    return (profil.whatsapp or profil.phone or "").strip()


def notifier(user, titre, message, lien="", urgent=False, sms_texte=None):
    """Notifie un utilisateur. Retourne la Notification créée.

    urgent=True déclenche l'envoi d'un SMS si un fournisseur est configuré
    et si l'utilisateur a un numéro.
    """
    notification = Notification.objects.create(
        user=user, title=titre, message=message, link=lien, is_urgent=urgent
    )

    if not urgent or not settings.NOTIFICATIONS.get("SMS_ENABLED", True):
        return notification

    numero = _numero_de(user)
    if not numero:
        notification.sms_detail = "Aucun numéro de téléphone au profil"
        notification.save(update_fields=["sms_detail"])
        return notification

    texte = sms_texte or f"{titre} : {message}"
    if lien:
        base = settings.PAYMENTS.get("PUBLIC_BASE_URL", "").rstrip("/")
        texte = f"{texte} {base}{lien}"

    resultat = get_sms_provider().send(numero, texte)
    notification.sms_status = (
        Notification.Sms.SENT if resultat.ok else Notification.Sms.FAILED
    )
    notification.sms_detail = resultat.message[:250]
    notification.save(update_fields=["sms_status", "sms_detail"])

    if not resultat.ok:
        logger.warning("SMS non délivré à %s : %s", user, resultat.message)
    return notification


def notifier_par_lot(utilisateurs, titre, message, lien="", urgent=False):
    return [notifier(u, titre, message, lien, urgent) for u in utilisateurs]


def alerter_les_admins(titre, message, lien="", sms_texte=None):
    """Prévient les administrateurs qu'une action les attend.

    Pour eux, l'e-mail a du sens : c'est la seule voie qui marche déjà
    aujourd'hui, sans passerelle SMS. Le SMS part en plus dès qu'une
    passerelle est branchée.

    Renvoie le nombre d'administrateurs prévenus.
    """
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail

    base = settings.PAYMENTS.get("PUBLIC_BASE_URL", "").rstrip("/")
    adresse = f"{base}{lien}" if lien else base
    admins = list(get_user_model().objects.filter(is_staff=True, is_active=True))

    for admin in admins:
        notifier(admin, titre, message, lien=lien, urgent=True, sms_texte=sms_texte)

    destinataires = [a.email for a in admins if a.email]
    if destinataires:
        try:
            send_mail(
                subject=f"[{settings.EAZYMARKET['SITE_NAME']}] {titre}",
                message=f"{message}\n\n{adresse}\n",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=destinataires,
                fail_silently=True,
            )
        except Exception:  # noqa: BLE001 — un e-mail perdu ne doit rien casser
            logger.exception("Alerte administrateur non envoyée par e-mail")

    logger.info("Alerte admin : %s (%s destinataire(s))", titre, len(admins))
    return len(admins)
