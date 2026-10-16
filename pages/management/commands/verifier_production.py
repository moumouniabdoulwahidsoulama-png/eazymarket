"""
Contrôle avant (et après) la mise en ligne.

    python manage.py verifier_production

Passe en revue tout ce qui casse un déploiement Django sur un hébergement
mutualisé, et dit quoi corriger. À relancer après chaque mise à jour.
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Vérifie que la configuration est prête pour la production."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.erreurs = 0
        self.alertes = 0

    # ------------------------------------------------------------------
    def ok(self, message):
        self.stdout.write(self.style.SUCCESS(f"  [ok]      {message}"))

    def alerte(self, message, quoi_faire=""):
        self.alertes += 1
        self.stdout.write(self.style.WARNING(f"  [à voir]  {message}"))
        if quoi_faire:
            self.stdout.write(f"            → {quoi_faire}")

    def erreur(self, message, quoi_faire=""):
        self.erreurs += 1
        self.stdout.write(self.style.ERROR(f"  [ERREUR]  {message}"))
        if quoi_faire:
            self.stdout.write(f"            → {quoi_faire}")

    def titre(self, texte):
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO(texte))

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("\nVérification de la configuration EazyMarket"))
        self.stdout.write("=" * 62)

        self._securite()
        self._base_de_donnees()
        self._fichiers()
        self._donnees()
        self._paiements()
        self._email()
        self._artisans()
        self._notifications()

        self.stdout.write("")
        self.stdout.write("=" * 62)
        if self.erreurs:
            self.stdout.write(self.style.ERROR(
                f"{self.erreurs} problème(s) bloquant(s) et {self.alertes} point(s) à surveiller."
            ))
            self.stdout.write("Corrigez les [ERREUR] avant d'ouvrir le site au public.")
        elif self.alertes:
            self.stdout.write(self.style.WARNING(
                f"Aucun problème bloquant. {self.alertes} point(s) à surveiller."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("Tout est en ordre. Le site peut être ouvert."))
        self.stdout.write("")

    # ------------------------------------------------------------------
    def _securite(self):
        self.titre("Sécurité")

        if not getattr(settings, "DOTENV_TROUVE", True):
            self.erreur(
                "AUCUN FICHIER .env : l'application tourne sur ses valeurs par "
                "défaut (base SQLite vide, DEBUG activé). Toutes les lignes "
                "ci-dessous en découlent — corrigez celle-ci d'abord.",
                "Reposer votre .env à la racine de l'application, "
                "ou le régénérer : python deploiement/configurer.py",
            )

        if settings.DEBUG:
            self.erreur(
                "DEBUG est activé : la moindre erreur affichera votre configuration aux visiteurs.",
                "Mettre DJANGO_DEBUG=False dans le fichier .env",
            )
        else:
            self.ok("DEBUG désactivé")

        cle = settings.SECRET_KEY
        if "dev-only" in cle or len(cle) < 40:
            self.erreur(
                "La clé secrète est celle du développement.",
                'Générer : python -c "import secrets;print(secrets.token_urlsafe(60))" '
                "puis la mettre dans DJANGO_SECRET_KEY",
            )
        else:
            self.ok("Clé secrète propre à cette installation")

        hosts = [h for h in settings.ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1", "[::1]")]
        if not hosts:
            self.erreur(
                "Aucun nom de domaine dans ALLOWED_HOSTS : le site répondra « Bad Request ».",
                "Renseigner DJANGO_ALLOWED_HOSTS avec votre sous-domaine",
            )
        elif "*" in settings.ALLOWED_HOSTS:
            self.erreur("ALLOWED_HOSTS contient « * » : à ne jamais faire en production.")
        else:
            self.ok(f"Domaines autorisés : {', '.join(hosts)}")

        repares = getattr(settings, "HOSTS_REPARES", [])
        if repares:
            for brut, propre in repares:
                self.alerte(
                    f"Domaine mal recopié dans le .env : {brut}",
                    f"Corrigé au vol en « {propre} », mais remettez la valeur "
                    "propre dans le .env — un domaine collé depuis une "
                    "discussion arrive souvent transformé en lien.",
                )

        if not settings.DEBUG and not settings.CSRF_TRUSTED_ORIGINS:
            self.alerte(
                "CSRF_TRUSTED_ORIGINS est vide : les formulaires peuvent être refusés en HTTPS.",
                "Renseigner DJANGO_CSRF_TRUSTED_ORIGINS avec https://votre-sous-domaine",
            )
        elif settings.CSRF_TRUSTED_ORIGINS:
            self.ok("Origines de confiance renseignées")

        base = settings.PAYMENTS.get("PUBLIC_BASE_URL", "")
        if not settings.DEBUG and ("127.0.0.1" in base or "localhost" in base):
            self.erreur(
                "PUBLIC_BASE_URL pointe encore vers votre ordinateur.",
                "Mettre l'adresse publique du site (https://...)",
            )
        elif base:
            self.ok(f"Adresse publique : {base}")

    # ------------------------------------------------------------------
    def _base_de_donnees(self):
        self.titre("Base de données")
        moteur = settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1]

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.ok(f"Connexion établie ({moteur})")
        except Exception as exc:  # noqa: BLE001
            self.erreur(f"Impossible de se connecter à la base ({moteur}) : {exc}",
                        "Vérifier DB_NAME, DB_USER, DB_PASSWORD dans le .env")
            return

        if moteur == "sqlite3" and not settings.DEBUG:
            self.alerte(
                "SQLite en production : un seul écrivain à la fois.",
                "Basculer sur MySQL dès que plusieurs commandes arrivent en même temps",
            )

        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        en_attente = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if en_attente:
            self.erreur(f"{len(en_attente)} migration(s) non appliquée(s).",
                        "Lancer : python manage.py migrate")
        else:
            self.ok("Toutes les migrations sont appliquées")

    # ------------------------------------------------------------------
    def _fichiers(self):
        self.titre("Fichiers statiques et médias")

        static_root = Path(settings.STATIC_ROOT)
        if not static_root.exists() or not any(static_root.iterdir()):
            self.erreur("Les fichiers statiques ne sont pas rassemblés : le site sera sans style.",
                        "Lancer : python manage.py collectstatic --noinput")
        else:
            nb = sum(1 for _ in static_root.rglob("*") if _.is_file())
            self.ok(f"{nb} fichiers statiques dans {static_root}")

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.erreur(f"Le dossier des médias n'existe pas : {media_root}",
                        "Le créer, ou corriger DJANGO_MEDIA_ROOT")
        elif not os.access(media_root, os.W_OK):
            self.erreur(f"Le dossier des médias n'est pas accessible en écriture : {media_root}",
                        "Donner les droits d'écriture (permissions 755)")
        else:
            self.ok(f"Dossier des médias accessible en écriture : {media_root}")
            for nom in ("static", "media"):
                dossier = static_root if nom == "static" else media_root
                if dossier.exists() and not (dossier / ".htaccess").exists() and not settings.DEBUG:
                    self.alerte(
                        f"Pas de .htaccess dans le dossier {nom}.",
                        "Copier deploiement/htaccess-pour-static-et-media.txt "
                        f"vers {dossier}/.htaccess",
                    )

    # ------------------------------------------------------------------
    def _donnees(self):
        self.titre("Données de départ")
        from django.contrib.auth import get_user_model

        from products.models import Category
        from regions.models import Country
        from services.models import ServiceCategory

        if not get_user_model().objects.filter(is_staff=True).exists():
            self.erreur("Aucun compte administrateur.",
                        "Lancer : python manage.py createsuperuser")
        else:
            self.ok("Compte administrateur présent")

        if not Category.objects.exists() or not ServiceCategory.objects.exists():
            self.erreur("Les rayons et les métiers ne sont pas installés.",
                        "Lancer : python manage.py init_catalogue")
        else:
            self.ok(f"{Category.objects.count()} rayons et "
                    f"{ServiceCategory.objects.count()} métiers en place")

        ouverts = Country.objects.filter(is_active=True)
        if not ouverts.exists():
            self.erreur("Aucun pays ouvert : le catalogue sera vide.",
                        "Administration → Pays → cocher « Ouvert au public »")
        else:
            self.ok(f"Pays ouverts : {', '.join(c.name for c in ouverts)}")

    # ------------------------------------------------------------------
    def _paiements(self):
        self.titre("Encaissement")
        from regions.models import Country, PaymentAccount

        for pays in Country.objects.filter(is_active=True):
            comptes = PaymentAccount.objects.filter(country=pays, is_active=True)
            if not comptes.exists():
                self.erreur(f"{pays.name} : aucun numéro d'encaissement, personne ne pourra payer.",
                            "Administration → Pays & villes → Comptes d'encaissement")
            else:
                self.ok(f"{pays.name} : {comptes.count()} moyen(s) de paiement "
                        f"({', '.join(c.get_channel_display() for c in comptes)})")

    # ------------------------------------------------------------------
    def _artisans(self):
        """Une promotion qu'on oublie d'arrêter coûte plus cher qu'elle ne rapporte."""
        from services.models import Artisan

        conf = settings.EAZYMARKET
        jours = conf["ARTISAN_SUB_DAYS"]
        prix = conf["ARTISAN_SUB_PRICE"]

        if conf.get("ARTISAN_FREE_LAUNCH"):
            gratuits = Artisan.objects.filter(subscription_active=False).count()
            self.alerte(
                f"PÉRIODE DE LANCEMENT ACTIVE : les artisans s'inscrivent et "
                f"apparaissent dans l'annuaire SANS payer les {prix} FCFA. "
                f"{gratuits} profil(s) en profitent actuellement.",
                "Quand l'annuaire est assez rempli : ARTISAN_FREE_LAUNCH=False "
                "dans le .env, puis RESTART. Les profils non abonnés "
                "disparaîtront de l'annuaire jusqu'à leur paiement.",
            )
        else:
            self.ok(f"Abonnement artisan exigé : {prix} FCFA pour {jours} jours")

    # ------------------------------------------------------------------
    def _email(self):
        self.titre("E-mail")
        # On teste le chemin complet : les deux backends finissent par
        # « EmailBackend », donc ne regarder que le dernier morceau ne dit rien.
        backend = settings.EMAIL_BACKEND
        if "console" in backend.lower():
            if settings.DEBUG:
                self.ok("Mode développement : les e-mails s'affichent dans la console")
            else:
                self.alerte("Les e-mails ne partent pas (mode console).",
                            "Renseigner EMAIL_HOST, EMAIL_HOST_USER et EMAIL_HOST_PASSWORD")
        elif not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER:
            self.alerte("Envoi SMTP activé mais incomplet : le formulaire de contact échouera.",
                        "Renseigner EMAIL_HOST et EMAIL_HOST_USER dans le .env")
        else:
            self.ok(f"Envoi via {settings.EMAIL_HOST}")

    # ------------------------------------------------------------------
    def _notifications(self):
        self.titre("Notifications et confirmations")
        from orders.models import Order, SellerConfirmation

        conf = settings.NOTIFICATIONS
        heures = settings.EAZYMARKET["ORDER_CONFIRMATION_HOURS"]
        self.ok(f"Le vendeur a {heures} h pour confirmer, sinon le client est remboursé")

        fournisseur = conf.get("SMS_PROVIDER", "log")
        if not conf.get("SMS_ENABLED", True):
            self.alerte("Les SMS sont désactivés (SMS_ENABLED=False).",
                        "Beaucoup de vendeurs n'ouvrent pas leurs e-mails : sans SMS, "
                        "ils ne sauront pas qu'une commande payée les attend.")
        elif fournisseur == "log":
            self.alerte("Aucune passerelle SMS : les messages urgents ne partent pas.",
                        "En attendant, relancez les vendeurs depuis "
                        "Administration → bouton « Relancer » (WhatsApp). "
                        "Pour automatiser : SMS_PROVIDER=http ou orange dans le .env")
        elif fournisseur == "http" and not conf["HTTP"]["URL"]:
            self.erreur("SMS_PROVIDER=http mais SMS_HTTP_URL est vide.",
                        "Renseigner l'adresse de la passerelle dans le .env")
        elif fournisseur == "orange" and not conf["ORANGE"]["CLIENT_ID"]:
            self.erreur("SMS_PROVIDER=orange mais les identifiants Orange manquent.",
                        "Renseigner ORANGE_SMS_CLIENT_ID et ORANGE_SMS_CLIENT_SECRET")
        else:
            self.ok(f"SMS envoyés via « {fournisseur} »")

        self._videos()

        from orders.services import commandes_sans_livraison

        from payments.models import Transaction

        a_valider = Transaction.objects.filter(
            status=Transaction.Status.AWAITING_REVIEW
        ).count()
        if a_valider:
            self.erreur(
                f"{a_valider} paiement(s) déclaré(s) attendent votre validation. "
                "Ces clients ont payé et ne voient rien avancer.",
                "Administration → Paiements à valider, ou "
                "/paiement/admin/transactions/",
            )
        else:
            self.ok("Aucun paiement en attente de validation")

        litiges = Order.objects.filter(non_recu_signale=True).exclude(
            status__in=[Order.Status.CANCELLED, Order.Status.REFUNDED]
        ).count()
        if litiges:
            self.erreur(
                f"{litiges} client(s) déclarent ne pas avoir reçu leur commande. "
                "Le paiement des vendeurs concernés est bloqué en attendant votre arbitrage.",
                "Administration → Commandes, filtrer sur « Non-réception signalée »",
            )
        else:
            self.ok("Aucun litige de livraison en cours")

        jamais_livrees = commandes_sans_livraison().count()
        if jamais_livrees:
            self.alerte(
                f"{jamais_livrees} commande(s) confirmées mais jamais marquées livrées "
                f"depuis plus de {settings.EAZYMARKET['DELIVERY_ALERT_DAYS']} jours.",
                "Souvent le vendeur a livré sans cliquer. Relancez-le : tant que "
                "la livraison n'est pas enregistrée, il ne sera jamais payé.",
            )

        en_retard = SellerConfirmation.objects.filter(
            status=SellerConfirmation.Status.PENDING, deadline__lt=timezone.now()
        ).count()
        if en_retard:
            self.erreur(
                f"{en_retard} commande(s) dépassent le délai sans avoir été traitées : "
                "l'argent de ces clients est bloqué.",
                "La tâche cron « traiter_commandes » ne tourne pas. "
                "cPanel → Tâches Cron → toutes les heures (0 * * * *)",
            )
        else:
            self.ok("Aucune commande en retard de traitement")

    # ------------------------------------------------------------------
    def _videos(self):
        """Espace occupé par les vidéos : c'est ce qui remplit un mutualisé."""
        from videos.models import Video

        conf = settings.EAZYMARKET
        hebergees = Video.objects.hebergees()
        nombre = hebergees.count()
        octets = sum(v.size for v in hebergees.only("size"))
        mo = octets / (1024 * 1024)

        liens = Video.objects.filter(file="").count()
        detail = f"{nombre} vidéo(s) hébergée(s), {mo:.0f} Mo"
        if liens:
            detail += f" — plus {liens} lien(s) externe(s), qui ne coûtent rien"

        if mo > 4000:
            self.alerte(
                f"{detail}. L'espace disque se remplit.",
                f"Baisser VIDEO_FREE_SLOTS (actuellement {conf['VIDEO_FREE_SLOTS']}) "
                "dans le .env : les vendeurs pourront toujours coller un lien TikTok.",
            )
        else:
            self.ok(detail)
