"""
Écrit le fichier .env de production, sans laisser la moindre valeur d'exemple.

    python deploiement/configurer.py

Le script détecte tout seul votre compte, vos chemins et le dossier public de
votre sous-domaine, génère la clé secrète, puis vous pose les cinq questions
auxquelles lui seul ne peut pas répondre. Il crée aussi les dossiers
static/ et media/ avec leur .htaccess de protection.

N'utilise que la bibliothèque standard : il fonctionne même quand Django
refuse de démarrer.
"""

import os
import re
import secrets
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
EXEMPLE = BASE_DIR / "deploiement" / ".env.production.example"
CIBLE = BASE_DIR / ".env"
HTACCESS = BASE_DIR / "deploiement" / "htaccess-pour-static-et-media.txt"

# Dossiers du compte cPanel qui ne sont jamais une racine de site
IGNORER = {
    "public_ftp", "mail", "etc", "logs", "ssl", "tmp", "virtualenv", "cache",
    "access-logs", "cpanel", "cpeasyapache", "perl5", "ssh", "backups",
    ".cagefs", ".cpanel", ".cphorde", ".htpasswds", ".trash", "nodevenv",
}


def demander(question, defaut="", obligatoire=True):
    invite = f"{question}"
    if defaut:
        invite += f"\n  [Entrée = {defaut}]"
    invite += "\n  > "
    while True:
        reponse = input(invite).strip()
        if not reponse and defaut:
            return defaut
        if reponse or not obligatoire:
            return reponse
        print("  Cette réponse est nécessaire.")


def choisir(question, options, autre="Autre — je saisis le chemin"):
    print(f"\n{question}")
    for i, option in enumerate(options, start=1):
        print(f"  {i}) {option}")
    print(f"  {len(options) + 1}) {autre}")
    while True:
        choix = input("  > ").strip()
        if choix.isdigit():
            n = int(choix)
            if 1 <= n <= len(options):
                return options[n - 1]
            if n == len(options) + 1:
                return None
        print("  Tapez le numéro de votre choix.")


def racines_possibles(home: Path, hote: str):
    """Cherche le dossier public du sous-domaine parmi les dossiers du compte."""
    trouves = []
    exact = home / hote
    if exact.is_dir():
        trouves.append(exact)

    for chemin in sorted(home.iterdir()):
        if not chemin.is_dir() or chemin.name in IGNORER or chemin == exact:
            continue
        if chemin.name.startswith("."):
            continue
        if "." in chemin.name:  # ressemble à un nom de domaine
            trouves.append(chemin)

    public_html = home / "public_html"
    if public_html.is_dir():
        if public_html not in trouves:
            trouves.append(public_html)
        for chemin in sorted(public_html.iterdir()):
            if chemin.is_dir() and not chemin.name.startswith("."):
                trouves.append(chemin)
    return trouves


def main():
    if not EXEMPLE.exists():
        print(f"Fichier modèle introuvable : {EXEMPLE}")
        sys.exit(1)

    home = Path.home()
    utilisateur = home.name

    print()
    print("Configuration de production d'EazyMarket")
    print("=" * 62)
    print(f"  Compte détecté     : {utilisateur}")
    print(f"  Dossier personnel  : {home}")
    print(f"  Application        : {BASE_DIR}")

    if CIBLE.exists():
        print()
        print(f"  Un fichier .env existe déjà ({CIBLE}).")
        if demander("  L'écraser ? (oui/non)", "non").lower() not in ("oui", "o", "yes", "y"):
            print("  Rien n'a été modifié.")
            sys.exit(0)
        # Attention : Path(".env").with_suffix(...) produit « .env.env... »
        # parce qu'un nom commençant par un point n'a pas d'extension.
        # On construit donc le nom à la main, sinon le message affiché ne
        # correspond pas au fichier réellement écrit.
        sauvegarde = CIBLE.with_name(CIBLE.name + ".sauvegarde")
        shutil.copy(CIBLE, sauvegarde)
        print(f"  Ancienne version conservée : {sauvegarde}")
        print("  (elle contient vos identifiants de base actuels : gardez-la)")

    # ---------- 1. L'adresse du site ----------
    print()
    print("-" * 62)
    hote = demander(
        "1/5 — Adresse complète du site, sans https://\n"
        "      (exemple : boutique.mondomaine.com)"
    ).lower().strip()
    for prefixe in ("https://", "http://"):
        if hote.startswith(prefixe):
            hote = hote[len(prefixe):]
    hote = hote.strip("/").split("/")[0]

    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", hote):
        print(f"  « {hote} » ne ressemble pas à une adresse valide.")
        sys.exit(1)

    # ---------- 2. Le dossier public ----------
    print()
    print("-" * 62)
    print("2/5 — Dossier public du sous-domaine")
    print("      (la « racine du document » affichée par cPanel)")
    candidats = racines_possibles(home, hote)
    docroot = None
    if candidats:
        choix = choisir("      Dossiers trouvés sur le compte :",
                        [str(c) for c in candidats])
        docroot = Path(choix) if choix else None
    if docroot is None:
        docroot = Path(demander("      Chemin complet du dossier public",
                                str(home / hote)))
    if not docroot.is_dir():
        print(f"\n  Le dossier {docroot} n'existe pas.")
        if demander("  Le créer ? (oui/non)", "oui").lower() in ("oui", "o", "yes", "y"):
            docroot.mkdir(parents=True, exist_ok=True)
        else:
            sys.exit(1)

    # ---------- 3. La base de données ----------
    print()
    print("-" * 62)
    print("3/5 — Base de données MySQL")
    print(f"      Rappel : cPanel préfixe les noms par « {utilisateur}_ »")
    db_name = demander("      Nom complet de la base", f"{utilisateur}_eazymarket")
    db_user = demander("      Utilisateur de la base", f"{utilisateur}_eazyuser")
    db_pass = demander("      Mot de passe de la base")

    # ---------- 4. Le HTTPS ----------
    print()
    print("-" * 62)
    ssl = demander(
        "4/5 — Le certificat HTTPS est-il déjà actif sur ce sous-domaine ?\n"
        "      (répondez non si vous n'avez pas encore lancé AutoSSL) (oui/non)",
        "non",
    ).lower() in ("oui", "o", "yes", "y")

    # ---------- 5. L'e-mail ----------
    print()
    print("-" * 62)
    domaine_base = ".".join(hote.split(".")[-2:])
    email_user = email_pass = ""
    veut_email = demander(
        "5/5 — Configurer l'envoi d'e-mails maintenant ?\n"
        "      (adresse créée dans cPanel → Comptes de messagerie) (oui/non)",
        "non",
    ).lower() in ("oui", "o", "yes", "y")
    if veut_email:
        email_user = demander("      Adresse d'envoi", f"no-reply@{domaine_base}")
        email_pass = demander("      Mot de passe de cette adresse")

    # ---------- Écriture ----------
    contenu = EXEMPLE.read_text(encoding="utf-8")
    remplacements = {
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
        "DJANGO_DEBUG": "False",
        "DJANGO_ALLOWED_HOSTS": f"{hote},www.{hote}",
        "DJANGO_CSRF_TRUSTED_ORIGINS": f"https://{hote},https://www.{hote}",
        "SECURE_SSL_REDIRECT": "True" if ssl else "False",
        "DJANGO_STATIC_ROOT": str(docroot / "static"),
        "DJANGO_MEDIA_ROOT": str(docroot / "media"),
        "DJANGO_LOG_DIR": str(BASE_DIR / "logs"),
        "DJANGO_SERVE_MEDIA": "True",
        "DB_ENGINE": "mysql",
        "DB_NAME": db_name,
        "DB_USER": db_user,
        "DB_PASSWORD": db_pass,
        "DB_HOST": "localhost",
        "DB_PORT": "3306",
        "PUBLIC_BASE_URL": f"{'https' if ssl else 'http'}://{hote}",
        "CONTACT_EMAIL": email_user or f"contact@{domaine_base}",
    }
    if email_user:
        remplacements.update({
            "EMAIL_HOST": f"mail.{domaine_base}",
            "EMAIL_HOST_USER": email_user,
            "EMAIL_HOST_PASSWORD": email_pass,
            "DEFAULT_FROM_EMAIL": f"EazyMarket <{email_user}>",
        })
    else:
        # Rien ne doit rester à l'état d'exemple : l'application refuserait de démarrer
        remplacements.update({
            "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
            "EMAIL_HOST": "",
            "EMAIL_HOST_USER": "",
            "EMAIL_HOST_PASSWORD": "",
            "DEFAULT_FROM_EMAIL": f"EazyMarket <no-reply@{domaine_base}>",
        })

    lignes = []
    for ligne in contenu.splitlines():
        nu = ligne.strip()
        if nu and not nu.startswith("#") and "=" in nu:
            cle = nu.split("=", 1)[0].strip()
            if cle in remplacements:
                commentaire = ""
                if "  #" in ligne:
                    commentaire = "  #" + ligne.split("  #", 1)[1]
                lignes.append(f"{cle}={remplacements[cle]}{commentaire}")
                continue
        lignes.append(ligne)
    resultat = "\n".join(lignes) + "\n"

    restants = [l for l in resultat.splitlines()
                if any(m in l for m in ("A_REMPLIR", "VOTRE-DOMAINE", "/home/UTILISATEUR"))
                and not l.strip().startswith("#")]
    if restants:
        print("\n  Des valeurs d'exemple subsistent, corrigez-les à la main :")
        for l in restants:
            print("   ", l)

    CIBLE.write_text(resultat, encoding="utf-8")
    os.chmod(CIBLE, 0o600)

    # ---------- Dossiers publics + protection ----------
    protection = HTACCESS.read_text(encoding="utf-8") if HTACCESS.exists() else ""
    for nom in ("static", "media"):
        dossier = docroot / nom
        dossier.mkdir(parents=True, exist_ok=True)
        os.chmod(dossier, 0o755)
        if protection:
            (dossier / ".htaccess").write_text(protection, encoding="utf-8")
    (BASE_DIR / "logs").mkdir(exist_ok=True)

    print()
    print("=" * 62)
    print("  Fichier .env écrit :", CIBLE)
    print("  Lisible par vous seul (permissions 600).")
    print()
    print("  Adresse du site   :", remplacements["PUBLIC_BASE_URL"])
    print("  Fichiers statiques:", remplacements["DJANGO_STATIC_ROOT"])
    print("  Photos            :", remplacements["DJANGO_MEDIA_ROOT"])
    print("  Base de données   :", db_name)
    print("  Protection .htaccess posée dans les deux dossiers.")
    if not ssl:
        print()
        print("  HTTPS pas encore actif : après AutoSSL, repassez")
        print("  SECURE_SSL_REDIRECT=True et PUBLIC_BASE_URL en https:// dans le .env.")
    print()
    print("  Étape suivante :")
    print("      python deploiement/mise_en_ligne.py")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Interrompu. Le fichier .env n'a pas été modifié.")
        sys.exit(1)
