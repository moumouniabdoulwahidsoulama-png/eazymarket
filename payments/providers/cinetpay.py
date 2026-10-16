"""
Agrégateur CinetPay — Orange Money, Moov Money, Wave et cartes en une
seule intégration (Afrique de l'Ouest, FCFA/XOF).

Documentation : https://docs.cinetpay.com
Il faut un compte marchand et trois valeurs dans le .env :
CINETPAY_API_KEY, CINETPAY_SITE_ID, CINETPAY_SECRET_KEY.

Le même code fonctionne avec un autre agrégateur (PayDunya, LigdiCash,
FedaPay) : il suffit de copier ce fichier et d'adapter les URLs.
"""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.urls import reverse

from .base import PaymentProvider, PaymentResult

logger = logging.getLogger("payments")


class CinetPayProvider(PaymentProvider):
    name = "cinetpay"
    label = "Mobile Money & carte (automatique)"
    channels = ["orange_money", "moov_money", "wave", "card"]
    automatic = True

    @property
    def conf(self):
        return settings.PAYMENTS.get("CINETPAY", {})

    @property
    def is_configured(self):
        return bool(self.conf.get("API_KEY") and self.conf.get("SITE_ID"))

    # ------------------------------------------------------------------
    def _post(self, path, payload):
        try:
            import requests
        except ImportError:  # pragma: no cover
            raise RuntimeError(
                "Le paquet « requests » est nécessaire : pip install requests"
            )
        url = f"{self.conf['BASE_URL'].rstrip('/')}/{path.lstrip('/')}"
        response = requests.post(url, json=payload, timeout=25)
        response.raise_for_status()
        return response.json()

    def _absolute(self, path):
        base = settings.PAYMENTS.get("PUBLIC_BASE_URL", "").rstrip("/")
        return f"{base}{path}"

    # ------------------------------------------------------------------
    def initiate(self, tx, request=None, **kwargs):
        if not self.is_configured:
            return PaymentResult(
                ok=False,
                message="CinetPay n'est pas configuré (clés manquantes dans le .env).",
            )

        payload = {
            "apikey": self.conf["API_KEY"],
            "site_id": self.conf["SITE_ID"],
            "transaction_id": tx.reference,
            "amount": int(tx.amount),
            "currency": "XOF",
            "description": f"{settings.EAZYMARKET['SITE_NAME']} — {tx.get_purpose_display()}",
            "channels": "ALL",
            "lang": "fr",
            "return_url": self._absolute(reverse("payment_return", args=[tx.reference])),
            "notify_url": self._absolute(reverse("payment_webhook")),
            "customer_name": (tx.user.last_name or tx.user.username)[:50],
            "customer_surname": (tx.user.first_name or "")[:50],
            "customer_email": tx.user.email or "",
            "customer_phone_number": tx.payer_number or "",
            "metadata": json.dumps({"user_id": tx.user_id, "purpose": tx.purpose}),
        }

        try:
            data = self._post("payment", payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("CinetPay : échec de l'initialisation (%s)", tx.reference)
            return PaymentResult(ok=False, message=f"Service de paiement indisponible ({exc}).")

        tx.provider = self.name
        tx.raw_response = data
        code = str(data.get("code"))
        if code != "201":
            tx.status = tx.Status.FAILED
            tx.notes = data.get("description", "")
            tx.save(update_fields=["provider", "raw_response", "status", "notes"])
            return PaymentResult(ok=False, message=data.get("description", "Paiement refusé."))

        token = data.get("data", {}).get("payment_token", "")
        url = data.get("data", {}).get("payment_url", "")
        tx.provider_reference = token
        tx.status = tx.Status.PENDING
        tx.save(update_fields=["provider", "raw_response", "provider_reference", "status"])
        return PaymentResult(
            ok=True, mode="redirect", redirect_url=url, provider_reference=token
        )

    # ------------------------------------------------------------------
    def verify(self, tx):
        """Vérifie l'état réel auprès de CinetPay (source de vérité)."""
        if not self.is_configured:
            return False
        payload = {
            "apikey": self.conf["API_KEY"],
            "site_id": self.conf["SITE_ID"],
            "transaction_id": tx.reference,
        }
        try:
            data = self._post("payment/check", payload)
        except Exception:  # noqa: BLE001
            logger.exception("CinetPay : échec de la vérification (%s)", tx.reference)
            return False

        tx.raw_response = data
        info = data.get("data", {}) or {}
        status = str(info.get("status", "")).upper()
        tx.provider_reference = info.get("operator_id", tx.provider_reference)
        tx.payer_number = info.get("phone_number", tx.payer_number) or ""
        tx.save(update_fields=["raw_response", "provider_reference", "payer_number"])
        return status == "ACCEPTED"

    # ------------------------------------------------------------------
    def handle_webhook(self, request):
        """CinetPay notifie en POST ; on re-vérifie toujours côté serveur."""
        from payments.models import Transaction

        reference = request.POST.get("cpm_trans_id") or request.POST.get("transaction_id")
        if not reference:
            return None, False

        secret = self.conf.get("SECRET_KEY", "")
        signature = request.headers.get("x-token", "")
        if secret and signature:
            fields = [
                "cpm_site_id", "cpm_trans_id", "cpm_trans_date", "cpm_amount",
                "cpm_currency", "signature", "payment_method", "cel_phone_num",
                "cpm_phone_prefixe", "cpm_language", "cpm_version",
                "cpm_payment_config", "cpm_page_action", "cpm_custom",
                "cpm_designation", "cpm_error_message",
            ]
            raw = "".join(request.POST.get(f, "") for f in fields)
            expected = hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                logger.warning("CinetPay : signature invalide pour %s", reference)
                return None, False

        try:
            tx = Transaction.objects.get(reference=reference)
        except Transaction.DoesNotExist:
            logger.warning("CinetPay : transaction inconnue %s", reference)
            return None, False

        return tx, self.verify(tx)

    # ------------------------------------------------------------------
    def payout(self, payout):
        """Reversement automatique (API Transfer, à activer sur le compte)."""
        return False, (
            "Le transfert automatique n'est pas activé. Effectuez le retrait "
            "depuis votre tableau de bord CinetPay puis marquez-le comme versé."
        )
