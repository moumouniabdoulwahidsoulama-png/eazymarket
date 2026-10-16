"""
Dépanne l'accès à l'administration.

    python manage.py admin_reset                       → liste les comptes administrateurs
    python manage.py admin_reset --user NOM            → redonne les droits admin à ce compte
    python manage.py admin_reset --user NOM --mdp XXXX → change aussi son mot de passe
    python manage.py admin_reset --creer NOM --mdp XXX → crée un administrateur

À utiliser quand vous n'arrivez plus à vous connecter à /django-admin/.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Liste, répare ou crée un compte administrateur."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Nom d'utilisateur existant à réparer")
        parser.add_argument("--creer", help="Nom d'utilisateur à créer")
        parser.add_argument("--mdp", help="Nouveau mot de passe")
        parser.add_argument("--email", default="", help="Adresse e-mail")

    def handle(self, *args, **options):
        if options["creer"]:
            name = options["creer"]
            password = options["mdp"]
            if not password:
                self.stderr.write("Indiquez un mot de passe avec --mdp")
                return
            user, created = User.objects.get_or_create(
                username=name, defaults={"email": options["email"]}
            )
            user.is_staff = user.is_superuser = user.is_active = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"{'Créé' if created else 'Mis à jour'} : {name} — connectez-vous sur /django-admin/"
            ))
            return

        if options["user"]:
            try:
                user = User.objects.get(username=options["user"])
            except User.DoesNotExist:
                self.stderr.write(f"Aucun compte nommé « {options['user']} ».")
                self._list()
                return
            user.is_staff = user.is_superuser = user.is_active = True
            if options["mdp"]:
                user.set_password(options["mdp"])
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f"{user.username} : droits administrateur rétablis"
                + (" et mot de passe changé." if options["mdp"] else ".")
            ))
            return

        self._list()

    def _list(self):
        admins = User.objects.filter(is_staff=True)
        if not admins:
            self.stdout.write(self.style.WARNING(
                "Aucun compte administrateur. Créez-en un :\n"
                "  python manage.py admin_reset --creer votre_nom --mdp VotreMotDePasse"
            ))
            return
        self.stdout.write("Comptes administrateurs :")
        for user in admins:
            state = []
            if not user.is_active:
                state.append("DÉSACTIVÉ")
            if not user.is_superuser:
                state.append("pas superutilisateur")
            if not user.last_login:
                state.append("jamais connecté")
            suffix = f"  ({', '.join(state)})" if state else ""
            self.stdout.write(f"  - {user.username}{suffix}")
        self.stdout.write(
            "\nAdresse de connexion : http://127.0.0.1:8000/django-admin/"
            "\n(/admin/ y renvoie automatiquement)"
            "\nMot de passe oublié :"
            "\n  python manage.py admin_reset --user NOM --mdp NouveauMotDePasse"
        )
