"""Fournisseurs de paiement enfichables.

Ajouter un opérateur = ajouter un fichier ici et l'inscrire dans REGISTRY.
Le reste de l'application ne connaît que `get_provider()`.
"""

from django.conf import settings

from .base import PaymentProvider, PaymentResult
from .manual import ManualProvider
from .cinetpay import CinetPayProvider

REGISTRY = {
    "manual": ManualProvider,
    "cinetpay": CinetPayProvider,
}


def get_provider(name=None):
    name = name or settings.PAYMENTS.get("PROVIDER", "manual")
    cls = REGISTRY.get(name, ManualProvider)
    return cls()


__all__ = ["PaymentProvider", "PaymentResult", "get_provider", "REGISTRY"]
