"""
Fabrique le fichier ZIP à envoyer sur l'hébergement.

    python deploiement/faire_le_paquet.py

Le ZIP contient le code et rien d'autre : ni votre base locale, ni vos
mots de passe (.env), ni les photos de test, ni l'environnement virtuel.
"""

import datetime
import fnmatch
import os
import sys
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Dossiers jamais envoyés
DOSSIERS_EXCLUS = {
    "venv", ".venv", "env", "__pycache__", ".git", ".idea", ".vscode",
    "_legacy", "logs", "media", "staticfiles", "node_modules", "paquets",
}

# Dossiers qui n'ont rien à faire dans le projet : ils apparaissent quand on
# extrait une archive sans écraser (Windows crée un sous-dossier au nom du
# ZIP), ou quand un outil dépose ses fichiers à côté. Les embarquer gonfle le
# paquet et, surtout, laisse croire qu'une mise à jour a été appliquée alors
# qu'elle dort dans un coin.
MOTIFS_INTRUS = ["mise-a-jour*", "maj*", "* outputs", "*copie*", "*Copy*", "nouveau*"]


def est_un_intrus(nom: str) -> bool:
    return any(fnmatch.fnmatch(nom, motif) for motif in MOTIFS_INTRUS)

# Fichiers jamais envoyés
FICHIERS_EXCLUS = [
    ".env",                 # vos mots de passe : se recrée sur le serveur
    "db.sqlite3",           # votre base locale
    "db.sqlite3-journal",
    "*.pyc", "*.pyo", "*.log", "*.bak", "*.zip", "*.tgz", "*.tar.gz",
    "apercu_*.html",        # aperçus de travail
    "*.sqlite3",
]


def exclu(chemin: Path) -> bool:
    if any(part in DOSSIERS_EXCLUS for part in chemin.parts):
        return True
    return any(fnmatch.fnmatch(chemin.name, motif) for motif in FICHIERS_EXCLUS)


def main():
    sortie_dir = BASE_DIR / "paquets"
    sortie_dir.mkdir(exist_ok=True)
    horodatage = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    archive = sortie_dir / f"eazymarket-{horodatage}.zip"

    intrus = []
    fichiers = []
    for racine, dossiers, noms in os.walk(BASE_DIR):
        racine_path = Path(racine)
        if racine_path == BASE_DIR:
            for d in list(dossiers):
                if d not in DOSSIERS_EXCLUS and est_un_intrus(d):
                    intrus.append(d)
                    dossiers.remove(d)
        dossiers[:] = [d for d in dossiers if d not in DOSSIERS_EXCLUS]
        for nom in noms:
            chemin = racine_path / nom
            relatif = chemin.relative_to(BASE_DIR)
            if not exclu(relatif):
                fichiers.append((chemin, relatif))

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for chemin, relatif in fichiers:
            zf.write(chemin, relatif.as_posix())

    taille = archive.stat().st_size / 1024
    print()
    print("  Paquet prêt à être envoyé")
    print("  " + "-" * 52)
    print(f"  Fichier  : {archive}")
    print(f"  Contenu  : {len(fichiers)} fichiers, {taille:.0f} Ko")
    print()
    print("  Ce paquet NE contient PAS : votre base locale, votre fichier .env,")
    print("  vos photos de test, ni l'environnement virtuel. C'est voulu.")
    print()

    # On montre ce qui est parti : un dossier qui manque se repère d'un coup d'œil.
    dossiers_inclus = sorted({r.parts[0] for _, r in fichiers if len(r.parts) > 1})
    print("  Dossiers inclus :", ", ".join(dossiers_inclus))
    print()

    if intrus:
        print("  ATTENTION — dossiers ignorés, car ils ressemblent à une archive")
        print("  extraite au mauvais endroit :")
        for nom in intrus:
            print(f"      {nom}")
        print()
        print("  Si c'est une mise à jour, elle N'EST PAS appliquée : ses fichiers")
        print("  doivent être copiés PAR-DESSUS le projet, pas laissés à côté.")
        print("  Le plus simple : double-cliquez sur appliquer-la-mise-a-jour.bat")
        print()
    print("  Suite : cPanel → Gestionnaire de fichiers → dossier de l'application")
    print("          → Téléverser → Extraire → puis suivre GUIDE_DEPLOIEMENT_LWS.md")
    print()

    # Garde-fou : on refuse d'envoyer un secret par erreur
    noms = {r.as_posix() for _, r in fichiers}
    fuites = [n for n in noms if n == ".env" or n.endswith("/.env") or n.endswith(".sqlite3")]
    if fuites:
        print("  ATTENTION : des fichiers sensibles sont dans le paquet :", fuites)
        sys.exit(1)


if __name__ == "__main__":
    main()
