"""Catalogue produits."""

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from django.conf import settings
from django.db import models
from django.db.models import Avg, Count
from django.urls import reverse
from django.utils.text import slugify


def commission_rate():
    return Decimal(str(settings.EAZYMARKET["COMMISSION_RATE"])) / Decimal("100")


class Category(models.Model):
    name = models.CharField("Nom", max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50, default="fa-box", help_text="Icône Font Awesome (ex: fa-mobile-screen)"
    )
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, blank=True, null=True, related_name="subcategories"
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("category_products", args=[self.slug])


class ProductQuerySet(models.QuerySet):
    def visible(self):
        """Annonces réellement achetables.

        Un produit « sur commande » reste visible même sans stock : le vendeur
        va le chercher, et le client connaît le délai avant de payer.
        """
        return self.filter(is_available=True, is_approved=True).filter(
            models.Q(stock__gt=0) | models.Q(made_to_order=True)
        ).exclude(seller__profile__is_store_suspended=True)

    def in_country(self, country):
        """Le catalogue est local : on ne montre que le pays affiché."""
        if country is None:
            return self
        return self.filter(models.Q(country=country) | models.Q(country__isnull=True))

    def with_stats(self):
        return self.annotate(
            avg_rating=Avg("reviews__rating"), review_count=Count("reviews", distinct=True)
        )


class Product(models.Model):
    class Condition(models.TextChoices):
        NEW = "new", "Neuf"
        USED = "used", "Occasion"
        REFURB = "refurb", "Reconditionné"

    name = models.CharField("Nom", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField()
    short_description = models.CharField(max_length=300, blank=True)

    base_price = models.DecimalField(
        "Prix vendeur", max_digits=12, decimal_places=0, default=0,
        help_text="Ce que le vendeur touche avant commission, en FCFA",
    )
    compare_price = models.DecimalField(
        "Prix barré", max_digits=12, decimal_places=0, null=True, blank=True,
        help_text="Prix avant promotion (facultatif)",
    )
    commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("5.00"),
        help_text="Commission EazyMarket appliquée à ce produit (%)",
    )

    stock = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField("En vente", default=True)
    is_approved = models.BooleanField(
        "Validé par la modération", default=True,
        help_text="Décocher pour retirer temporairement une annonce",
    )
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.NEW)

    main_image = models.ImageField(upload_to="products/", blank=True, null=True)

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="products", null=True, blank=True,
    )
    country = models.ForeignKey(
        "regions.Country", on_delete=models.PROTECT, null=True, blank=True,
        related_name="products", verbose_name="Pays",
    )

    weight = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    dimensions = models.CharField(max_length=100, blank=True)
    warranty_months = models.PositiveIntegerField("Garantie (mois)", default=0)
    delivery_available = models.BooleanField("Livraison possible", default=True)
    made_to_order = models.BooleanField(
        "Sur commande", default=False,
        help_text="Vous ne le gardez pas en stock : vous allez le chercher après la commande",
    )
    lead_time_days = models.PositiveIntegerField(
        "Délai de mise à disposition (jours)", default=2,
        help_text="Affiché au client avant qu'il paie, si le produit est sur commande",
    )
    pickup_address = models.CharField("Adresse de retrait", max_length=200, blank=True)

    is_featured = models.BooleanField(default=False)
    boosted_until = models.DateTimeField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    num_reviews = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)

    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        verbose_name = "Produit"
        ordering = ["-is_featured", "-created_at"]
        indexes = [
            models.Index(fields=["is_available", "is_approved"]),
            models.Index(fields=["category", "-created_at"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from EazyMarket.imagerie import optimiser_champ_image
        optimiser_champ_image(self, "main_image")
        if self.country_id is None and self.seller_id:
            profile = getattr(self.seller, "profile", None)
            if profile is not None and profile.country_id:
                self.country_id = profile.country_id
        if self.country_id is None:
            from regions.models import Country

            default = Country.default()
            if default:
                self.country_id = default.pk
        if not self.slug:
            base = slugify(self.name) or "produit"
            slug, counter = base, 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("product_detail", args=[self.slug])

    # ---------- Prix ----------
    # Le vendeur saisit ce qu'il veut TOUCHER (base_price).
    # On ajoute la commission, puis on arrondit le total au palier supérieur
    # pour afficher un prix lisible : 1 000 F devient 1 100 F, jamais 1 050 F.
    # Le vendeur touche exactement son prix ; la plateforme garde la différence.

    @property
    def rate(self):
        # Le taux peut arriver en float (valeur du .env) : on normalise.
        return Decimal(str(self.commission_rate or 0)) / Decimal("100")

    @staticmethod
    def _step_for(amount):
        for ceiling, step in settings.EAZYMARKET["PRICE_STEPS"]:
            if amount <= ceiling:
                return Decimal(step)
        return Decimal("1000")

    @property
    def price(self):
        """Prix affiché à l'acheteur, arrondi au palier supérieur.

        Une commission à 0 % (boutique officielle) affiche le prix tel quel :
        pas de plancher, pas d'arrondi qui gonflerait le prix pour rien.
        """
        base = self.base_price or Decimal("0")
        if base <= 0:
            return Decimal("0")
        if self.rate <= 0:
            return base
        floor = Decimal(settings.EAZYMARKET["COMMISSION_MIN"])
        target = base + max(base * self.rate, floor)
        step = self._step_for(target)
        return (target / step).quantize(Decimal("1"), rounding=ROUND_CEILING) * step

    @property
    def commission_amount(self):
        """Ce que garde la plateforme : la différence entre affiché et vendeur."""
        return self.price - (self.base_price or Decimal("0"))

    @property
    def commission_percent(self):
        base = self.base_price or Decimal("0")
        if base <= 0:
            return 0
        return round(float(self.commission_amount / base * 100), 1)

    @property
    def discount_percentage(self):
        if self.compare_price and self.compare_price > self.price:
            return int(round((1 - self.price / self.compare_price) * 100))
        return 0

    @property
    def in_stock(self):
        if not (self.is_available and self.is_approved):
            return False
        return self.stock > 0 or self.made_to_order

    @property
    def max_quantity(self):
        """Quantité maximum commandable.

        Un article « sur commande » n'a pas de stock : le vendeur va le
        chercher. On plafonne quand même, pour éviter les commandes farfelues.
        """
        if self.made_to_order:
            return max(self.stock, settings.EAZYMARKET.get("MADE_TO_ORDER_MAX", 20))
        return self.stock

    @property
    def stock_label(self):
        if self.is_available and self.is_approved and self.made_to_order and self.stock <= 0:
            return f"Sur commande — livré sous {self.lead_time_days} jour{'s' if self.lead_time_days > 1 else ''}"
        if not self.in_stock:
            return "Épuisé"
        if self.stock <= 3:
            return f"Plus que {self.stock} en stock"
        return "En stock"

    @property
    def stock_badge(self):
        if not self.in_stock:
            return "danger"
        if self.made_to_order and self.stock <= 0:
            return "info"
        return "success"

    @property
    def image_url(self):
        if self.main_image:
            return self.main_image.url
        return None


class ProductImage(models.Model):
    """Photos supplémentaires d'un produit."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to="products/")
    alt = models.CharField(max_length=150, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Photo produit"
        verbose_name_plural = "Photos produit"
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        from EazyMarket.imagerie import optimiser_champ_image
        optimiser_champ_image(self, "image")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Photo de {self.product.name}"


class ProductReview(models.Model):
    """Avis d'un acheteur — uniquement après achat confirmé."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(choices=[(i, f"{i} étoile{'s' if i > 1 else ''}") for i in range(1, 6)])
    comment = models.TextField()
    is_verified_purchase = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Avis produit"
        verbose_name_plural = "Avis produits"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], name="un_avis_par_produit_et_client")
        ]

    def __str__(self):
        return f"{self.user.username} — {self.product.name} ({self.rating}★)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        stats = ProductReview.objects.filter(product=self.product).aggregate(
            avg=Avg("rating"), n=Count("id")
        )
        Product.objects.filter(pk=self.product_id).update(
            rating=stats["avg"] or 0, num_reviews=stats["n"] or 0
        )


class Favorite(models.Model):
    """Liste d'envies."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Favori"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="un_favori_par_produit")
        ]

    def __str__(self):
        return f"{self.user.username} ♥ {self.product.name}"
