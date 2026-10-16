"""Créé un panier dès l'inscription (évite un cas particulier partout ailleurs)."""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Cart


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_cart(sender, instance, created, **kwargs):
    if created:
        Cart.objects.get_or_create(user=instance)
