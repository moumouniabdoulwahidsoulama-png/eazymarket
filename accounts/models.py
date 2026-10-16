"""Profils utilisateurs et rôles."""

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    class Type(models.TextChoices):
        BUYER = "buyer", "Acheteur"
        SELLER = "seller", "Vendeur"
        DELIVERY = "delivery", "Livreur"
        ARTISAN = "artisan", "Artisan / Prestataire"

    USER_TYPES = Type.choices  # compatibilité

    VEHICLES = (
        ("bicycle", "Vélo"),
        ("scooter", "Moto / Scooter"),
        ("tricycle", "Tricycle"),
        ("car", "Voiture"),
        ("van", "Fourgonnette"),
        ("truck", "Camion"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    user_type = models.CharField("Rôle", max_length=20, choices=Type.choices, default=Type.BUYER)
    phone = models.CharField("Téléphone", max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    address = models.TextField("Adresse", blank=True)
    quartier = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, default="Ouagadougou", blank=True)
    country = models.ForeignKey(
        "regions.Country", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="users", verbose_name="Pays",
    )
    is_verified = models.BooleanField("Compte vérifié", default=False)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ---- Vendeur ----
    store_name = models.CharField("Nom de la boutique", max_length=100, blank=True)
    store_slug = models.SlugField(max_length=120, blank=True)
    store_description = models.TextField(blank=True)
    store_logo = models.ImageField(upload_to="stores/", blank=True, null=True)
    store_cover = models.ImageField(upload_to="stores/", blank=True, null=True)
    is_store_active = models.BooleanField(default=False)
    store_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    # ---- Fiabilité du vendeur ----
    # Un commerçant ne met pas son stock à jour trois fois par jour : on mesure
    # donc ce qui compte vraiment pour le client, sa capacité à confirmer.
    orders_confirmed = models.PositiveIntegerField("Commandes confirmées", default=0)
    orders_cancelled = models.PositiveIntegerField(
        "Commandes annulées faute de stock", default=0
    )
    confirmation_minutes_total = models.PositiveIntegerField(default=0)
    is_store_suspended = models.BooleanField(
        "Boutique suspendue", default=False,
        help_text="Suspendue automatiquement après trop d'annulations",
    )
    suspended_reason = models.CharField(max_length=250, blank=True)
    extra_slots = models.PositiveIntegerField(
        "Emplacements achetés", default=0,
        help_text="Annonces supplémentaires achetées par packs",
    )
    extra_video_slots = models.PositiveIntegerField(
        "Emplacements vidéo achetés", default=0,
        help_text="Vidéos hébergées supplémentaires achetées par packs de 500 FCFA",
    )
    unlimited_slots = models.BooleanField(
        "Emplacements illimités", default=False,
        help_text="Boutique officielle de la plateforme : aucune limite d'annonces",
    )
    is_official = models.BooleanField(
        "Boutique officielle", default=False,
        help_text="Affiche le badge « Boutique officielle » sur la vitrine et les fiches",
    )

    # ---- Acheteur ----
    free_unlocks_left = models.PositiveIntegerField(
        "Contacts artisans offerts", default=1,
        help_text="Déblocages de contact gratuits restants",
    )

    # ---- Livreur ----
    is_driver = models.BooleanField(
        "Compte livreur activé", default=False,
        help_text="Permet de livrer, quel que soit le rôle principal",
    )
    vehicle_type = models.CharField(max_length=50, blank=True, choices=VEHICLES)
    delivery_zone = models.CharField(
        max_length=100, blank=True, help_text="Zone couverte (ex : Ouaga — Tanghin, Dapoya)"
    )
    is_available = models.BooleanField(default=False)
    delivery_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_deliveries = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"{self.user.username} — {self.get_user_type_display()}"

    two_factor_enabled = models.BooleanField(
        "Double authentification", default=False,
        help_text="Un code à usage unique est demandé à chaque connexion",
    )
    two_factor_channel = models.CharField(
        "Canal du code", max_length=10, default="email",
        choices=[("email", "E-mail"), ("sms", "SMS")],
    )

    def save(self, *args, **kwargs):
        from EazyMarket.imagerie import optimiser_champ_image
        for champ in ("profile_picture", "store_logo", "store_cover"):
            optimiser_champ_image(self, champ)
        if self.store_name and not self.store_slug:
            from django.utils.text import slugify

            self.store_slug = slugify(self.store_name)[:120]
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        full = self.user.get_full_name()
        return self.store_name or full or self.user.username

    @property
    def initials(self):
        source = self.display_name
        parts = [p for p in source.split() if p]
        return "".join(p[0].upper() for p in parts[:2]) or source[:1].upper()

    # ---------- Emplacements d'annonces (vendeur) ----------
    @property
    def has_unlimited_slots(self):
        """L'équipe de la plateforme publie sans limite : les revenus lui reviennent."""
        return self.unlimited_slots or self.user.is_staff

    @property
    def total_slots(self):
        if self.has_unlimited_slots:
            return None  # illimité
        return settings.EAZYMARKET["SHOP_FREE_SLOTS"] + self.extra_slots

    @property
    def used_slots(self):
        return self.user.products.count()

    @property
    def slots_left(self):
        if self.has_unlimited_slots:
            return None
        return max(0, self.total_slots - self.used_slots)

    @property
    def can_publish(self):
        return self.has_unlimited_slots or self.slots_left > 0

    # ---------- Ce que le compte peut faire ----------
    # Un même compte peut vendre ET livrer : on ne force personne à créer un
    # second compte pour ajouter une activité.
    @property
    def can_sell(self):
        """La boutique est-elle réellement ouverte ?

        Depuis septembre 2026, remplir le formulaire ne suffit plus : la
        boutique s'active au paiement du pack. `is_store_active` est mis à
        True par le règlement, jamais par le formulaire.
        """
        if self.is_store_suspended:
            return False
        return self.is_store_active or self.unlimited_slots or self.user.is_staff

    @property
    def boutique_en_attente(self):
        """Le vendeur a rempli sa fiche mais n'a pas encore payé le pack."""
        return bool(self.store_name) and not self.can_sell

    # ---------- Fiabilité ----------
    @property
    def orders_handled(self):
        return self.orders_confirmed + self.orders_cancelled

    @property
    def confirmation_rate(self):
        """Part des commandes confirmées, en %. 100 tant qu'il n'y a rien eu."""
        if not self.orders_handled:
            return 100
        return round(self.orders_confirmed / self.orders_handled * 100)

    @property
    def avg_confirmation_delay(self):
        """Délai moyen de confirmation, formaté pour l'affichage."""
        if not self.orders_confirmed:
            return None
        minutes = self.confirmation_minutes_total / self.orders_confirmed
        if minutes < 60:
            return f"{int(minutes)} min"
        if minutes < 60 * 24:
            return f"{minutes / 60:.1f} h".replace(".0", "")
        return f"{minutes / 1440:.1f} j".replace(".0", "")

    @property
    def reliability_label(self):
        if not self.orders_handled:
            return "Nouveau vendeur"
        taux = self.confirmation_rate
        if taux >= 95:
            return "Très fiable"
        if taux >= 85:
            return "Fiable"
        if taux >= 70:
            return "Irrégulier"
        return "Peu fiable"

    @property
    def reliability_badge(self):
        if not self.orders_handled:
            return "neutral"
        taux = self.confirmation_rate
        return "success" if taux >= 85 else ("warning" if taux >= 70 else "danger")

    @property
    def can_deliver(self):
        return self.user_type == self.Type.DELIVERY or self.is_driver

    @property
    def can_offer_services(self):
        return hasattr(self.user, "artisan_profile")

    @property
    def is_pro(self):
        return self.can_sell or self.can_deliver or self.can_offer_services

    @property
    def dashboard_url_name(self):
        return {
            self.Type.SELLER: "seller_dashboard",
            self.Type.DELIVERY: "delivery_dashboard",
            self.Type.ARTISAN: "artisan_dashboard",
        }.get(self.user_type, "profile")


class LogConnexion(models.Model):
    """Trace de chaque tentative de connexion.

    Sert à deux choses : voir qui accède aux comptes, et bloquer les
    attaques par force brute — on compte les échecs récents d'une même IP.
    """

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="connexions",
    )
    identifiant_saisi = models.CharField("Identifiant essayé", max_length=254, blank=True)
    adresse_ip = models.GenericIPAddressField("Adresse IP", null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    succes = models.BooleanField("Réussie", default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Connexion"
        verbose_name_plural = "Journal des connexions"
        ordering = ["-date"]
        indexes = [models.Index(fields=["adresse_ip", "succes", "date"])]

    def __str__(self):
        etat = "OK" if self.succes else "ECHEC"
        return f"[{etat}] {self.identifiant_saisi or self.utilisateur} — {self.adresse_ip}"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_user_profile(sender, instance, created, **kwargs):
    """Un seul signal : crée le profil à l'inscription, sans le réécrire ensuite."""
    if created:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={"free_unlocks_left": settings.EAZYMARKET["CONTACT_FREE_UNLOCKS"]},
        )
