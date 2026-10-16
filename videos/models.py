"""Vidéos de présentation, pour la boutique comme pour les artisans.

Une photo peut être prise n'importe où sur internet ; une vidéo de quelques
secondes où l'on tourne autour de l'objet, beaucoup plus difficilement.
C'est la meilleure preuve qu'un vendeur possède réellement ce qu'il vend, et
pour un artisan, la seule façon de montrer son travail en mouvement.

Deux formes possibles :

* un fichier hébergé chez nous — rassurant, mais il occupe du disque et de la
  bande passante : ces vidéos-là consomment un emplacement, et au-delà du
  quota offert le vendeur achète un pack ;
* un lien TikTok, YouTube, Facebook ou Instagram — beaucoup de vendeurs
  filment déjà pour ces plateformes. Cela ne nous coûte rien, donc c'est
  gratuit et sans limite de quota.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .liens import PLATEFORMES, identifier, url_de_lecture


class VideoQuerySet(models.QuerySet):
    def visibles(self):
        return self.filter(is_approved=True)

    def hebergees(self):
        """Celles qui occupent réellement de la place sur le serveur."""
        return self.exclude(file="")


class Video(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="videos",
        verbose_name="Propriétaire",
    )

    # La vidéo est rattachée soit à un produit, soit à un artisan.
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    file = models.FileField("Fichier", upload_to="videos/%Y/%m/", blank=True)
    external_url = models.URLField("Lien TikTok / YouTube", blank=True)

    title = models.CharField("Titre", max_length=120, blank=True)
    duration = models.PositiveIntegerField("Durée (secondes)", default=0)
    size = models.PositiveBigIntegerField("Taille (octets)", default=0)

    is_approved = models.BooleanField(
        "Validée", default=True,
        help_text="Décochez pour retirer immédiatement une vidéo du site",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = VideoQuerySet.as_manager()

    class Meta:
        verbose_name = "Vidéo"
        verbose_name_plural = "Vidéos"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["content_type", "object_id"])]

    def __str__(self):
        return self.title or f"Vidéo #{self.pk}"

    def delete(self, *args, **kwargs):
        """Supprimer la ligne supprime aussi le fichier : le disque est compté."""
        fichier = self.file
        resultat = super().delete(*args, **kwargs)
        if fichier:
            fichier.storage.delete(fichier.name)
        return resultat

    # ---------- Nature de la vidéo ----------
    @property
    def is_hosted(self):
        return bool(self.file)

    @property
    def plateforme(self):
        return identifier(self.external_url)

    @property
    def plateforme_nom(self):
        return PLATEFORMES.get(self.plateforme, {}).get("nom", "")

    @property
    def plateforme_icone(self):
        return PLATEFORMES.get(self.plateforme, {}).get("icone", "fa-play")

    @property
    def embed_url(self):
        return url_de_lecture(self.external_url)

    # ---------- Affichage ----------
    @property
    def poster_url(self):
        """Image affichée avant lecture.

        On réutilise la photo du produit ou de l'artisan : le serveur n'a pas
        ffmpeg pour extraire une image de la vidéo, et de toute façon la photo
        du produit est plus soignée qu'une image tirée au hasard.
        """
        cible = self.target
        if cible is None:
            return ""
        for attribut in ("main_image", "photo", "image"):
            image = getattr(cible, attribut, None)
            if image:
                try:
                    return image.url
                except ValueError:
                    continue
        return ""

    @property
    def duree_affichee(self):
        if not self.duration:
            return ""
        minutes, secondes = divmod(self.duration, 60)
        return f"{minutes}:{secondes:02d}" if minutes else f"{secondes} s"

    @property
    def poids_affiche(self):
        if not self.size:
            return ""
        return f"{self.size / (1024 * 1024):.1f} Mo".replace(".0", "")

    # ---------- Utilitaires ----------
    @classmethod
    def toutes_pour(cls, objet):
        """Toutes les vidéos d'un produit ou d'un artisan, retirées comprises.

        C'est la vue du propriétaire : il doit voir qu'une de ses vidéos a été
        retirée du site, sinon il ne comprend pas pourquoi elle n'apparaît pas.
        """
        if objet is None or not objet.pk:
            return cls.objects.none()
        return cls.objects.filter(
            content_type=ContentType.objects.get_for_model(objet), object_id=objet.pk
        )

    @classmethod
    def pour(cls, objet):
        """Vidéos réellement affichées au public."""
        return cls.toutes_pour(objet).visibles()
