"""
Place de marché des services : artisans, demandes, devis, avis.

Le parcours complet est : le client publie une demande → l'artisan
répond par un devis chiffré → le client accepte → le travail se fait →
le client note l'artisan.
"""

from datetime import timedelta
from decimal import Decimal

import re

from django.conf import settings
from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class ServiceCategory(models.Model):
    name = models.CharField("Métier", max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(max_length=50, default="fa-screwdriver-wrench")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="service_categories/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Catégorie de service"
        verbose_name_plural = "Catégories de services"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("artisan_list_category", args=[self.slug])


class ArtisanQuerySet(models.QuerySet):
    def visible(self):
        """Artisans réellement affichés dans l'annuaire.

        Un profil n'apparaît que s'il est actif, non bloqué et abonné.
        Pendant une opération de lancement (ARTISAN_FREE_LAUNCH=True dans
        le .env), l'abonnement n'est pas exigé : l'annuaire se remplit
        d'abord, on facture ensuite.
        """
        qs = self.filter(is_available=True, is_blocked=False)
        if not settings.EAZYMARKET.get("ARTISAN_FREE_LAUNCH"):
            qs = qs.filter(subscription_active=True, subscription_end__gt=timezone.now())
        return qs

    def in_country(self, country):
        """L'annuaire est local : un artisan intervient dans son pays."""
        if country is None:
            return self
        return self.filter(models.Q(country=country) | models.Q(country__isnull=True))


class Artisan(models.Model):
    class Plan(models.TextChoices):
        NONE = "aucun", "Non abonné"
        PRO = "pro", "Abonné"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="artisan_profile"
    )
    service_category = models.ForeignKey(
        ServiceCategory, on_delete=models.PROTECT, related_name="artisans"
    )
    secondary_categories = models.ManyToManyField(
        ServiceCategory, blank=True, related_name="secondary_artisans",
        help_text="Autres métiers exercés",
    )

    full_name = models.CharField("Nom complet", max_length=200)
    phone = models.CharField("Téléphone", max_length=20)
    whatsapp = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to="artisans/", blank=True, null=True)

    address = models.TextField("Adresse")
    quartier = models.CharField(max_length=100)
    city = models.CharField(max_length=100, default="Ouagadougou")
    country = models.ForeignKey(
        "regions.Country", on_delete=models.PROTECT, null=True, blank=True,
        related_name="artisans", verbose_name="Pays",
    )
    intervention_radius = models.CharField(
        "Zone d'intervention", max_length=200, blank=True,
        help_text="Ex : Ouaga centre, Tanghin, Zogona",
    )

    description = models.TextField("Présentation", help_text="Présentez-vous et vos compétences")
    years_experience = models.PositiveIntegerField("Années d'expérience", default=0)
    price_range = models.CharField("Fourchette de prix", max_length=100, help_text="ex : 5 000 – 25 000 FCFA")
    hourly_rate = models.DecimalField(
        "Tarif horaire", max_digits=10, decimal_places=0, null=True, blank=True
    )
    is_available = models.BooleanField("Disponible", default=True)
    accepts_urgent = models.BooleanField("Accepte les urgences", default=False)

    # ---- Abonnement ----
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.NONE)
    subscription_active = models.BooleanField(default=False)
    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    contact_views = models.PositiveIntegerField(
        "Contacts débloqués", default=0,
        help_text="Nombre de fois où un client a payé pour voir votre numéro",
    )

    # ---- Réputation ----
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews = models.PositiveIntegerField(default=0)
    completed_jobs = models.PositiveIntegerField(default=0)
    response_rate = models.PositiveIntegerField("Taux de réponse (%)", default=100)

    # ---- Visibilité / modération ----
    is_featured = models.BooleanField("Mis en avant", default=False)
    featured_until = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField("Identité vérifiée", default=False)
    id_document = models.ImageField(
        upload_to="artisans/id/", blank=True, null=True,
        help_text="Pièce d'identité — usage interne, jamais affichée",
    )
    is_blocked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ArtisanQuerySet.as_manager()

    class Meta:
        verbose_name = "Artisan"
        ordering = ["-is_featured", "-rating", "-completed_jobs"]
        indexes = [models.Index(fields=["service_category", "-rating"])]

    def __str__(self):
        return f"{self.full_name} — {self.service_category.name}"

    def get_absolute_url(self):
        return reverse("artisan_detail", args=[self.pk])

    # ---------- Contact ----------
    @property
    def phone_masque(self):
        """Aperçu du numéro, sans qu'on puisse l'utiliser.

        On ne laisse voir que les deux premiers chiffres : ils indiquent
        l'opérateur, ce qui rassure le client, sans permettre d'appeler.
        Afficher davantage revient à donner le numéro — un numéro burkinabè
        n'a que huit chiffres.
        """
        chiffres = re.sub(r"\D", "", self.phone or "")
        for indicatif in ("00226", "226"):
            if chiffres.startswith(indicatif) and len(chiffres) > len(indicatif):
                chiffres = chiffres[len(indicatif):]
                break
        if len(chiffres) < 4:
            return "•• •• •• ••"

        visible = chiffres[:2]
        caches = ["••"] * max(1, (len(chiffres) - 2 + 1) // 2)
        return " ".join([visible] + caches)

    def save(self, *args, **kwargs):
        from EazyMarket.imagerie import optimiser_champ_image
        optimiser_champ_image(self, "photo")
        if self.country_id is None:
            profile = getattr(self.user, "profile", None)
            if profile is not None and profile.country_id:
                self.country_id = profile.country_id
            else:
                from regions.models import Country

                default = Country.default()
                if default:
                    self.country_id = default.pk
        super().save(*args, **kwargs)

    # ---------- Abonnement ----------
    def is_subscription_active(self):
        if not self.subscription_active:
            return False
        if self.subscription_end and self.subscription_end < timezone.now():
            Artisan.objects.filter(pk=self.pk).update(subscription_active=False, plan=self.Plan.NONE)
            self.subscription_active = False
            self.plan = self.Plan.NONE
            return False
        return True

    def activate_subscription(self, plan="pro", days=30):
        """Active ou prolonge — si l'abonnement court encore, on ajoute la durée."""
        now = timezone.now()
        start = now
        base = self.subscription_end if (self.subscription_end and self.subscription_end > now) else now
        self.plan = plan
        self.subscription_active = True
        self.subscription_start = self.subscription_start or start
        self.subscription_end = base + timedelta(days=days)
        self.save(update_fields=["plan", "subscription_active", "subscription_start", "subscription_end"])
        return self.subscription_end

    @property
    def days_left(self):
        if not self.subscription_end:
            return 0
        delta = self.subscription_end - timezone.now()
        return max(0, delta.days)

    @property
    def is_boosted(self):
        return bool(self.is_featured and self.featured_until and self.featured_until > timezone.now())

    @property
    def is_listed(self):
        """Le profil apparaît-il dans l'annuaire ?"""
        if settings.EAZYMARKET.get("ARTISAN_FREE_LAUNCH"):
            return self.is_available and not self.is_blocked
        return self.is_available and not self.is_blocked and self.is_subscription_active()

    @property
    def can_answer(self):
        """Peut-il répondre aux demandes et envoyer des devis ?"""
        return settings.EAZYMARKET.get("ARTISAN_FREE_LAUNCH") or self.is_subscription_active()

    # ---------- Affichage ----------
    @property
    def initials(self):
        parts = [p for p in self.full_name.split() if p]
        return "".join(p[0].upper() for p in parts[:2]) or "?"

    @property
    def stars(self):
        full = int(self.rating)
        half = 1 if (self.rating - full) >= Decimal("0.5") else 0
        return {"full": range(full), "half": half, "empty": range(5 - full - half)}

    def refresh_rating(self):
        stats = self.reviews.aggregate(avg=Avg("rating"), n=Count("id"))
        Artisan.objects.filter(pk=self.pk).update(
            rating=stats["avg"] or 0, total_reviews=stats["n"] or 0
        )


class Portfolio(models.Model):
    artisan = models.ForeignKey(Artisan, on_delete=models.CASCADE, related_name="portfolios")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="portfolio/", blank=True, null=True)
    image_url = models.URLField(blank=True)
    link = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Réalisation"
        verbose_name_plural = "Réalisations"
        ordering = ["-is_featured", "-created_at"]

    def __str__(self):
        return f"{self.title} — {self.artisan.full_name}"

    def save(self, *args, **kwargs):
        from EazyMarket.imagerie import optimiser_champ_image
        optimiser_champ_image(self, "image")
        super().save(*args, **kwargs)

    @property
    def display_image(self):
        if self.image:
            return self.image.url
        return self.image_url or ""


class ServiceRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        QUOTED = "quoted", "Devis envoyé"
        ACCEPTED = "accepted", "Acceptée"
        IN_PROGRESS = "in_progress", "En cours"
        COMPLETED = "completed", "Terminée"
        REJECTED = "rejected", "Refusée"
        CANCELLED = "cancelled", "Annulée"

    class Urgency(models.TextChoices):
        FLEXIBLE = "flexible", "Quand c'est possible"
        WEEK = "week", "Dans la semaine"
        URGENT = "urgent", "Urgent (24 h)"

    reference = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    artisan = models.ForeignKey(Artisan, on_delete=models.CASCADE, related_name="service_requests")
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_requests"
    )

    title = models.CharField("Objet", max_length=200)
    description = models.TextField("Description du travail")
    photo = models.ImageField(
        upload_to="requests/", blank=True, null=True, help_text="Une photo aide l'artisan à chiffrer"
    )
    preferred_date = models.DateField("Date souhaitée", null=True, blank=True)
    preferred_time = models.TimeField(null=True, blank=True)
    urgency = models.CharField(max_length=20, choices=Urgency.choices, default=Urgency.FLEXIBLE)
    budget = models.CharField("Budget estimé", max_length=100, blank=True)

    client_phone = models.CharField(max_length=20)
    client_address = models.TextField()

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_message = models.TextField(blank=True)
    viewed_by_artisan = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Demande de service"
        verbose_name_plural = "Demandes de service"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.title}"

    def save(self, *args, **kwargs):
        if not self.reference:
            import secrets

            self.reference = f"DS-{timezone.now():%y%m}-{secrets.token_hex(2).upper()}"
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status in (self.Status.PENDING, self.Status.QUOTED, self.Status.ACCEPTED, self.Status.IN_PROGRESS)

    @property
    def accepted_quote(self):
        return self.quotes.filter(status=Quote.Status.ACCEPTED).first()


class Quote(models.Model):
    """Devis envoyé par l'artisan pour une demande."""

    class Status(models.TextChoices):
        SENT = "sent", "Envoyé"
        ACCEPTED = "accepted", "Accepté"
        REFUSED = "refused", "Refusé"
        EXPIRED = "expired", "Expiré"

    reference = models.CharField(max_length=24, unique=True, blank=True, editable=False)
    service_request = models.ForeignKey(
        ServiceRequest, on_delete=models.CASCADE, related_name="quotes"
    )
    artisan = models.ForeignKey(Artisan, on_delete=models.CASCADE, related_name="quotes")

    labour_cost = models.DecimalField("Main-d'œuvre", max_digits=12, decimal_places=0, default=0)
    materials_cost = models.DecimalField("Fournitures", max_digits=12, decimal_places=0, default=0)
    travel_cost = models.DecimalField("Déplacement", max_digits=12, decimal_places=0, default=0)
    details = models.TextField("Détail de la prestation")
    duration = models.CharField("Durée estimée", max_length=100, blank=True, help_text="ex : 2 jours")
    valid_until = models.DateField("Valable jusqu'au", null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    client_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Devis"
        verbose_name_plural = "Devis"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.total} FCFA"

    def save(self, *args, **kwargs):
        if not self.reference:
            import secrets

            self.reference = f"DV-{timezone.now():%y%m}-{secrets.token_hex(2).upper()}"
        if not self.valid_until:
            self.valid_until = (timezone.now() + timedelta(days=15)).date()
        super().save(*args, **kwargs)

    @property
    def total(self):
        return (self.labour_cost or 0) + (self.materials_cost or 0) + (self.travel_cost or 0)

    @property
    def is_expired(self):
        return bool(self.valid_until and self.valid_until < timezone.now().date())


class ServiceMessage(models.Model):
    """Fil de discussion entre le client et l'artisan sur une demande."""

    service_request = models.ForeignKey(
        ServiceRequest, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    attachment = models.ImageField(upload_to="messages/", blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Message"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender} → {self.service_request.reference}"


class ServiceReview(models.Model):
    artisan = models.ForeignKey(Artisan, on_delete=models.CASCADE, related_name="reviews")
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    service_request = models.OneToOneField(
        ServiceRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="review"
    )
    rating = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    punctuality = models.PositiveSmallIntegerField(
        "Ponctualité", choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True
    )
    quality = models.PositiveSmallIntegerField(
        "Qualité du travail", choices=[(i, str(i)) for i in range(1, 6)], null=True, blank=True
    )
    comment = models.TextField()
    artisan_reply = models.TextField("Réponse de l'artisan", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Avis"
        verbose_name_plural = "Avis"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["artisan", "client"], name="un_avis_par_client_et_artisan")
        ]

    def __str__(self):
        return f"{self.client} → {self.artisan.full_name} ({self.rating}★)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.artisan.refresh_rating()


class ContactUnlock(models.Model):
    """Un client a payé (ou utilisé son crédit offert) pour voir le numéro d'un artisan.

    Sans cela, un client pourrait appeler l'artisan directement et la
    plateforme ne verrait jamais la mise en relation qu'elle a produite.
    """

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="contact_unlocks"
    )
    artisan = models.ForeignKey(Artisan, on_delete=models.CASCADE, related_name="contact_unlocks")
    amount = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    is_free = models.BooleanField("Crédit offert", default=False)
    transaction_reference = models.CharField(max_length=40, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contact débloqué"
        verbose_name_plural = "Contacts débloqués"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["client", "artisan"], name="un_deblocage_par_couple")
        ]

    def __str__(self):
        return f"{self.client} → {self.artisan.full_name}"

    @property
    def is_active(self):
        return self.expires_at is None or self.expires_at > timezone.now()

    @classmethod
    def is_unlocked(cls, user, artisan):
        if not user.is_authenticated:
            return False
        if artisan.user_id == user.id:
            return True
        unlock = cls.objects.filter(client=user, artisan=artisan).first()
        return bool(unlock and unlock.is_active)
