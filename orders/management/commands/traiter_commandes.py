"""
Annule les commandes que les vendeurs n'ont pas confirmées à temps
et rembourse les clients. À lancer toutes les heures.

    python manage.py traiter_commandes

Chaque exécution écrit une ligne horodatée : un journal qui avance prouve
que la tâche tourne, un journal vide prouve le contraire. C'est la seule
façon simple de vérifier qu'un cron fait bien son travail.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.services import traiter_les_commandes_expirees


class Command(BaseCommand):
    help = "Annule et rembourse les commandes non confirmées dans le délai."

    def add_arguments(self, parser):
        parser.add_argument(
            "--silencieux", action="store_true",
            help="N'écrire une ligne que s'il s'est passé quelque chose.",
        )

    def handle(self, *args, **options):
        nombre = traiter_les_commandes_expirees()
        horodatage = timezone.localtime().strftime("%d/%m/%Y %H:%M")

        if nombre:
            self.stdout.write(self.style.WARNING(
                f"[{horodatage}] {nombre} part(s) de commande annulée(s) faute "
                "de confirmation. Les clients ont été remboursés."
            ))
        elif not options["silencieux"]:
            self.stdout.write(self.style.SUCCESS(
                f"[{horodatage}] Aucune commande en retard."
            ))
