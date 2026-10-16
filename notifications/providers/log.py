"""Fournisseur par défaut : rien n'est envoyé, tout est tracé.

Permet de développer et de mettre en ligne sans compte SMS. Les messages
apparaissent dans logs/eazymarket.log et dans le back-office.
"""

import logging

from .base import SmsProvider, SmsResult

logger = logging.getLogger("notifications")


class LogProvider(SmsProvider):
    name = "log"
    label = "Journal (aucun envoi réel)"

    def send(self, numero, texte):
        numero = self.normaliser(numero)
        if not numero:
            return SmsResult(ok=False, message="Numéro absent ou invalide")
        logger.info("SMS (simulé) vers %s : %s", numero, self.raccourcir(texte))
        return SmsResult(ok=True, reference="log", message="Simulé — aucun fournisseur configuré")
