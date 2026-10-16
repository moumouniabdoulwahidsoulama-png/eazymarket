"""Reconnaissance des liens vidéo externes (TikTok, YouTube, etc.).

Un vendeur qui filme déjà pour TikTok ne devrait pas avoir à réenvoyer son
fichier : il colle son lien. Cela ne coûte ni disque ni bande passante à la
plateforme, donc ces vidéos-là ne consomment aucun emplacement payant.
"""

import re
from urllib.parse import parse_qs, urlparse

# Seules ces plateformes sont acceptées : cela évite qu'un lien serve à
# emmener les visiteurs vers n'importe quoi.
PLATEFORMES = {
    "youtube": {"nom": "YouTube", "icone": "fa-youtube", "hotes": (
        "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")},
    "tiktok": {"nom": "TikTok", "icone": "fa-tiktok", "hotes": (
        "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "m.tiktok.com")},
    "facebook": {"nom": "Facebook", "icone": "fa-facebook", "hotes": (
        "facebook.com", "www.facebook.com", "fb.watch", "web.facebook.com")},
    "instagram": {"nom": "Instagram", "icone": "fa-instagram", "hotes": (
        "instagram.com", "www.instagram.com")},
}


def identifier(url):
    """Renvoie la clé de plateforme d'un lien, ou "" s'il n'est pas accepté."""
    if not url:
        return ""
    try:
        hote = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    for cle, infos in PLATEFORMES.items():
        if hote in infos["hotes"]:
            return cle
    return ""


def _id_youtube(url):
    decoupe = urlparse(url)
    if decoupe.hostname and decoupe.hostname.endswith("youtu.be"):
        return decoupe.path.lstrip("/").split("/")[0]
    if decoupe.path.startswith("/shorts/"):
        return decoupe.path.split("/shorts/")[1].split("/")[0]
    if decoupe.path.startswith("/embed/"):
        return decoupe.path.split("/embed/")[1].split("/")[0]
    return (parse_qs(decoupe.query).get("v") or [""])[0]


def _id_tiktok(url):
    trouve = re.search(r"/video/(\d+)", url)
    return trouve.group(1) if trouve else ""


def url_de_lecture(url):
    """Adresse à mettre dans une iframe, ou "" si la plateforme n'en offre pas.

    Quand elle vaut "", l'interface affiche un simple bouton « Voir la vidéo »
    qui ouvre le lien dans un nouvel onglet.
    """
    plateforme = identifier(url)
    if plateforme == "youtube":
        identifiant = _id_youtube(url)
        if identifiant and re.fullmatch(r"[\w-]{6,20}", identifiant):
            return f"https://www.youtube-nocookie.com/embed/{identifiant}"
    elif plateforme == "tiktok":
        identifiant = _id_tiktok(url)
        if identifiant:
            return f"https://www.tiktok.com/embed/v2/{identifiant}"
    return ""
