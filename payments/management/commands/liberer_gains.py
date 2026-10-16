"""Libère les gains vendeurs arrivés à échéance. À lancer une fois par jour."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.services import release_due_entries


class Command(BaseCommand):
    help = "Rend disponibles au retrait les gains dont le délai de sécurité est écoulé."

    def handle(self, *args, **options):
        count = release_due_entries()
        horodatage = timezone.localtime().strftime("%d/%m/%Y %H:%M")
        self.stdout.write(self.style.SUCCESS(
            f"[{horodatage}] {count} écriture(s) de gains libérée(s)."
        ))
