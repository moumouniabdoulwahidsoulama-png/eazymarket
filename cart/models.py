"""Panier d'achat."""

from decimal import Decimal

from django.conf import settings
from django.db import models

from products.models import Product


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Panier"

    def __str__(self):
        return f"Panier de {self.user.username}"

    @property
    def items_list(self):
        return self.items.select_related("product__category", "product__seller")

    @property
    def subtotal(self):
        return sum((item.subtotal for item in self.items_list), Decimal("0"))

    @property
    def total(self):
        return self.subtotal

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def sellers_count(self):
        return len({i.product.seller_id for i in self.items_list if i.product.seller_id})

    def delivery_fee(self, mode="delivery", city=None):
        conf = settings.EAZYMARKET
        if mode == "pickup":
            return Decimal("0")
        if self.subtotal >= conf["FREE_DELIVERY_FROM"]:
            return Decimal("0")
        same_city = (city or conf["CITY"]).strip().lower() == conf["CITY"].strip().lower()
        return Decimal(conf["DELIVERY_FEE_CITY"] if same_city else conf["DELIVERY_FEE_OUT"])

    def has_stock_issue(self):
        return [
            i for i in self.items_list
            if not i.product.in_stock or i.quantity > i.product.max_quantity
        ]


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Article du panier"
        verbose_name_plural = "Articles du panier"
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="un_article_par_panier")
        ]

    def __str__(self):
        return f"{self.quantity}× {self.product.name}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    @property
    def commission(self):
        return self.product.commission_amount * self.quantity
