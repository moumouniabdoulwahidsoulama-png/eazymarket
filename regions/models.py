"""
Ouverture internationale.

EazyMarket n'est pas un site mondial unique : c'est une place de marché
**locale, répliquée pays par pays**. Chaque pays a ses vendeurs, ses artisans,
ses livreurs, sa monnaie, ses tarifs et ses numéros d'encaissement. Un acheteur
de Ouagadougou voit les produits du Burkina, un acheteur d'Abidjan voit ceux de
Côte d'Ivoire.

C'est le seul modèle qui tienne : la livraison, la confiance et le mobile money
sont des affaires locales. Ouvrir un pays, c'est y trouver des vendeurs, des
livreurs et un numéro pour encaisser — pas écrire du code.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Country(models.Model):
    """Un pays ouvert (ou en préparation) sur la plateforme."""

    name = models.CharField("Pays", max_length=100, unique=True)
    code = models.CharField("Code ISO", max_length=2, unique=True, help_text="Ex : BF, CI, SN")
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    flag = models.CharField("Drapeau", max_length=8, blank=True, help_text="Emoji, ex : 🇧🇫")
    dial_code = models.CharField("Indicatif", max_length=8, default="+226")

    currency_code = models.CharField("Code devise", max_length=8, default="XOF")
    currency_symbol = models.CharField("Symbole devise", max_length=12, default="FCFA")

    main_city = models.CharField("Ville principale", max_length=100, default="Ouagadougou")
    support_phone = models.CharField("Téléphone d'assistance", max_length=32, blank=True)
    support_whatsapp = models.CharField("WhatsApp d'assistance", max_length=32, blank=True)

    is_active = models.BooleanField(
        "Ouvert au public", default=False,
        help_text="Décoché : le pays n'apparaît pas dans le sélecteur",
    )
    is_default = models.BooleanField("Pays par défaut", default=False)
    order = models.PositiveIntegerField(default=0)

    # Tarifs locaux — 0 signifie « utiliser la valeur du fichier .env »
    shop_pack_price = models.DecimalField("Pack d'annonces", max_digits=12, decimal_places=0, default=0)
    artisan_sub_price = models.DecimalField("Abonnement artisan", max_digits=12, decimal_places=0, default=0)
    contact_unlock_price = models.DecimalField("Déblocage de contact", max_digits=12, decimal_places=0, default=0)
    delivery_fee_city = models.DecimalField("Livraison en ville", max_digits=12, decimal_places=0, default=0)
    delivery_fee_out = models.DecimalField("Livraison hors ville", max_digits=12, decimal_places=0, default=0)
    free_delivery_from = models.DecimalField("Livraison offerte dès", max_digits=12, decimal_places=0, default=0)
    payout_min = models.DecimalField("Retrait minimum", max_digits=12, decimal_places=0, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pays"
        verbose_name_plural = "Pays"
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.flag} {self.name}".strip()

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        if self.is_default:
            Country.objects.exclude(pk=self.pk).update(is_default=False)

    # ------------------------------------------------------------------
    def _or_default(self, value, key):
        value = Decimal(value or 0)
        return value if value > 0 else Decimal(settings.EAZYMARKET[key])

    @property
    def pricing(self):
        """Tarifs applicables dans ce pays, avec repli sur le .env."""
        conf = settings.EAZYMARKET
        return {
            "CURRENCY": self.currency_symbol,
            "SHOP_PACK_PRICE": self._or_default(self.shop_pack_price, "SHOP_PACK_PRICE"),
            "SHOP_PACK_SIZE": conf["SHOP_PACK_SIZE"],
            "SHOP_FREE_SLOTS": conf["SHOP_FREE_SLOTS"],
            "ARTISAN_SUB_PRICE": self._or_default(self.artisan_sub_price, "ARTISAN_SUB_PRICE"),
            "ARTISAN_SUB_DAYS": conf["ARTISAN_SUB_DAYS"],
            "CONTACT_UNLOCK_PRICE": self._or_default(self.contact_unlock_price, "CONTACT_UNLOCK_PRICE"),
            "CONTACT_UNLOCK_DAYS": conf["CONTACT_UNLOCK_DAYS"],
            "DELIVERY_FEE_CITY": self._or_default(self.delivery_fee_city, "DELIVERY_FEE_CITY"),
            "DELIVERY_FEE_OUT": self._or_default(self.delivery_fee_out, "DELIVERY_FEE_OUT"),
            "FREE_DELIVERY_FROM": self._or_default(self.free_delivery_from, "FREE_DELIVERY_FROM"),
            "PAYOUT_MIN": self._or_default(self.payout_min, "PAYOUT_MIN"),
            "COMMISSION_RATE": conf["COMMISSION_RATE"],
            "COMMISSION_MIN": conf["COMMISSION_MIN"],
            "DELIVERY_REQUIRED_SHARES": conf["DELIVERY_REQUIRED_SHARES"],
        }

    @property
    def is_open(self):
        """Un pays est réellement ouvert s'il a de quoi encaisser."""
        return self.is_active and self.payment_accounts.filter(is_active=True).exists()

    @classmethod
    def default(cls):
        return (
            cls.objects.filter(is_default=True).first()
            or cls.objects.filter(is_active=True).first()
            or cls.objects.first()
        )


class City(models.Model):
    """Ville couverte — sert aux frais de livraison et au filtrage des courses."""

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField("Ville", max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    is_main = models.BooleanField("Ville principale", default=False)
    delivery_fee = models.DecimalField(
        "Frais de livraison", max_digits=12, decimal_places=0, default=0,
        help_text="0 = tarif du pays",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Ville"
        verbose_name_plural = "Villes"
        ordering = ["country", "order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["country", "name"], name="une_ville_par_pays")
        ]

    def __str__(self):
        return f"{self.name} ({self.country.code})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class PaymentAccount(models.Model):
    """Un numéro sur lequel les clients d'un pays envoient l'argent.

    Gérés depuis l'administration : ouvrir un nouveau pays, c'est ajouter ici
    un numéro local — aucun code à modifier.
    """

    class Channel(models.TextChoices):
        ORANGE = "orange_money", "Orange Money"
        MOOV = "moov_money", "Moov Money"
        WAVE = "wave", "Wave"
        MTN = "mtn_money", "MTN MoMo"
        AIRTEL = "airtel_money", "Airtel Money"
        OTHER = "other", "Autre"

    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="payment_accounts")
    channel = models.CharField("Opérateur", max_length=20, choices=Channel.choices)
    label = models.CharField("Nom affiché", max_length=60, blank=True)
    number = models.CharField("Numéro", max_length=32)
    holder = models.CharField("Titulaire", max_length=120, blank=True)
    ussd_template = models.CharField(
        "Code à composer", max_length=60, blank=True,
        help_text="Ex : *144*10*{numero}*{montant}#  — laisser vide si l'opérateur n'en a pas",
    )
    menu_hint = models.CharField(
        "Menu de l'opérateur", max_length=60, blank=True,
        help_text="Ex : #144#, *555#, application Wave",
    )
    whatsapp = models.CharField(
        "WhatsApp", max_length=32, blank=True,
        help_text="Si ce numéro reçoit aussi WhatsApp",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Compte d'encaissement"
        verbose_name_plural = "Comptes d'encaissement"
        ordering = ["country", "order", "id"]

    def __str__(self):
        return f"{self.get_channel_display()} {self.number} ({self.country.code})"

    @property
    def digits(self):
        raw = "".join(c for c in self.number if c.isdigit())
        indicatif = "".join(c for c in self.country.dial_code if c.isdigit())
        if indicatif and raw.startswith(indicatif) and len(raw) > len(indicatif):
            raw = raw[len(indicatif):]
        return raw

    def ussd(self, amount):
        if not self.ussd_template:
            return ""
        return self.ussd_template.format(numero=self.digits, montant=int(amount))

    def as_dict(self, amount=0):
        return {
            "id": self.pk,
            "channel": self.channel,
            "label": self.label or self.get_channel_display(),
            "number": self.number,
            "name": self.holder,
            "ussd": self.ussd(amount),
            "menu": self.menu_hint,
            "whatsapp": self.whatsapp,
        }
