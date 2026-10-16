"""
Point d'entrée de l'application pour Passenger (cPanel / LWS).

Ce fichier doit rester à la racine du dossier de l'application Python, à côté
de manage.py. C'est lui que vous indiquez dans « Setup Python App » →
Application startup file : passenger_wsgi.py

L'objet exposé doit s'appeler `application`.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "EazyMarket.settings")

# Marque « on tourne sur le serveur ». Les réglages s'en servent pour refuser
# de démarrer si le fichier .env manque, au lieu de repartir en silence sur
# une base SQLite vide avec DEBUG activé.
os.environ["EAZYMARKET_SERVEUR"] = "1"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
