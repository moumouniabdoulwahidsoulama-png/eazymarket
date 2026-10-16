"""
Toutes les étapes serveur en une seule commande.

    python deploiement/mise_en_ligne.py

À lancer depuis le dossier de l'application, avec l'environnement virtuel
activé — ou à coller dans cPanel → Setup Python App → « Execute python script ».

Enchaîne : migrations → catalogue → fichiers statiques → vérification.
Sans risque : rien n'écrase de données existantes, la commande peut être
relancée autant de fois que nécessaire.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "EazyMarket.settings")

# Contrôle AVANT tout : sans .env, les migrations partiraient sur une base
# SQLite neuve au lieu de la vraie base MySQL. On s'arrête là.
if not (BASE_DIR / ".env").exists():
    print()
    print("=" * 62)
    print("  ARRÊT : aucun fichier .env dans", BASE_DIR)
    print("=" * 62)
    print()
    print("  Sans ce fichier, l'application ne connaît pas votre base de")
    print("  données : elle en créerait une vide, et votre site paraîtrait")
    print("  avoir tout perdu. Rien n'a été modifié.")
    print()
    print("  Vos données sont intactes — c'est seulement le fichier de")
    print("  configuration qui manque. Deux façons de le remettre :")
    print()
    print("    1. Vous avez une copie du .env → reposez-la ici.")
    print("    2. Vous ne l'avez plus         → python deploiement/configurer.py")
    print()
    print("  Dans les deux cas, indiquez EXACTEMENT la même base de données")
    print("  qu'avant (cPanel → Bases de données MySQL pour retrouver le nom).")
    print()
    sys.exit(1)

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402

from django.conf import settings  # noqa: E402


def _encodage_mysql():
    """Sur MySQL, la base doit accepter les emoji avant d'insérer les drapeaux."""
    if "mysql" in settings.DATABASES["default"]["ENGINE"]:
        call_command("reparer_utf8mb4")
    else:
        print("        base non-MySQL : rien à faire.")


def _protection_des_dossiers():
    """Repose le .htaccess dans static/ et media/.

    Utile à chaque mise à jour : ce fichier évolue (types vidéo, cache) et
    il vit sur le serveur, en dehors du dépôt, donc il ne se met pas à jour
    tout seul quand on téléverse une nouvelle version.
    """
    modele = BASE_DIR / "deploiement" / "htaccess-pour-static-et-media.txt"
    if not modele.exists():
        print("        modèle introuvable : ignoré.")
        return

    contenu = modele.read_text(encoding="utf-8")
    poses = 0
    for chemin in (settings.STATIC_ROOT, settings.MEDIA_ROOT):
        dossier = Path(chemin)
        if not dossier.exists():
            continue
        (dossier / ".htaccess").write_text(contenu, encoding="utf-8")
        poses += 1
    print(f"        {poses} dossier(s) protégé(s).")


ETAPES = [
    ("Application des migrations", lambda: call_command("migrate", interactive=False)),
    ("Encodage de la base (emoji, accents)", _encodage_mysql),
    ("Pays, rayons et métiers", lambda: call_command("init_catalogue")),
    ("Rassemblement des fichiers statiques",
     lambda: call_command("collectstatic", interactive=False, clear=True, verbosity=0)),
    ("Protection des dossiers static/ et media/", _protection_des_dossiers),
]


def _expliquer(exc):
    """Traduit les échecs les plus fréquents en langage clair."""
    texte = str(exc)
    conf = settings.DATABASES["default"]

    if "1045" in texte or "Access denied" in texte:
        sauvegarde = BASE_DIR / ".env.sauvegarde"
        print()
        print("  Ce que ça veut dire : le nom d'utilisateur ou le mot de passe")
        print("  de la base est faux. Ce n'est PAS une perte de données —")
        print("  la base est là, l'application n'a pas le droit de l'ouvrir.")
        print()
        print(f"  Actuellement, le .env dit :  base « {conf.get('NAME')} », "
              f"utilisateur « {conf.get('USER')} »")
        print()
        if sauvegarde.exists():
            print("  Vos identifiants qui fonctionnaient sont dans la sauvegarde :")
            print()
            print(f"      grep '^DB_' {sauvegarde}")
            print()
            print("  Recopiez ces trois lignes (DB_NAME, DB_USER, DB_PASSWORD)")
            print("  dans le .env, puis relancez cette commande.")
        else:
            print("  Retrouvez-les dans cPanel → Bases de données MySQL.")
            print("  Le nom ET l'utilisateur commencent par votre préfixe cPanel.")
            print("  Si vous avez oublié le mot de passe, changez-le depuis")
            print("  cPanel (« Modifier le mot de passe » de l'utilisateur).")
    elif "1049" in texte or "Unknown database" in texte:
        print()
        print(f"  La base « {conf.get('NAME')} » n'existe pas sur ce serveur.")
        print("  Vérifiez son nom exact dans cPanel → Bases de données MySQL.")
    elif "2003" in texte or "Can't connect" in texte:
        print()
        print(f"  Le serveur de base « {conf.get('HOST')} » ne répond pas.")
        print("  Sur cPanel, DB_HOST doit presque toujours valoir localhost.")


def main():
    print()
    print("Mise en ligne d'EazyMarket")
    print("=" * 62)
    for numero, (titre, action) in enumerate(ETAPES, start=1):
        print(f"\n[{numero}/{len(ETAPES)}] {titre}…")
        try:
            action()
            print("        terminé.")
        except Exception as exc:  # noqa: BLE001
            print(f"        ÉCHEC : {exc}")
            _expliquer(exc)
            print("\nCorrigez cette erreur avant de continuer.")
            sys.exit(1)

    print("\n" + "=" * 62)
    call_command("verifier_production")
    print("S'il manque un compte administrateur :")
    print("    python manage.py createsuperuser")
    print("Puis redémarrez l'application dans cPanel (bouton RESTART).")
    print()


if __name__ == "__main__":
    main()
