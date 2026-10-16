"""Compression des images envoyées par les utilisateurs.

Au Burkina, beaucoup de connexions se paient au mégaoctet et les téléphones
produisent des photos de 3 à 8 Mo. Les afficher telles quelles, c'est lent
pour le visiteur et coûteux pour lui. On réduit donc chaque image dès l'envoi :
redimensionnée, recompressée, et débarrassée de ses métadonnées d'appareil.

Aucune dépendance nouvelle : Pillow est déjà là pour Django.
"""

import io
import logging

from django.core.files.base import ContentFile

logger = logging.getLogger("eazymarket")

COTE_MAX = 1280        # un téléphone n'a pas besoin de plus large
QUALITE = 80           # bon compromis poids / netteté
POIDS_MINI = 90 * 1024  # en dessous, l'image est déjà légère : on n'y touche pas


def compresser_image(fichier, cote_max=COTE_MAX, qualite=QUALITE):
    """Renvoie une version allégée du fichier image, ou None si rien à faire.

    Ne lève jamais : une image illisible est renvoyée telle quelle plutôt que
    de faire échouer un envoi de produit.
    """
    try:
        from PIL import Image, ImageOps
    except Exception:  # noqa: BLE001 — Pillow absent : on ne bloque pas
        return None

    try:
        taille = getattr(fichier, "size", 0) or 0
        fichier.seek(0)
        image = Image.open(fichier)
        image = ImageOps.exif_transpose(image)  # respecte l'orientation du téléphone
        format_origine = (image.format or "").upper()

        # Un PNG avec transparence reste en PNG ; le reste part en JPEG,
        # bien plus léger pour une photo.
        transparent = image.mode in ("RGBA", "LA", "P") and format_origine == "PNG"

        trop_grande = max(image.size) > cote_max
        if not trop_grande and taille and taille < POIDS_MINI and not transparent:
            return None  # déjà légère, on la laisse

        if trop_grande:
            image.thumbnail((cote_max, cote_max), Image.LANCZOS)

        buffer = io.BytesIO()
        if transparent:
            image.save(buffer, format="PNG", optimize=True)
            extension = "png"
        else:
            image.convert("RGB").save(buffer, format="JPEG", quality=qualite, optimize=True, progressive=True)
            extension = "jpg"

        # Si on n'a rien gagné, on garde l'original.
        if taille and buffer.tell() >= taille and not trop_grande:
            return None

        return ContentFile(buffer.getvalue()), extension
    except Exception:  # noqa: BLE001
        logger.exception("Compression d'image échouée : image conservée telle quelle")
        return None


def optimiser_champ_image(instance, nom_champ):
    """Compresse le champ image d'une instance, avant sauvegarde en base.

    À appeler dans save() : on ne retouche que si le fichier vient d'être
    envoyé (il a un contenu en mémoire), pour ne pas recompresser à chaque
    enregistrement une image déjà stockée.
    """
    champ = getattr(instance, nom_champ, None)
    if not champ:
        return
    # Fichier déjà en base (pas de nouvel envoi) : on ne le rouvre pas.
    if not hasattr(champ, "file") or getattr(champ, "_committed", True):
        return

    resultat = compresser_image(champ)
    if not resultat:
        return
    contenu, extension = resultat

    nom = champ.name.rsplit("/", 1)[-1]
    base = nom.rsplit(".", 1)[0] if "." in nom else nom
    champ.save(f"{base}.{extension}", contenu, save=False)
