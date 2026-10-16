"""Lecture de la durée d'une vidéo, sans ffmpeg.

L'hébergement mutualisé de LWS ne fournit pas ffmpeg et on ne peut pas
l'installer. On lit donc la durée directement dans l'en-tête du fichier :
un MP4 (et un .mov, même format de conteneur) range cette information dans
un petit bloc nommé « mvhd ». Quelques dizaines de lignes suffisent, et
aucune dépendance n'est ajoutée au projet.

Si le format ne permet pas la lecture (WebM par exemple), on renvoie 0 :
le contrôle de taille prend alors le relais, et le navigateur du vendeur
a déjà refusé les vidéos trop longues avant l'envoi.
"""

import struct

# On ne lit jamais plus que ça : un mvhd se trouve toujours au début ou à
# la toute fin du fichier, jamais au milieu de la vidéo elle-même.
FENETRE = 3 * 1024 * 1024


def _lire_mvhd(donnees):
    """Cherche le bloc mvhd et en extrait la durée en secondes."""
    position = donnees.find(b"mvhd")
    if position < 0:
        return 0

    debut = position + 4
    if debut + 1 > len(donnees):
        return 0

    version = donnees[debut]
    try:
        if version == 1:
            # version 1 : dates sur 8 octets, échelle et durée sur 8
            bloc = donnees[debut + 20 : debut + 32]
            if len(bloc) < 12:
                return 0
            echelle, duree = struct.unpack(">IQ", bloc)
        else:
            # version 0 : dates sur 4 octets
            bloc = donnees[debut + 12 : debut + 20]
            if len(bloc) < 8:
                return 0
            echelle, duree = struct.unpack(">II", bloc)
    except struct.error:
        return 0

    if not echelle:
        return 0
    return int(duree / echelle)


def duree_en_secondes(fichier):
    """Durée d'une vidéo envoyée par un formulaire. 0 si on ne sait pas."""
    try:
        fichier.seek(0)
        debut = fichier.read(FENETRE)
        duree = _lire_mvhd(debut)

        if not duree:
            # Certains téléphones écrivent l'en-tête à la fin du fichier.
            taille = getattr(fichier, "size", 0)
            if taille > FENETRE:
                fichier.seek(max(0, taille - FENETRE))
                duree = _lire_mvhd(fichier.read(FENETRE))
    except Exception:  # noqa: BLE001 — un fichier illisible n'est jamais bloquant
        return 0
    finally:
        try:
            fichier.seek(0)
        except Exception:  # noqa: BLE001
            pass

    # Une durée aberrante (fichier corrompu) vaut mieux ignorée que refusée.
    return duree if 0 < duree < 60 * 60 * 12 else 0
