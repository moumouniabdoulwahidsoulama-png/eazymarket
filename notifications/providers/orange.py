"""
Orange SMS API (Burkina Faso).

Compte à ouvrir sur developer.orange.com, puis renseigner l'identifiant et le
secret dans le .env. Les SMS s'achètent par paquets.
"""

import logging

from django.conf import settings

from .base import SmsProvider, SmsResult

logger = logging.getLogger("notifications")


class OrangeProvider(SmsProvider):
    name = "orange"
    label = "Orange SMS API"

    _jeton = None

    @property
    def conf(self):
        return settings.NOTIFICATIONS.get("ORANGE", {})

    def _obtenir_jeton(self, requests):
        if self._jeton:
            return self._jeton
        reponse = requests.post(
            f"{self.conf['BASE_URL'].rstrip('/')}/oauth/v3/token",
            data={"grant_type": "client_credentials"},
            auth=(self.conf["CLIENT_ID"], self.conf["CLIENT_SECRET"]),
            timeout=15,
        )
        reponse.raise_for_status()
        OrangeProvider._jeton = reponse.json()["access_token"]
        return self._jeton

    def send(self, numero, texte):
        if not (self.conf.get("CLIENT_ID") and self.conf.get("SENDER_NUMBER")):
            return SmsResult(ok=False, message="Identifiants Orange SMS absents")

        numero = self.normaliser(numero)
        if not numero:
            return SmsResult(ok=False, message="Numéro absent ou invalide")

        try:
            import requests
        except ImportError:
            return SmsResult(ok=False, message="Le paquet « requests » est nécessaire")

        expediteur = self.normaliser(self.conf["SENDER_NUMBER"])
        try:
            jeton = self._obtenir_jeton(requests)
            reponse = requests.post(
                f"{self.conf['BASE_URL'].rstrip('/')}/smsmessaging/v1/outbound/"
                f"tel%3A%2B{expediteur}/requests",
                headers={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"},
                json={
                    "outboundSMSMessageRequest": {
                        "address": f"tel:+{numero}",
                        "senderAddress": f"tel:+{expediteur}",
                        "senderName": settings.NOTIFICATIONS.get("SMS_SENDER", ""),
                        "outboundSMSTextMessage": {"message": self.raccourcir(texte, 160)},
                    }
                },
                timeout=20,
            )
            reponse.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            OrangeProvider._jeton = None  # le jeton a peut-être expiré
            logger.warning("SMS Orange non envoyé vers %s : %s", numero, exc)
            return SmsResult(ok=False, message=str(exc))

        return SmsResult(ok=True, reference="orange")
