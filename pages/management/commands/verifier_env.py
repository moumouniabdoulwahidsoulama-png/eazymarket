"""Dit exactement ce que l'application a lu dans le fichier .env.

    python manage.py verifier_env

Aucun mot de passe n'est affiché : uniquement les noms des réglages, et
pour chacun s'il vient de votre fichier ou d'une valeur par défaut. C'est
l'outil à lancer quand le site « perd » sa base de données ou repart vide.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# Les réglages sans lesquels le site ne tourne pas correctement en ligne.
INDISPENSABLES = [
    ("DJANGO_SECRET_KEY", "Clé de sécurité propre à votre installation"),
    ("DJANGO_DEBUG", "Doit valoir False en ligne"),
    ("DJANGO_ALLOWED_HOSTS", "Votre nom de domaine, sinon « Bad Request »"),
    ("DB_ENGINE", "mysql — sinon l'application repart sur une base vide"),
    ("DB_NAME", "Nom de votre base MySQL"),
    ("DB_USER", "Utilisateur de la base"),
    ("DB_PASSWORD", "Mot de passe de la base"),
    ("PUBLIC_BASE_URL", "Adresse publique, utilisée dans les liens envoyés"),
    ("DJANGO_STATIC_ROOT", "Dossier public des fichiers statiques"),
    ("DJANGO_MEDIA_ROOT", "Dossier public des photos et vidéos"),
]

UTILES = [
    ("DJANGO_CSRF_TRUSTED_ORIGINS", "https://votre-domaine — sinon les formulaires refusent"),
    ("EMAIL_HOST", "Serveur d'envoi des e-mails"),
    ("EMAIL_HOST_USER", "Boîte d'envoi"),
    ("ORANGE_MONEY_NUMBER_1", "Numéro d'encaissement principal"),
    ("SMS_PROVIDER", "Passerelle SMS (log, http ou orange)"),
]


class Command(BaseCommand):
    help = "Affiche ce que l'application a lu dans le fichier .env (sans les mots de passe)."

    def _ligne(self, etat, cle, commentaire=""):
        couleurs = {
            "ok": self.style.SUCCESS, "manque": self.style.ERROR,
            "defaut": self.style.WARNING,
        }
        etiquettes = {"ok": "[lu]     ", "manque": "[MANQUE] ", "defaut": "[défaut] "}
        texte = f"  {etiquettes[etat]}{cle}"
        if commentaire:
            texte += f"\n            → {commentaire}"
        self.stdout.write(couleurs[etat](texte))

    def handle(self, *args, **options):
        chemin = Path(settings.BASE_DIR) / ".env"
        lues = set(getattr(settings, "DOTENV_LUES", []))

        self.stdout.write(self.style.HTTP_INFO("\nCe que l'application a lu dans le .env"))
        self.stdout.write("=" * 62)
        self.stdout.write(f"\nFichier attendu : {chemin}")

        if not getattr(settings, "DOTENV_TROUVE", False):
            self.stdout.write(self.style.ERROR(
                "\nCE FICHIER N'EXISTE PAS.\n"
                "L'application tourne entièrement sur ses valeurs par défaut :\n"
                "base SQLite vide, DEBUG activé. Reposez votre .env ici, "
                "ou relancez :\n    python deploiement/configurer.py\n"
            ))
            return

        taille = chemin.stat().st_size
        self.stdout.write(f"Trouvé, {taille} octets, {len(lues)} réglage(s) lu(s).\n")

        self.stdout.write(self.style.HTTP_INFO("\nRéglages indispensables"))
        manquants = []
        for cle, role in INDISPENSABLES:
            if cle in lues:
                self._ligne("ok", cle)
            else:
                manquants.append(cle)
                self._ligne("manque", cle, role)

        self.stdout.write(self.style.HTTP_INFO("\nRéglages utiles"))
        for cle, role in UTILES:
            self._ligne("ok" if cle in lues else "defaut", cle, "" if cle in lues else role)

        ignorees = getattr(settings, "DOTENV_IGNOREES", [])
        if ignorees:
            self.stdout.write(self.style.HTTP_INFO("\nLignes que le lecteur n'a pas comprises"))
            self.stdout.write(self.style.ERROR(
                "  Ces lignes sont dans le fichier mais n'ont PAS été appliquées :"))
            for numero, extrait, raison in ignorees:
                self.stdout.write(self.style.ERROR(f"    ligne {numero} : {extrait}"))
                self.stdout.write(f"                {raison}")

        doublons = getattr(settings, "DOTENV_DOUBLONS", [])
        if doublons:
            self.stdout.write(self.style.HTTP_INFO("\nRéglages écrits deux fois"))
            self.stdout.write(self.style.WARNING(
                "  C'est la PREMIÈRE occurrence qui compte, les suivantes sont ignorées :"))
            for numero, cle in doublons:
                self.stdout.write(self.style.WARNING(f"    ligne {numero} : {cle}"))

        self.stdout.write("\n" + "=" * 62)
        self.stdout.write(self.style.HTTP_INFO("Ce que l'application utilise vraiment"))
        moteur = settings.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1]
        base = settings.DATABASES["default"].get("NAME", "")
        self.stdout.write(f"  Base de données  : {moteur} ({base})")
        self.stdout.write(f"  DEBUG            : {settings.DEBUG}")
        self.stdout.write(f"  Domaines         : {', '.join(settings.ALLOWED_HOSTS) or '(aucun)'}")
        self.stdout.write(f"  Fichiers publics : {settings.STATIC_ROOT}")
        self.stdout.write(f"  Photos et vidéos : {settings.MEDIA_ROOT}")

        # Cas très fréquent : on a envoyé sur le serveur le .env de son
        # ordinateur. Les trois indices se voient d'un coup d'œil.
        indices = []
        if settings.DEBUG:
            indices.append("DJANGO_DEBUG=True")
        if moteur == "sqlite3":
            indices.append("pas de base MySQL")
        if "127.0.0.1" in settings.PAYMENTS.get("PUBLIC_BASE_URL", ""):
            indices.append("PUBLIC_BASE_URL pointe sur 127.0.0.1")

        self.stdout.write("")
        if len(indices) >= 2:
            self.stdout.write(self.style.ERROR(
                "CE .env EST CELUI D'UN ORDINATEUR DE DÉVELOPPEMENT, pas du serveur.\n"
                "  Indices : " + ", ".join(indices) + "\n\n"
                "  C'est l'erreur la plus courante : en cherchant le .env manquant,\n"
                "  on retrouve celui de son PC et on l'envoie. Le site redémarre,\n"
                "  mais sur une base vide.\n\n"
                "  Vos données sont intactes dans MySQL. Pour écrire le bon fichier :\n\n"
                "      python deploiement/configurer.py\n\n"
                "  Répondez « oui » à la question « L'écraser ? », puis indiquez\n"
                "  EXACTEMENT la même base MySQL qu'avant (cPanel → Bases de\n"
                "  données MySQL). Ensuite :\n\n"
                "      rm -f db.sqlite3\n"
                "      python deploiement/mise_en_ligne.py\n\n"
                "  et RESTART dans cPanel.\n"
            ))
        elif moteur == "sqlite3":
            self.stdout.write(self.style.ERROR(
                "ATTENTION : l'application utilise une base SQLite, pas votre base MySQL.\n"
                "Vos données ne sont pas perdues — elles sont dans MySQL, l'application\n"
                "ne les ouvre simplement pas. Ajoutez au .env le bloc de la base :\n\n"
                "    DB_ENGINE=mysql\n"
                "    DB_NAME=votre_base\n"
                "    DB_USER=votre_utilisateur\n"
                "    DB_PASSWORD=votre_mot_de_passe\n"
                "    DB_HOST=localhost\n"
                "    DB_PORT=3306\n\n"
                "Puis : rm -f db.sqlite3 && python deploiement/mise_en_ligne.py\n"
                "et RESTART dans cPanel.\n"
            ))
        elif manquants:
            self.stdout.write(self.style.WARNING(
                f"{len(manquants)} réglage(s) indispensable(s) manquent : "
                + ", ".join(manquants) + "\n"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("Rien ne manque.\n"))
