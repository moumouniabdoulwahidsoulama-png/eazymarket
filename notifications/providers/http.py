"""
Fournisseur générique : n'importe quelle passerelle SMS avec une API HTTP.

La plupart des agrégateurs ouest-africains exposent une simple URL à appeler
avec le numéro, le message et un jeton. Il suffit de renseigner les noms des
champs dans le .env — aucun code à écrire.
"""

import logging

from django.conf import settings

from .base import SmsProvider, SmsResult

logger = logging.getLogger("notifications")


class HttpProvider(SmsProvider):
    name = "http"
    label = "Passerelle SMS (API HTTP)"

    @property
    def conf(self):
        return settings.NOTIFICATIONS.get("HTTP", {})

    def send(self, numero, texte):
        url = self.conf.get("URL")
        if not url:
            return SmsResult(ok=False, message="SMS_HTTP_URL n'est pas renseigné")

        numero = self.normaliser(numero)
        if not numero:
            return SmsResult(ok=False, message="Numéro absent ou invalide")

        try:
            import requests
        except ImportError:
            return SmsResult(ok=False, message="Le paquet « requests » est nécessaire")

        donnees = {
            self.conf.get("FIELD_TO", "to"): numero,
            self.conf.get("FIELD_MESSAGE", "message"): self.raccourcir(texte),
            self.conf.get("FIELD_SENDER", "sender"): settings.NOTIFICATIONS.get("SMS_SENDER", ""),
        }
        entetes = {}
        if self.conf.get("TOKEN"):
            entetes["Authorization"] = f"Bearer {self.conf['TOKEN']}"

        try:
            methode = (self.conf.get("METHOD") or "POST").upper()
            reponse = requests.request(
                methode, url,
                json=donnees if methode != "GET" else None,
                params=donnees if methode == "GET" else None,
                headers=entetes, timeout=15,
            )
            reponse.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("SMS non envoyé vers %s : %s", numero, exc)
            return SmsResult(ok=False, message=str(exc))

        return SmsResult(ok=True, reference=str(reponse.status_code))
