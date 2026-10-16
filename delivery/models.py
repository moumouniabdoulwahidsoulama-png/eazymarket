"""
Validation des livreurs par parrainage.

Un livreur transporte la marchandise d'autrui et manipule de l'argent : on ne
peut pas l'accepter sur simple déclaration. Pour être activé, il partage le
lien de l'application à trois personnes qu'il inscrit dans son dossier, et un
administrateur valide. C'est gratuit pour lui, dissuasif pour les indélicats,
et cela fait connaître l'application à chaque nouvelle candidature.
"""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class DeliveryReferral(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "À compléter"
        SUBMITTED = "submitted", "Soumis"
        VERIFIED = "verified", "Validé"
        REJECTED = "rejected", "Refusé"


    deliverer = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="referral"
    )
    referral_code = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    id_document = models.ImageField(
        "Pièce d'identité", upload_to="referrals/", blank=True, null=True,
        help_text="Usage interne — jamais affichée publiquement",
    )
    note = models.TextField("Note interne", blank=True)

    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="verified_referrals",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier livreur"
        verbose_name_plural = "Dossiers livreurs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.deliverer.username} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = secrets.token_hex(4).upper()
        super().save(*args, **kwargs)

    @property
    def required(self):
        from django.conf import settings

        return settings.EAZYMARKET["DELIVERY_REQUIRED_SHARES"]

    @property
    def sponsor_count(self):
        return self.sponsors.count()

    @property
    def missing(self):
        return max(0, self.required - self.sponsor_count)

    @property
    def share_url(self):
        from django.conf import settings

        base = settings.PAYMENTS.get("PUBLIC_BASE_URL", "").rstrip("/")
        return f"{base}/?parrain={self.referral_code}"

    @property
    def share_text(self):
        from django.conf import settings

        name = settings.EAZYMARKET["SITE_NAME"]
        return (
            f"Salut ! Je livre pour {name}, la nouvelle application pour acheter "
            f"et trouver un artisan à {settings.EAZYMARKET['CITY']}. "
            f"Installe-la ici : {self.share_url}"
        )

    @property
    def is_complete(self):
        return self.missing == 0

    def mark_verified(self, by=None):
        self.status = self.Status.VERIFIED
        self.verified_at = timezone.now()
        self.verified_by = by
        self.save(update_fields=["status", "verified_at", "verified_by", "updated_at"])
        profile = self.deliverer.profile
        profile.is_verified = True
        profile.is_driver = True
        profile.is_available = True
        profile.save(update_fields=["is_verified", "is_driver", "is_available"])


class Sponsor(models.Model):
    """Une personne à qui le livreur a partagé le lien et qui répond de lui."""

    referral = models.ForeignKey(DeliveryReferral, on_delete=models.CASCADE, related_name="sponsors")
    full_name = models.CharField("Nom et prénom", max_length=150)
    phone = models.CharField("Téléphone", max_length=20)
    relation = models.CharField(
        "Lien", max_length=100, blank=True,
        help_text="Ex : ancien employeur, voisin, commerçant, chef de quartier",
    )
    is_reachable = models.BooleanField("Joint par téléphone", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Personne parrainée"
        verbose_name_plural = "Personnes parrainées"
        ordering = ["id"]

    def __str__(self):
        return f"{self.full_name} ({self.phone})"
