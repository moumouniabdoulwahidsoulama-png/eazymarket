"""Contrat commun à tous les fournisseurs de paiement."""

from dataclasses import dataclass, field


@dataclass
class PaymentResult:
    """Ce que retourne une initialisation de paiement."""

    ok: bool
    # "redirect"  -> l'utilisateur part sur la page de l'opérateur
    # "instructions" -> on affiche une marche à suivre dans l'application
    mode: str = "instructions"
    redirect_url: str = ""
    provider_reference: str = ""
    message: str = ""
    payload: dict = field(default_factory=dict)


class PaymentProvider:
    """Interface. Chaque fournisseur implémente ces quatre méthodes."""

    name = "base"
    label = "Fournisseur"
    #: canaux proposés à l'utilisateur (valeurs de Transaction.Channel)
    channels = []
    #: True si la confirmation arrive automatiquement (webhook / API)
    automatic = False

    def initiate(self, tx, request=None, **kwargs):
        """Démarre le paiement pour une Transaction. Retourne un PaymentResult."""
        raise NotImplementedError

    def verify(self, tx):
        """Interroge l'opérateur et retourne True si le paiement est confirmé."""
        return False

    def handle_webhook(self, request):
        """Traite une notification serveur-à-serveur. Retourne (Transaction|None, bool)."""
        return None, False

    def payout(self, payout):
        """Envoie l'argent au vendeur. Retourne (ok: bool, message: str)."""
        return False, "Reversement manuel : à effectuer depuis votre application mobile money."
