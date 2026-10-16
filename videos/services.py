"""Ajout et contrôle des vidéos.

Toute la logique est ici pour qu'une vidéo passe exactement les mêmes
contrôles, qu'elle vienne du tableau de bord vendeur ou de l'atelier artisan.
"""

import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from .duree import duree_en_secondes
from .liens import identifier
from .models import Video

logger = logging.getLogger("videos")

EXTENSIONS = (".mp4", ".m4v", ".mov", ".webm")


def _conf():
    return settings.EAZYMARKET


def emplacements(user):
    """Combien de vidéos hébergées cet utilisateur peut encore publier.

    Renvoie un dictionnaire prêt pour l'affichage. `restants = None` signifie
    « aucune limite » (boutique officielle, administrateur).
    """
    profil = getattr(user, "profile", None)
    utilises = Video.objects.hebergees().filter(owner=user).count()

    illimite = bool(
        user.is_staff
        or (profil and (profil.unlimited_slots or profil.is_official))
    )
    if illimite:
        return {"utilises": utilises, "total": None, "restants": None, "illimite": True}

    total = _conf()["VIDEO_FREE_SLOTS"] + (profil.extra_video_slots if profil else 0)
    return {
        "utilises": utilises,
        "total": total,
        "restants": max(0, total - utilises),
        "illimite": False,
        "gratuits": _conf()["VIDEO_FREE_SLOTS"],
        "pack_taille": _conf()["VIDEO_PACK_SIZE"],
        "pack_prix": _conf()["VIDEO_PACK_PRICE"],
    }


def _verifier_le_fichier(fichier):
    """Contrôles serveur. Le navigateur en fait déjà une partie, mais on ne
    fait jamais confiance à ce qui arrive du navigateur."""
    conf = _conf()
    nom = (fichier.name or "").lower()

    if not nom.endswith(EXTENSIONS):
        raise ValidationError(
            "Format non accepté. Envoyez une vidéo MP4 (c'est ce que filment "
            "tous les téléphones) ou MOV."
        )

    maxi = conf["VIDEO_MAX_MB"] * 1024 * 1024
    if fichier.size > maxi:
        raise ValidationError(
            f"Vidéo trop lourde : {fichier.size / (1024 * 1024):.0f} Mo pour "
            f"{conf['VIDEO_MAX_MB']} Mo autorisés. Filmez plus court, ou "
            "réglez votre appareil photo sur une qualité plus basse."
        )

    duree = duree_en_secondes(fichier)
    if duree > conf["VIDEO_MAX_SECONDS"]:
        raise ValidationError(
            f"Vidéo trop longue : {duree} secondes pour "
            f"{conf['VIDEO_MAX_SECONDS']} autorisées. Quelques secondes qui "
            "font le tour de l'article suffisent — c'est même plus regardé."
        )
    return duree


def ajouter_video(user, cible, *, fichier=None, lien="", titre=""):
    """Ajoute une vidéo à un produit ou à un artisan.

    Lève ValidationError avec un message directement affichable au vendeur.
    """
    conf = _conf()
    lien = (lien or "").strip()

    if not fichier and not lien:
        raise ValidationError("Choisissez un fichier vidéo, ou collez un lien TikTok / YouTube.")

    deja = Video.objects.filter(
        content_type=ContentType.objects.get_for_model(cible), object_id=cible.pk
    ).count()
    if deja >= conf["VIDEO_MAX_PAR_FICHE"]:
        raise ValidationError(
            f"Cette fiche a déjà {conf['VIDEO_MAX_PAR_FICHE']} vidéos. "
            "Supprimez-en une pour en ajouter une autre."
        )

    duree = 0
    taille = 0

    if fichier:
        etat = emplacements(user)
        if not etat["illimite"] and etat["restants"] <= 0:
            raise ValidationError(
                f"Vos {etat['total']} emplacements vidéo sont occupés. "
                f"Vous pouvez supprimer une ancienne vidéo, acheter "
                f"{conf['VIDEO_PACK_SIZE']} emplacements pour "
                f"{conf['VIDEO_PACK_PRICE']} FCFA, ou coller un lien "
                "TikTok / YouTube — les liens sont gratuits et sans limite."
            )
        duree = _verifier_le_fichier(fichier)
        taille = fichier.size
        lien = ""
    else:
        if not identifier(lien):
            raise ValidationError(
                "Lien non reconnu. Collez l'adresse d'une vidéo TikTok, YouTube, "
                "Facebook ou Instagram."
            )

    video = Video.objects.create(
        owner=user,
        content_type=ContentType.objects.get_for_model(cible),
        object_id=cible.pk,
        file=fichier or "",
        external_url=lien,
        title=(titre or "").strip()[:120],
        duration=duree,
        size=taille,
    )
    logger.info(
        "Vidéo %s ajoutée par %s (%s)", video.pk, user, "fichier" if fichier else "lien"
    )
    return video
