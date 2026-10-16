"""
Encaissement manuel sur vos numéros mobile money.

Les numéros sont enregistrés **en base**, pays par pays
(Administration → Pays & villes → Comptes d'encaissement). Ouvrir un nouveau
pays consiste donc à y ajouter un numéro local : aucun code à modifier.

Si la base est vide, on retombe sur les numéros du fichier `.env` — ce qui
permet de démarrer sans rien configurer.
"""

from django.conf import settings

from .base import PaymentProvider, PaymentResult


class ManualProvider(PaymentProvider):
    name = "manual"
    label = "Mobile Money (validation manuelle)"
    channels = ["orange_money", "moov_money", "wave", "mtn_money", "airtel_money", "cash"]
    automatic = False

    # ------------------------------------------------------------------
    @property
    def conf(self):
        return settings.PAYMENTS.get("MANUAL", {})

    def _db_accounts(self, country):
        """Comptes enregistrés en base pour ce pays."""
        if country is None:
            return []
        try:
            return list(country.payment_accounts.filter(is_active=True))
        except Exception:
            return []

    def _env_accounts(self, amount):
        """Repli : les numéros du fichier .env, si la base n'a rien."""
        template = self.conf.get("USSD_TEMPLATE", "*144*10*{numero}*{montant}#")
        indicatif = "226"
        result = []

        def digits(number):
            raw = "".join(c for c in str(number) if c.isdigit())
            if raw.startswith(indicatif) and len(raw) > len(indicatif):
                raw = raw[len(indicatif):]
            return raw

        for account in self.conf.get("ACCOUNTS", []):
            if not account.get("number"):
                continue
            result.append({
                "id": account.get("id"),
                "channel": "orange_money",
                "label": account.get("label") or "Orange Money",
                "number": account["number"],
                "name": account.get("name", ""),
                "ussd": template.format(numero=digits(account["number"]), montant=int(amount)),
                "menu": "#144#",
                "whatsapp": account.get("whatsapp", ""),
            })
        for key, channel, label, menu in (
            ("MOOV_MONEY_NUMBER", "moov_money", "Moov Money", "*555#"),
            ("WAVE_NUMBER", "wave", "Wave", "Application Wave"),
        ):
            number = self.conf.get(key)
            if number:
                result.append({
                    "id": channel, "channel": channel, "label": label, "number": number,
                    "name": self.conf.get("HOLDER", ""), "ussd": "", "menu": menu,
                    "whatsapp": self.conf.get(f"{channel.upper()}_WHATSAPP", ""),
                })
        return result

    def _all_accounts(self, country, amount):
        accounts = self._db_accounts(country)
        if accounts:
            return [a.as_dict(amount) for a in accounts]
        return self._env_accounts(amount)

    # ------------------------------------------------------------------
    def accounts_for(self, channel, amount, country=None):
        """Comptes à afficher pour un canal, code à composer inclus."""
        accounts = self._all_accounts(country, amount)
        if not channel:
            return accounts
        return [a for a in accounts if a["channel"] == channel]

    def available_channels(self, country=None):
        seen = []
        for account in self._all_accounts(country, 0):
            if account["channel"] not in seen:
                seen.append(account["channel"])
        return seen or ["orange_money"]

    @staticmethod
    def country_of(tx):
        profile = getattr(tx.user, "profile", None)
        if profile is not None and profile.country_id:
            return profile.country
        try:
            from regions.models import Country

            return Country.default()
        except Exception:
            return None

    # ------------------------------------------------------------------
    def initiate(self, tx, request=None, **kwargs):
        country = kwargs.get("country") or self.country_of(tx)
        accounts = self.accounts_for(tx.channel or "", tx.amount, country)
        if not accounts:
            return PaymentResult(
                ok=False,
                message=(
                    "Aucun numéro d'encaissement n'est configuré pour ce moyen de paiement. "
                    "Ajoutez-en un dans Administration → Pays & villes → Comptes d'encaissement."
                ),
            )
        tx.provider = self.name
        tx.status = tx.Status.PENDING
        tx.save(update_fields=["provider", "status"])
        return PaymentResult(
            ok=True,
            mode="instructions",
            message="Suivez les instructions pour finaliser le paiement.",
            payload={"accounts": accounts, "reference": tx.reference, "amount": tx.amount},
        )

    def verify(self, tx):
        # Aucune API : la confirmation passe par un administrateur.
        return tx.status == tx.Status.SUCCESS
