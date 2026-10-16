"""
Configuration Django — EazyMarket
Marketplace produits + services (Burkina Faso).

Tout ce qui est sensible ou dépend de l'environnement se lit dans un
fichier .env à la racine du projet (voir .env.example). Aucune clé ne
doit être écrite en dur dans ce fichier.
"""

import os
import re
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------
# Petit lecteur de .env (évite une dépendance externe)
# ---------------------------------------------------------------------
# Ce que le lecteur a rencontré. Sert au diagnostic (manage.py verifier_env) :
# une ligne mal écrite dans le .env est invisible autrement, et c'est ce qui
# fait repartir une application sur une base vide sans que personne comprenne.
DOTENV_LUES = []      # clés effectivement chargées
DOTENV_IGNOREES = []  # lignes que le lecteur n'a pas su interpréter
DOTENV_DOUBLONS = []  # clés présentes plusieurs fois (la première gagne)

_CLE_VALIDE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_dotenv(path):
    """Charge le .env. Renvoie True s'il a été trouvé et lu.

    Tolérant sur la forme (BOM Windows, « export », guillemets, espaces
    autour du =) mais il note tout ce qu'il n'a pas compris, au lieu de
    l'ignorer en silence.
    """
    if not path.exists():
        return False

    # utf-8-sig : Bloc-notes de Windows ajoute une marque invisible en tête
    # de fichier, qui collerait à la première clé et la rendrait introuvable.
    try:
        contenu = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        contenu = path.read_text(encoding="latin-1")

    for numero, raw in enumerate(contenu.splitlines(), start=1):
        line = raw.strip().lstrip("\ufeff")
        if not line or line.startswith(("#", ";")):
            continue
        if "=" not in line:
            DOTENV_IGNOREES.append((numero, line[:60], "pas de signe ="))
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        # « export CLE=valeur » : forme courante quand on recopie depuis un script
        if key.lower().startswith("export "):
            key = key[7:].strip()
        # Décorations Markdown collées en recopiant depuis une discussion
        key = key.strip("*`\u00a0 ")

        if not _CLE_VALIDE.match(key):
            DOTENV_IGNOREES.append((numero, line[:60], f"nom de clé invalide : {key!r}"))
            continue

        value = value.strip()
        # Commentaire de fin de ligne : on coupe sur " #" (un # collé à la
        # valeur est conservé — le code USSD se termine par #)
        cut = re.split(r"\s+#", value, maxsplit=1)[0]
        cut = cut.strip().strip("'\"").replace("\u00a0", " ").strip()

        if key in DOTENV_LUES:
            DOTENV_DOUBLONS.append((numero, key))
            continue
        DOTENV_LUES.append(key)
        os.environ.setdefault(key, cut)
    return True


DOTENV_TROUVE = _load_dotenv(BASE_DIR / ".env")

# Sur le serveur, l'absence de .env doit tout arrêter.
#
# Sans ce garde-fou, Django repart sur ses valeurs par défaut : base SQLite
# vide, DEBUG activé, clé secrète de développement — le site tourne, mais sur
# une base neuve, et la moindre erreur affiche la configuration aux visiteurs.
# C'est une panne silencieuse, la pire espèce. Mieux vaut refuser de démarrer.
if not DOTENV_TROUVE and os.environ.get("EAZYMARKET_SERVEUR"):
    raise ImproperlyConfigured(
        f"\n\nAucun fichier .env trouvé dans {BASE_DIR}.\n\n"
        "L'application refuse de démarrer : sans ce fichier elle utiliserait\n"
        "une base SQLite vide au lieu de votre base MySQL, et vos données\n"
        "sembleraient avoir disparu.\n\n"
        "Si vous venez de mettre le site à jour, le .env a probablement été\n"
        "effacé ou déposé au mauvais endroit. Deux façons de le remettre :\n\n"
        "  1. Vous en avez une copie  → reposez-la ici, puis RESTART.\n"
        "  2. Vous ne l'avez plus     → python deploiement/configurer.py\n\n"
        "Attention : indiquez EXACTEMENT la même base de données qu'avant,\n"
        "sinon le site repartira à vide.\n"
    )


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(env(key, str(default))).lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    return [v.strip() for v in env(key, default).split(",") if v.strip()]


# ---------------------------------------------------------------------
# Garde-fou : le fichier .env contient-il encore les valeurs d'exemple ?
# ---------------------------------------------------------------------
_A_REMPLACER = ("A_REMPLIR", "VOTRE-DOMAINE", "UTILISATEUR/", "/home/UTILISATEUR")


def _verifier_le_env():
    """Arrête tout de suite avec un message clair plutôt qu'une erreur illisible."""
    fautives = []
    for cle, valeur in os.environ.items():
        if not cle.startswith(("DJANGO_", "DB_", "SITE_", "EMAIL_", "ORANGE_", "MOOV_",
                               "WAVE_", "SUPPORT_", "CONTACT_", "PUBLIC_", "CINETPAY_")):
            continue
        if any(marqueur in str(valeur) for marqueur in _A_REMPLACER):
            fautives.append(f"    {cle}={valeur}")
    if fautives:
        raise ImproperlyConfigured(
            "\n\nLe fichier .env contient encore des valeurs d'exemple :\n\n"
            + "\n".join(sorted(fautives))
            + "\n\nRemplacez-les par vos vraies valeurs.\n"
            "Le plus simple : lancez  python deploiement/configurer.py\n"
            "Il détecte vos chemins, génère la clé secrète et écrit le .env pour vous.\n"
        )


_verifier_le_env()


# ---------------------------------------------------------------------
# Sécurité
# ---------------------------------------------------------------------
SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    "dev-only-key-change-me-in-production-0000000000000000000000",
)

DEBUG = env_bool("DJANGO_DEBUG", True)

# Les domaines sont souvent recopiés depuis une discussion ou un e-mail, où
# ils arrivent transformés en lien : [www.site.com](https://www.site.com).
# Tel quel, Django ne reconnaît plus le domaine et répond « Bad Request » —
# une panne difficile à relier à sa cause. On répare au chargement.
HOSTS_REPARES = []


def _nettoyer_hote(valeur):
    brut = valeur.strip()
    propre = brut
    lien = re.match(r"^\[([^\]]+)\]\([^)]*\)$", propre)
    if lien:
        propre = lien.group(1).strip()
    propre = re.sub(r"^https?://", "", propre, flags=re.I)
    propre = propre.split("/")[0].strip().strip(",").rstrip(".")
    if propre != brut:
        HOSTS_REPARES.append((brut, propre))
    return propre


def _nettoyer_origine(valeur):
    brut = valeur.strip()
    propre = brut
    lien = re.match(r"^\[([^\]]+)\]\(([^)]*)\)$", propre)
    if lien:
        propre = (lien.group(2) or lien.group(1)).strip()
    if propre and not re.match(r"^https?://", propre, flags=re.I):
        propre = "https://" + propre
    propre = propre.rstrip("/")
    if propre != brut:
        HOSTS_REPARES.append((brut, propre))
    return propre


ALLOWED_HOSTS = [
    h for h in (_nettoyer_hote(v) for v in
                env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")) if h
]
if DEBUG:
    # En développement on autorise aussi l'IP locale (test depuis un téléphone)
    ALLOWED_HOSTS += [".localhost", "0.0.0.0", "testserver"]
    try:
        import socket

        _host = socket.gethostname()
        ALLOWED_HOSTS += [_host, socket.gethostbyname(_host)]
    except Exception:  # pragma: no cover - dépend de la machine
        pass

CSRF_TRUSTED_ORIGINS = [
    o for o in (_nettoyer_origine(v) for v in env_list("DJANGO_CSRF_TRUSTED_ORIGINS")) if o
]


# Sur le serveur, un .env de développement doit aussi tout arrêter.
#
# L'erreur est facile à commettre : on cherche le .env qui manque, on trouve
# celui de son ordinateur et on l'envoie. Le site redémarre — mais sur une
# base SQLite vide, avec DEBUG activé et le mauvais nom de domaine. Il vaut
# mieux refuser de démarrer et le dire.
if os.environ.get("EAZYMARKET_SERVEUR"):
    _indices = []
    if DEBUG:
        _indices.append("DJANGO_DEBUG vaut True")
    if env("DB_ENGINE", "sqlite").lower() in ("sqlite", "sqlite3"):
        _indices.append("aucune base MySQL (DB_ENGINE absent ou sqlite)")
    if _indices:
        raise ImproperlyConfigured(
            "\n\nLe fichier .env chargé ressemble à celui de votre ordinateur,\n"
            "pas à celui du serveur :\n\n    - "
            + "\n    - ".join(_indices)
            + "\n\nL'application refuse de démarrer : elle utiliserait une base\n"
            "vide au lieu de votre base MySQL, et afficherait votre\n"
            "configuration aux visiteurs à la première erreur.\n\n"
            "Pour écrire le bon fichier :\n\n"
            "    python deploiement/configurer.py\n\n"
            "Il détecte vos chemins, génère la clé secrète et vous demande le\n"
            "nom de votre base MySQL. Indiquez EXACTEMENT la même qu'avant,\n"
            "sinon le site repartira à vide.\n\n"
            "Pour voir ce qui a été lu :  python manage.py verifier_env\n"
        )


# ---------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Applications métier
    "regions",
    "accounts",
    "products",
    "cart",
    "orders",
    "services",
    "payments",
    "delivery",
    "notifications",
    "videos",
    "pages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# WhiteNoise est optionnel : s'il n'est pas installé on le retire silencieusement
try:  # pragma: no cover
    import whitenoise  # noqa: F401
except ImportError:  # pragma: no cover
    MIDDLEWARE.remove("whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "EazyMarket.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "EazyMarket.context_processors.site_context",
            ],
        },
    },
]

WSGI_APPLICATION = "EazyMarket.wsgi.application"
ASGI_APPLICATION = "EazyMarket.asgi.application"


# ---------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------
DB_ENGINE = env("DB_ENGINE", "sqlite").lower()

if DB_ENGINE in ("mysql", "mariadb"):
    # Base native de cPanel. Le pilote PyMySQL (voir EazyMarket/__init__.py)
    # s'installe sans compilation, contrairement à mysqlclient.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env("DB_NAME", ""),
            "USER": env("DB_USER", ""),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "3306"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
elif DB_ENGINE in ("postgresql", "postgres"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", "eazymarket"),
            "USER": env("DB_USER", "eazymarket"),
            "PASSWORD": env("DB_PASSWORD", ""),
            "HOST": env("DB_HOST", "localhost"),
            "PORT": env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 jours
SESSION_SAVE_EVERY_REQUEST = True

# Le cookie CSRF n'a aucune raison d'être lu en JavaScript : on le ferme.
CSRF_COOKIE_HTTPONLY = True

# Anti-force-brute de la connexion (voir accounts/securite.py).
# Après LOGIN_MAX_ECHECS échecs en LOGIN_FENETRE_MINUTES minutes, l'IP est
# bloquée pendant LOGIN_BLOCAGE_MINUTES minutes.
LOGIN_MAX_ECHECS = int(env("LOGIN_MAX_ECHECS", "5"))
LOGIN_FENETRE_MINUTES = int(env("LOGIN_FENETRE_MINUTES", "15"))
LOGIN_BLOCAGE_MINUTES = int(env("LOGIN_BLOCAGE_MINUTES", "15"))


# ---------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Ouagadougou"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------
# Fichiers statiques et médias
# ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# En production sur cPanel, on place les fichiers servis par Apache dans le
# dossier public du sous-domaine : DJANGO_STATIC_ROOT et DJANGO_MEDIA_ROOT
# pointent alors vers ~/le-sous-domaine/static et .../media.
STATIC_ROOT = Path(env("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

try:
    MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
except OSError as exc:
    raise ImproperlyConfigured(
        f"\n\nLe dossier des photos ne peut pas être créé : {MEDIA_ROOT}\n"
        f"Raison : {exc}\n\n"
        "Corrigez DJANGO_MEDIA_ROOT dans le fichier .env avec un chemin qui existe\n"
        "et qui vous appartient, par exemple :\n"
        f"    DJANGO_MEDIA_ROOT={Path.home()}/VOTRE-SOUS-DOMAINE/media\n\n"
        "Le plus simple : lancez  python deploiement/configurer.py\n"
    ) from exc

# Filet de sécurité : sur un hébergement mutualisé, Apache ne sert pas toujours
# /media/ directement. Laissé à True, Django s'en charge lui-même — un peu moins
# rapide, mais les photos s'affichent toujours. À passer à False une fois le
# .htaccess « PassengerEnabled off » en place dans le dossier des médias.
SERVE_MEDIA = env_bool("DJANGO_SERVE_MEDIA", True)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG and "whitenoise.middleware.WhiteNoiseMiddleware" in MIDDLEWARE
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# Envois de fichiers.
# DATA_UPLOAD_MAX_MEMORY_SIZE ne concerne PAS les fichiers eux-mêmes (Django
# les met de côté séparément) mais le reste du formulaire : 5 Mo est large.
# FILE_UPLOAD_MAX_MEMORY_SIZE dit à partir de quelle taille un fichier est
# écrit sur disque au lieu d'être gardé en mémoire. On le laisse bas : sur un
# hébergement mutualisé, la mémoire est la ressource rare, pas le disque.
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
# Limite absolue acceptée par Django, quel que soit le formulaire.
# Doit rester sous les limites du serveur (upload_max_filesize côté cPanel).
MAX_UPLOAD_MB = int(env("MAX_UPLOAD_MB", "20"))


# ---------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "EazyMarket <no-reply@eazymarket.bf>")
CONTACT_EMAIL = env("CONTACT_EMAIL", "contact@eazymarket.bf")


# ---------------------------------------------------------------------
# Paramètres métier EazyMarket
# ---------------------------------------------------------------------
EAZYMARKET = {
    # Identité
    "SITE_NAME": env("SITE_NAME", "EazyMarket"),
    "SITE_TAGLINE": env("SITE_TAGLINE", "Achetez. Trouvez un pro. Au même endroit."),
    "CURRENCY": "FCFA",
    "COUNTRY": env("SITE_COUNTRY", "Burkina Faso"),
    "CITY": env("SITE_CITY", "Ouagadougou"),
    "SUPPORT_PHONE": env("SUPPORT_PHONE", "+226 64 69 12 08"),
    "SUPPORT_EMAIL": CONTACT_EMAIL,
    "WHATSAPP": env("SUPPORT_WHATSAPP", "22664691208"),
    # Deuxième ligne : quand la première ne répond pas
    "SUPPORT_PHONE_2": env("SUPPORT_PHONE_2", "+226 77 55 20 87"),
    "WHATSAPP_2": env("SUPPORT_WHATSAPP_2", "22677552087"),

    # ---- Boutique : emplacements produits ----
    # Le vendeur dispose d'emplacements. Les premiers sont offerts, ensuite il
    # achète des packs. Un emplacement = une annonce en ligne.
    # 0 = la boutique n'existe qu'une fois le pack payé. Mettre 2 ici
    # rétablirait l'essai gratuit, sans toucher au code.
    "SHOP_FREE_SLOTS": int(env("SHOP_FREE_SLOTS", "0")),
    "SHOP_PACK_SIZE": int(env("SHOP_PACK_SIZE", "10")),
    "SHOP_PACK_PRICE": int(env("SHOP_PACK_PRICE", "5000")),

    # ---- Boutique : commission sur les ventes ----
    # Le vendeur saisit ce qu'il veut toucher. La commission est ajoutée
    # par-dessus, puis le prix affiché est ARRONDI au palier supérieur pour
    # rester lisible (1 000 F → 1 100 F, jamais 1 050 F).
    "COMMISSION_RATE": float(env("COMMISSION_RATE", "5")),
    "COMMISSION_MIN": int(env("COMMISSION_MIN", "100")),
    # (seuil de prix, palier d'arrondi) — appliqué du plus petit au plus grand
    "PRICE_STEPS": [(10000, 100), (50000, 100), (200000, 500), (10**9, 1000)],

    # ---- Services : abonnement artisan ----
    "ARTISAN_SUB_PRICE": int(env("ARTISAN_SUB_PRICE", "1000")),
    "ARTISAN_SUB_DAYS": int(env("ARTISAN_SUB_DAYS", "90")),
    # Mettre à True pour une opération de lancement (profils visibles sans payer)
    "ARTISAN_FREE_LAUNCH": env_bool("ARTISAN_FREE_LAUNCH", False),
    "ARTISAN_BOOST_PRICE": int(env("ARTISAN_BOOST_PRICE", "2000")),
    "ARTISAN_BOOST_DAYS": int(env("ARTISAN_BOOST_DAYS", "7")),

    # ---- Services : déblocage du contact par le client ----
    "CONTACT_UNLOCK_PRICE": int(env("CONTACT_UNLOCK_PRICE", "200")),
    "CONTACT_UNLOCK_DAYS": int(env("CONTACT_UNLOCK_DAYS", "90")),
    # Nombre de contacts offerts à chaque nouveau client (pour amorcer l'usage)
    "CONTACT_FREE_UNLOCKS": int(env("CONTACT_FREE_UNLOCKS", "1")),

    # ---- Livreurs ----
    # Un livreur est activé après avoir parrainé N personnes, puis validation admin
    "DELIVERY_REQUIRED_SHARES": int(env("DELIVERY_REQUIRED_SHARES", "3")),

    # ---- Commandes : confirmation du vendeur ----
    # L'argent du client reste chez la plateforme tant que le vendeur n'a pas
    # confirmé qu'il a l'article. Passé le délai, la commande est annulée et
    # le client remboursé automatiquement.
    "ORDER_CONFIRMATION_HOURS": int(env("ORDER_CONFIRMATION_HOURS", "24")),
    "MADE_TO_ORDER_MAX": int(env("MADE_TO_ORDER_MAX", "20")),

    # ---------- Remboursement et litiges ----------
    # Un client annulé est d'abord recrédité en avoir. S'il préfère récupérer
    # l'argent sur son mobile money, il le demande — en dessous de ce montant
    # les frais de transfert coûtent plus cher que la somme rendue.
    "REFUND_MIN": int(env("REFUND_MIN", "500")),
    # Après la livraison, le client a ce délai pour dire qu'il n'a rien reçu.
    # C'est pendant cette fenêtre que l'argent du vendeur reste bloqué.
    "DISPUTE_WINDOW_DAYS": int(env("DISPUTE_WINDOW_DAYS", "3")),
    # Une commande confirmée mais jamais marquée livrée au bout de ce délai
    # est signalée dans le tableau de bord : quelque chose cloche.
    "DELIVERY_ALERT_DAYS": int(env("DELIVERY_ALERT_DAYS", "10")),

    # ---------- Vidéos ----------
    # Une vidéo de quelques secondes est la meilleure preuve qu'un vendeur
    # possède vraiment son article. Mais une vidéo pèse lourd : on limite
    # la durée et le poids, et on offre un petit nombre d'emplacements.
    # Un lien TikTok / YouTube ne consomme aucun emplacement : il ne coûte
    # ni disque ni bande passante.
    "VIDEO_FREE_SLOTS": int(env("VIDEO_FREE_SLOTS", "3")),
    "VIDEO_PACK_SIZE": int(env("VIDEO_PACK_SIZE", "5")),
    "VIDEO_PACK_PRICE": int(env("VIDEO_PACK_PRICE", "500")),
    "VIDEO_MAX_SECONDS": int(env("VIDEO_MAX_SECONDS", "30")),
    "VIDEO_MAX_MB": int(env("VIDEO_MAX_MB", "15")),
    "VIDEO_MAX_PAR_FICHE": int(env("VIDEO_MAX_PAR_FICHE", "3")),
    # Nombre d'annulations pour rupture de stock avant suspension de la boutique
    "SELLER_MAX_CANCELLATIONS": int(env("SELLER_MAX_CANCELLATIONS", "5")),
    # Seuil d'alerte dans le back-office
    "SELLER_ALERT_CANCELLATIONS": int(env("SELLER_ALERT_CANCELLATIONS", "2")),

    # ---- Livraison ----
    "DELIVERY_FEE_CITY": int(env("DELIVERY_FEE_CITY", "1000")),
    "DELIVERY_FEE_OUT": int(env("DELIVERY_FEE_OUT", "2500")),
    "FREE_DELIVERY_FROM": int(env("FREE_DELIVERY_FROM", "50000")),

    # ---- Reversement aux vendeurs ----
    "PAYOUT_MIN": int(env("PAYOUT_MIN", "5000")),
    "PAYOUT_DELAY_DAYS": int(env("PAYOUT_DELAY_DAYS", "3")),
}


# ---------------------------------------------------------------------
# Paiements (mobile money)
# ---------------------------------------------------------------------
PAYMENTS = {
    # Fournisseur actif : "manual" | "cinetpay"
    "PROVIDER": env("PAYMENT_PROVIDER", "manual"),

    # --- Encaissement manuel sur vos numéros marchands ---
    # Le client compose *144*10*NUMERO*MONTANT# puis valide avec son code.
    "MANUAL": {
        "USSD_TEMPLATE": env("ORANGE_USSD_TEMPLATE", "*144*10*{numero}*{montant}#"),
        "ACCOUNTS": [
            {
                "id": "om1",
                "label": "Orange Money",
                "number": env("ORANGE_MONEY_NUMBER_1", ""),
                "name": env("ORANGE_MONEY_NAME", ""),
                "whatsapp": env("ORANGE_MONEY_WHATSAPP_1", ""),
            },
            {
                "id": "om2",
                "label": "Orange Money (2ᵉ numéro)",
                "number": env("ORANGE_MONEY_NUMBER_2", ""),
                "name": env("ORANGE_MONEY_NAME", ""),
                "whatsapp": "",
            },
        ],
        "HOLDER": env("ORANGE_MONEY_NAME", ""),
        "MOOV_MONEY_NUMBER": env("MOOV_MONEY_NUMBER", ""),
        "MOOV_MONEY_WHATSAPP": env("MOOV_MONEY_WHATSAPP", ""),
        "WAVE_NUMBER": env("WAVE_NUMBER", ""),
        "WAVE_WHATSAPP": env("WAVE_WHATSAPP", ""),
    },

    # --- Agrégateur CinetPay (Orange, Moov, Wave, cartes) ---
    "CINETPAY": {
        "API_KEY": env("CINETPAY_API_KEY", ""),
        "SITE_ID": env("CINETPAY_SITE_ID", ""),
        "SECRET_KEY": env("CINETPAY_SECRET_KEY", ""),
        "BASE_URL": env("CINETPAY_BASE_URL", "https://api-checkout.cinetpay.com/v2"),
    },
    "PUBLIC_BASE_URL": env("PUBLIC_BASE_URL", "http://127.0.0.1:8000"),
}


# ---------------------------------------------------------------------
# Notifications (SMS)
# ---------------------------------------------------------------------
# Un commerçant burkinabè lit ses SMS, pas ses e-mails. Le SMS est donc le
# canal principal pour tout ce qui est urgent. La couche est enfichable :
# brancher un fournisseur revient à remplir ces valeurs.
NOTIFICATIONS = {
    # "log" (par défaut, écrit dans le journal) | "orange" | "http"
    "SMS_PROVIDER": env("SMS_PROVIDER", "log"),
    "SMS_SENDER": env("SMS_SENDER", "EAZYMARKET"),
    "SMS_ENABLED": env_bool("SMS_ENABLED", True),
    # Fournisseur générique : n'importe quelle API HTTP à paramètres
    "HTTP": {
        "URL": env("SMS_HTTP_URL", ""),
        "METHOD": env("SMS_HTTP_METHOD", "POST"),
        "TOKEN": env("SMS_HTTP_TOKEN", ""),
        # Noms des champs attendus par le fournisseur
        "FIELD_TO": env("SMS_HTTP_FIELD_TO", "to"),
        "FIELD_MESSAGE": env("SMS_HTTP_FIELD_MESSAGE", "message"),
        "FIELD_SENDER": env("SMS_HTTP_FIELD_SENDER", "sender"),
    },
    # Orange SMS API (Burkina Faso)
    "ORANGE": {
        "CLIENT_ID": env("ORANGE_SMS_CLIENT_ID", ""),
        "CLIENT_SECRET": env("ORANGE_SMS_CLIENT_SECRET", ""),
        "SENDER_NUMBER": env("ORANGE_SMS_SENDER_NUMBER", ""),
        "BASE_URL": env("ORANGE_SMS_BASE_URL", "https://api.orange.com"),
    },
}


# ---------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------
LOG_DIR = Path(env("DJANGO_LOG_DIR", str(BASE_DIR / "logs")))
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # Un journal illisible ne doit jamais empêcher le site de démarrer
    LOG_DIR = BASE_DIR / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "eazymarket.log",
            "maxBytes": 2 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console", "file"], "level": "ERROR", "propagate": False},
        "payments": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}


# ---------------------------------------------------------------------
# Durcissement en production
# ---------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 30)))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
