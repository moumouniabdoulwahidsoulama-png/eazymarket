"""
Paiements, portefeuilles et reversements.

Principe : tout mouvement d'argent passe par une Transaction (entrée) et
par des écritures de portefeuille (WalletEntry). Le solde d'un vendeur ou
d'un artisan n'est jamais un champ modifié à la main : c'est la somme de
ses écritures. Impossible de « perdre » de l'argent en cours de route.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction as db_transaction
from django.db.models import Sum
from django.utils import timezone


def _reference(prefix):
    return f"{prefix}-{timezone.now():%y%m%d}-{secrets.token_hex(3).upper()}"


class Transaction(models.Model):
    """Un encaissement (ou une tentative) vers EazyMarket."""

    class Purpose(models.TextChoices):
        ORDER = "order", "Commande"
        SUBSCRIPTION = "subscription", "Abonnement artisan"
        SHOP_PACK = "shop_pack", "Pack d'annonces vendeur"
        VIDEO_PACK = "video_pack", "Pack d'emplacements vidéo"
        CONTACT = "contact", "Déblocage de contact"
        BOOST = "boost", "Mise en avant"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        AWAITING_REVIEW = "awaiting_review", "À vérifier"
        SUCCESS = "success", "Réussi"
        FAILED = "failed", "Échoué"
        CANCELLED = "cancelled", "Annulé"
        REFUNDED = "refunded", "Remboursé"

    class Channel(models.TextChoices):
        ORANGE = "orange_money", "Orange Money"
        MOOV = "moov_money", "Moov Money"
        WAVE = "wave", "Wave"
        CARD = "card", "Carte bancaire"
        CASH = "cash", "Espèces à la livraison"
        CREDIT = "credit", "Avoir sur le compte"
        OTHER = "other", "Autre"

    reference = models.CharField(max_length=40, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="transactions"
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=0, help_text="Montant en FCFA")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    channel = models.CharField(max_length=20, choices=Channel.choices, blank=True)

    provider = models.CharField(max_length=30, default="manual")
    provider_reference = models.CharField(max_length=120, blank=True)
    payer_number = models.CharField(max_length=32, blank=True, help_text="Numéro qui a payé")

    # Objet lié (commande, abonnement…) sans dépendance croisée dure
    object_type = models.CharField(max_length=40, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)

    proof = models.ImageField(upload_to="payments/proofs/", blank=True, null=True)
    notes = models.TextField(blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_transactions",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Transaction"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "purpose"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.reference} · {self.amount:,.0f} FCFA · {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = _reference("TX")
        super().save(*args, **kwargs)

    @property
    def is_final(self):
        return self.status in (self.Status.SUCCESS, self.Status.REFUNDED)


class Wallet(models.Model):
    """Portefeuille d'un vendeur, artisan ou livreur."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet"
    )
    payout_channel = models.CharField(
        max_length=20, choices=Transaction.Channel.choices, default=Transaction.Channel.ORANGE
    )
    payout_number = models.CharField(max_length=32, blank=True)
    payout_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Portefeuille"
        verbose_name_plural = "Portefeuilles"

    def __str__(self):
        return f"Portefeuille de {self.user.username}"

    def _sum(self, **filters):
        return self.entries.filter(**filters).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    @property
    def locked(self):
        """Somme déjà demandée en versement et pas encore payée.

        Sans cela, on pourrait demander un retrait de tout son solde puis
        dépenser le même argent en avoir sur une commande : le compte
        passerait en négatif.
        """
        from django.db.models import Sum as _Sum

        total = self.payouts.filter(
            status__in=["requested", "processing"]
        ).aggregate(t=_Sum("amount"))["t"]
        return total or Decimal("0")

    @property
    def available(self):
        """Solde réellement utilisable : libéré, moins ce qui est déjà réservé."""
        return max(Decimal("0"), self._sum(is_released=True) - self.locked)

    @property
    def pending(self):
        """Argent encaissé mais pas encore libéré (délai de sécurité)."""
        return self._sum(is_released=False)

    @property
    def total_earned(self):
        return self._sum(amount__gt=0)

    @property
    def can_withdraw(self):
        return self.available >= settings.EAZYMARKET["PAYOUT_MIN"] and bool(self.payout_number)


class WalletEntry(models.Model):
    """Une ligne de compte : positive = gain, négative = retrait ou frais."""

    class Kind(models.TextChoices):
        SALE = "sale", "Vente"
        COMMISSION = "commission", "Commission EazyMarket"
        REFUND = "refund", "Remboursement"
        DELIVERY = "delivery", "Frais de livraison"
        PAYOUT = "payout", "Retrait"
        BONUS = "bonus", "Bonus"
        ADJUSTMENT = "adjustment", "Ajustement"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="entries")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    label = models.CharField(max_length=200)
    is_released = models.BooleanField(
        default=False, help_text="Libéré = disponible au retrait"
    )
    release_at = models.DateTimeField(null=True, blank=True)
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="wallet_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Écriture de portefeuille"
        verbose_name_plural = "Écritures de portefeuille"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount:+,.0f} — {self.label}"


class Payout(models.Model):
    """Un versement à faire vers un mobile money.

    Deux cas, même circuit : le vendeur qui retire ses gains, et le client
    qui préfère récupérer son argent plutôt que de garder un avoir. Les deux
    atterrissent dans le même écran d'administration, où le versement se fait
    à la main puis se marque comme payé.
    """

    class Kind(models.TextChoices):
        WITHDRAWAL = "withdrawal", "Retrait de gains"
        REFUND = "refund", "Remboursement client"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Demandé"
        PROCESSING = "processing", "En cours"
        PAID = "paid", "Versé"
        REJECTED = "rejected", "Refusé"

    reference = models.CharField(max_length=40, unique=True, editable=False)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="payouts")
    kind = models.CharField(
        "Nature", max_length=20, choices=Kind.choices, default=Kind.WITHDRAWAL
    )
    order = models.ForeignKey(
        "orders.Order", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="refunds", help_text="Commande à l'origine du remboursement",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    channel = models.CharField(max_length=20, choices=Transaction.Channel.choices)
    number = models.CharField(max_length=32)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    provider_reference = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Retrait"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {self.amount:,.0f} FCFA · {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = _reference("PO")
        super().save(*args, **kwargs)

    @db_transaction.atomic
    def mark_paid(self, by=None):
        if self.status == self.Status.PAID:
            return
        self.status = self.Status.PAID
        self.paid_at = timezone.now()
        self.processed_by = by
        self.save()
        libelle = (
            f"Remboursement {self.reference} envoyé sur {self.number}"
            if self.kind == self.Kind.REFUND
            else f"Retrait {self.reference} vers {self.number}"
        )
        WalletEntry.objects.create(
            wallet=self.wallet,
            kind=WalletEntry.Kind.PAYOUT,
            amount=-self.amount,
            label=libelle,
            is_released=True,
            order=self.order,
        )
