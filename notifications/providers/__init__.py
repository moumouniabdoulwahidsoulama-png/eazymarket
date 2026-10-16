"""Fournisseurs SMS enfichables.

Ajouter un opérateur = un fichier ici et une ligne dans REGISTRY.
Le reste de l'application ne connaît que `get_sms_provider()`.
"""

from django.conf import settings

from .base import SmsProvider, SmsResult
from .http import HttpProvider
from .log import LogProvider
from .orange import OrangeProvider

REGISTRY = {
    "log": LogProvider,
    "http": HttpProvider,
    "orange": OrangeProvider,
}


def get_sms_provider(name=None):
    name = name or settings.NOTIFICATIONS.get("SMS_PROVIDER", "log")
    return REGISTRY.get(name, LogProvider)()


__all__ = ["SmsProvider", "SmsResult", "get_sms_provider", "REGISTRY"]
