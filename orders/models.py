"""Commandes de la boutique."""

from datetime import timedelta

import secrets
from decimal import Decimal
from urllib.parse import quote

from django.conf import settings
from django.db import models
from django.utils import timezone

from products.models import Product


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente de paiement"
        AWAITING = "awaiting", "À confirmer par le vendeur"
        PAID = "paid", "Payée"
        PREPARING = "preparing", "En préparation"
        READY = "ready", "Prête"
        SHIPPED = "shipped", "En cours de livraison"
        DELIVERED = "delivered", "Livrée"
        CANCELLED = "cancelled", "Annulée"
        REFUNDED = "refunded", "Remboursée"

    class CancelReason(models.TextChoices):
        NO_STOCK = "no_stock", "Article indisponible chez le vendeur"
        NO_ANSWER = "no_answer", "Vendeur sans réponse dans le délai"
        BY_CLIENT = "by_client", "Annulée par le client"
        BY_ADMIN = "by_admin", "Annulée par l'équipe"

    class Fulfilment(models.TextChoices):
        DELIVERY = "delivery", "Livraison à domicile"
        PICKUP = "pickup", "Retrait sur place"

    STATUS_CHOICES = Status.choices  # compatibilité avec l'ancien code

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    order_number = models.CharField(max_length=20, unique=True, blank=True)

    subtotal = models.DecimalField("Sous-total", max_digits=12, decimal_places=0, default=0)
    delivery_fee = models.DecimalField("Frais de livraison", max_digits=10, decimal_places=0, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    commission_total = models.DecimalField(max_digits=12, decimal_places=0, default=0)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    fulfilment = models.CharField(
        max_length=20, choices=Fulfilment.choices, default=Fulfilment.DELIVERY
    )

    shipping_name = models.CharField("Nom du destinataire", max_length=150, blank=True)
    shipping_address = models.TextField("Adresse / repère")
    shipping_phone = models.CharField("Téléphone", max_length=20)
    shipping_quartier = models.CharField("Quartier", max_length=100, blank=True)
    shipping_city = models.CharField("Ville", max_length=100, default="Ouagadougou")
    shipping_country = models.CharField(max_length=100, default="Burkina Faso")
    country = models.ForeignKey(
        "regions.Country", on_delete=models.PROTECT, null=True, blank=True,
        related_name="orders", verbose_name="Pays",
    )

    delivery_driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
        limit_choices_to={"profile__user_type": "delivery"},
    )
    tracking_number = models.CharField(max_length=100, blank=True)
    delivery_notes = models.TextField("Instructions de livraison", blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # ---- Confirmation du vendeur ----
    confirmation_deadline = models.DateTimeField(
        "À confirmer avant", null=True, blank=True,
        help_text="Au-delà, la commande est annulée et le client remboursé",
    )
    confirmed_at = models.DateTimeField("Confirmée le", null=True, blank=True)
    cancel_reason = models.CharField(
        "Motif d'annulation", max_length=20, choices=CancelReason.choices, blank=True
    )
    cancel_note = models.CharField(max_length=250, blank=True)
    reception_confirmee = models.BooleanField(
        "Réception confirmée par le client", default=False,
        help_text="Le client a lui-même déclaré avoir reçu sa commande",
    )
    non_recu_signale = models.BooleanField(
        "Non-réception signalée", default=False,
        help_text="Le client déclare ne pas avoir reçu la commande : "
                  "l'argent du vendeur reste bloqué",
    )
    non_recu_note = models.CharField(max_length=250, blank=True)
    non_recu_at = models.DateTimeField(null=True, blank=True)
    refunded_amount = models.DecimalField(
        "Montant remboursé", max_digits=12, decimal_places=0, default=0
    )
    credit_applied = models.DecimalField(
        "Avoir utilisé", max_digits=12, decimal_places=0, default=0,
        help_text="Part de la commande réglée avec l'avoir du client",
    )

    payment_method = models.CharField(max_length=50, blank=True)
    payment_reference = models.CharField(max_length=60, blank=True)
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Commande"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]

    @property
    def fenetre_contestation_ouverte(self):
        """Le client peut-il encore dire qu'il n'a rien reçu ?"""
        # Inutile de proposer de contester à quelqu'un qui vient lui-même de
        # déclarer avoir reçu sa commande.
        if self.non_recu_signale or self.reception_confirmee or not self.delivered_at:
            return False
        jours = settings.EAZYMARKET["DISPUTE_WINDOW_DAYS"]
        return timezone.now() <= self.delivered_at + timedelta(days=jours)

    def __str__(self):
        return f"Commande {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"EZ{timezone.now():%y%m}{secrets.token_hex(2).upper()}"
        super().save(*args, **kwargs)

    # ---------- Aides d'affichage ----------
    # ---------- Confirmation ----------
    @property
    def waiting_confirmation(self):
        return self.status == self.Status.AWAITING

    @property
    def hours_left(self):
        """Heures restantes au vendeur pour confirmer."""
        if not self.confirmation_deadline:
            return 0
        delta = self.confirmation_deadline - timezone.now()
        return max(0, int(delta.total_seconds() // 3600))

    @property
    def is_expired(self):
        return bool(
            self.status == self.Status.AWAITING
            and self.confirmation_deadline
            and self.confirmation_deadline <= timezone.now()
        )

    @property
    def amount_to_pay(self):
        """Ce qu'il reste à payer une fois l'avoir déduit."""
        return max(Decimal("0"), self.total - (self.credit_applied or 0))

    @property
    def status_badge(self):
        return {
            self.Status.PENDING: "warning",
            self.Status.AWAITING: "warning",
            self.Status.PAID: "info",
            self.Status.PREPARING: "info",
            self.Status.READY: "info",
            self.Status.SHIPPED: "info",
            self.Status.DELIVERED: "success",
            self.Status.CANCELLED: "danger",
            self.Status.REFUNDED: "neutral",
        }.get(self.status, "neutral")

    @property
    def can_be_cancelled(self):
        return self.status in (self.Status.PENDING, self.Status.AWAITING, self.Status.PAID)

    @property
    def seller_total(self):
        return self.subtotal - self.commission_total

    def recompute_totals(self):
        items = list(self.items.all())
        self.subtotal = sum((i.subtotal for i in items), Decimal("0"))
        self.commission_total = sum((i.commission for i in items), Decimal("0"))
        self.total = self.subtotal + (self.delivery_fee or 0)
        self.save(update_fields=["subtotal", "commission_total", "total", "updated_at"])
        return self.total


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=12, decimal_places=0)
    quantity = models.PositiveIntegerField()
    subtotal = models.DecimalField(max_digits=12, decimal_places=0)

    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    commission = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Article de commande"
        verbose_name_plural = "Articles de commande"

    def __str__(self):
        return f"{self.quantity}× {self.product_name}"

    @property
    def seller_amount(self):
        return self.subtotal - self.commission


class OrderEvent(models.Model):
    """Historique de suivi visible par le client."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=250, blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Étape de commande"
        verbose_name_plural = "Étapes de commande"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.order.order_number} → {self.get_status_display()}"


class SellerConfirmation(models.Model):
    """Confirmation attendue d'un vendeur pour sa part de la commande.

    Un panier peut contenir les articles de plusieurs commerçants. Chacun
    confirme ce qui le concerne : si l'un n'a pas le stock, seule sa part est
    annulée et remboursée, le reste de la commande suit son cours.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ACCEPTED = "accepted", "Confirmée"
        REFUSED = "refused", "Article indisponible"
        EXPIRED = "expired", "Sans réponse"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="confirmations")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="order_confirmations"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField("Part du vendeur", max_digits=12, decimal_places=0, default=0)
    commission = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    deadline = models.DateTimeField("À confirmer avant")
    responded_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Confirmation vendeur"
        verbose_name_plural = "Confirmations vendeur"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["order", "seller"], name="une_confirmation_par_vendeur")
        ]

    def __str__(self):
        return f"{self.order.order_number} — {self.seller} ({self.get_status_display()})"

    @property
    def items(self):
        return self.order.items.filter(seller=self.seller)

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def hours_left(self):
        if not self.is_pending:
            return 0
        delta = self.deadline - timezone.now()
        return max(0, int(delta.total_seconds() // 3600))

    @property
    def is_expired(self):
        return self.is_pending and self.deadline <= timezone.now()

    @property
    def seller_amount(self):
        return self.amount - self.commission

    @property
    def relance_whatsapp(self):
        """Lien wa.me pour relancer le vendeur à la main.

        Tant qu'aucune passerelle SMS n'est branchée, c'est le moyen le plus
        direct : l'administrateur ouvre le lien et le message est déjà écrit.
        """
        profil = getattr(self.seller, "profile", None)
        numero = ""
        if profil:
            numero = (profil.whatsapp or profil.phone or "").strip()
        numero = "".join(c for c in numero if c.isdigit())
        if not numero:
            return ""
        if len(numero) == 8:  # numéro burkinabè saisi sans indicatif
            numero = "226" + numero
        texte = quote(
            f"Bonjour, vous avez une commande payée sur "
            f"{settings.EAZYMARKET['SITE_NAME']} "
            f"(n° {self.order.order_number}, {self.seller_amount:,.0f} FCFA pour vous). "
            f"Merci de confirmer dans l'application si vous avez l'article, "
            f"sinon le client sera remboursé.".replace(",", " ")
        )
        return f"https://wa.me/{numero}?text={texte}"


class OrderMessage(models.Model):
    """Discussion entre le client et le vendeur, attachée à une commande.

    Les numéros de téléphone ne sont jamais échangés ici : c'est ce qui permet
    à la plateforme de rester le point de passage, et de disposer d'une trace
    en cas de litige.
    """

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    attachment = models.ImageField(upload_to="orders/messages/", blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message de commande"
        verbose_name_plural = "Messages de commande"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender} → {self.order.order_number}"
