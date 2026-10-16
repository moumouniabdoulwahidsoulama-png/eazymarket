"""
Installe les pays, les villes principales et les comptes d'encaissement.

    python manage.py init_pays

Seul le Burkina Faso est ouvert au public. Les autres pays sont créés
« en préparation » : ils n'apparaissent pas dans le sélecteur tant que vous
ne les activez pas depuis l'administration. Un pays ne s'ouvre que lorsqu'il
a des vendeurs, des livreurs et un numéro pour encaisser sur place.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from regions.models import City, Country, PaymentAccount

# (nom, code, drapeau, indicatif, devise, symbole, ville principale, actif)
PAYS = [
    ("Burkina Faso", "BF", "🇧🇫", "+226", "XOF", "FCFA", "Ouagadougou", True),
    ("Côte d'Ivoire", "CI", "🇨🇮", "+225", "XOF", "FCFA", "Abidjan", False),
    ("Mali", "ML", "🇲🇱", "+223", "XOF", "FCFA", "Bamako", False),
    ("Sénégal", "SN", "🇸🇳", "+221", "XOF", "FCFA", "Dakar", False),
    ("Niger", "NE", "🇳🇪", "+227", "XOF", "FCFA", "Niamey", False),
    ("Bénin", "BJ", "🇧🇯", "+229", "XOF", "FCFA", "Cotonou", False),
    ("Togo", "TG", "🇹🇬", "+228", "XOF", "FCFA", "Lomé", False),
    ("Guinée", "GN", "🇬🇳", "+224", "GNF", "GNF", "Conakry", False),
    ("Ghana", "GH", "🇬🇭", "+233", "GHS", "GH₵", "Accra", False),
    ("Nigeria", "NG", "🇳🇬", "+234", "NGN", "₦", "Lagos", False),
    ("Cameroun", "CM", "🇨🇲", "+237", "XAF", "FCFA", "Douala", False),
    ("Tchad", "TD", "🇹🇩", "+235", "XAF", "FCFA", "N'Djaména", False),
]

VILLES = {
    "BF": ["Ouagadougou", "Bobo-Dioulasso", "Koudougou", "Ouahigouya", "Banfora",
           "Kaya", "Tenkodogo", "Fada N'Gourma", "Dédougou", "Dori", "Gaoua", "Ziniaré"],
    "CI": ["Abidjan", "Bouaké", "Yamoussoukro", "Korhogo", "San-Pédro", "Daloa"],
    "ML": ["Bamako", "Sikasso", "Ségou", "Mopti", "Koutiala", "Kayes"],
    "SN": ["Dakar", "Thiès", "Touba", "Saint-Louis", "Ziguinchor", "Kaolack"],
    "NE": ["Niamey", "Zinder", "Maradi", "Agadez", "Tahoua"],
    "BJ": ["Cotonou", "Porto-Novo", "Parakou", "Abomey-Calavi"],
    "TG": ["Lomé", "Sokodé", "Kara", "Kpalimé"],
}


class Command(BaseCommand):
    help = "Crée les pays, leurs villes et les comptes d'encaissement du pays par défaut."

    @transaction.atomic
    def handle(self, *args, **options):
        nouveaux = 0
        for order, (name, code, flag, dial, cur, sym, city, actif) in enumerate(PAYS):
            country, created = Country.objects.get_or_create(
                code=code,
                defaults={
                    "name": name, "flag": flag, "dial_code": dial,
                    "currency_code": cur, "currency_symbol": sym,
                    "main_city": city, "is_active": actif,
                    "is_default": code == "BF", "order": order,
                },
            )
            nouveaux += created
            if not created:
                country.flag = flag
                country.dial_code = dial
                country.order = order
                country.save(update_fields=["flag", "dial_code", "order"])

            for index, ville in enumerate(VILLES.get(code, [city])):
                City.objects.get_or_create(
                    country=country, name=ville,
                    defaults={"is_main": index == 0, "order": index},
                )

        self.stdout.write(self.style.SUCCESS(
            f"{len(PAYS)} pays en place ({nouveaux} nouveaux), "
            f"{City.objects.count()} villes."
        ))

        # --- Comptes d'encaissement du pays par défaut, repris du .env ---
        default = Country.objects.filter(is_default=True).first()
        if not default:
            return

        conf = settings.PAYMENTS.get("MANUAL", {})
        holder = conf.get("HOLDER") or settings.EAZYMARKET["SITE_NAME"]
        template = conf.get("USSD_TEMPLATE", "*144*10*{numero}*{montant}#")

        comptes = []
        for index, account in enumerate(conf.get("ACCOUNTS", [])):
            if account.get("number"):
                comptes.append({
                    "channel": PaymentAccount.Channel.ORANGE,
                    "label": account.get("label") or "Orange Money",
                    "number": account["number"],
                    "holder": account.get("name") or holder,
                    "ussd_template": template,
                    "menu_hint": "#144#",
                    "whatsapp": account.get("whatsapp", ""),
                    "order": index,
                })
        if conf.get("MOOV_MONEY_NUMBER"):
            comptes.append({
                "channel": PaymentAccount.Channel.MOOV, "label": "Moov Money",
                "number": conf["MOOV_MONEY_NUMBER"], "holder": holder,
                "ussd_template": "", "menu_hint": "*555#", "whatsapp": "", "order": 10,
            })
        if conf.get("WAVE_NUMBER"):
            comptes.append({
                "channel": PaymentAccount.Channel.WAVE, "label": "Wave",
                "number": conf["WAVE_NUMBER"], "holder": holder,
                "ussd_template": "", "menu_hint": "Application Wave",
                "whatsapp": conf.get("WAVE_WHATSAPP", ""), "order": 20,
            })

        created = 0
        for compte in comptes:
            _, was_created = PaymentAccount.objects.get_or_create(
                country=default, channel=compte["channel"], number=compte["number"],
                defaults=compte,
            )
            created += was_created

        if comptes:
            self.stdout.write(self.style.SUCCESS(
                f"{len(comptes)} compte(s) d'encaissement pour {default.name} ({created} nouveaux)."
            ))
        else:
            self.stdout.write(self.style.WARNING(
                "Aucun numéro dans le .env : ajoutez vos comptes d'encaissement "
                "depuis Administration → Pays & villes."
            ))
        self.stdout.write(
            "Pour ouvrir un nouveau pays : Administration → Pays, cochez « Ouvert au public », "
            "et ajoutez-y au moins un compte d'encaissement local."
        )
