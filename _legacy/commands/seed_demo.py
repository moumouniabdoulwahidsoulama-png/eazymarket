"""
Remplit la base avec des catégories, des métiers et un jeu de données de
démonstration. Idéal pour montrer le site à quelqu'un ou pour développer.

    python manage.py seed_demo            # catégories + métiers seulement
    python manage.py seed_demo --complet  # + comptes, produits et artisans fictifs
"""

import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Category, Product
from services.models import Artisan, ServiceCategory

CATEGORIES = [
    ("Téléphones & accessoires", "fa-mobile-screen-button"),
    ("Informatique", "fa-laptop"),
    ("Électroménager", "fa-blender"),
    ("Mode & habillement", "fa-shirt"),
    ("Beauté & soins", "fa-spray-can-sparkles"),
    ("Maison & décoration", "fa-couch"),
    ("Alimentation & terroir", "fa-bowl-food"),
    ("Agriculture & élevage", "fa-seedling"),
    ("Motos & pièces", "fa-motorcycle"),
    ("Construction & outillage", "fa-trowel-bricks"),
    ("Enfants & bébé", "fa-baby"),
    ("Sport & loisirs", "fa-futbol"),
]

METIERS = [
    ("Plomberie", "fa-faucet-drip"),
    ("Électricité", "fa-bolt"),
    ("Menuiserie bois", "fa-hammer"),
    ("Soudure & métallerie", "fa-fire-flame-simple"),
    ("Maçonnerie", "fa-trowel-bricks"),
    ("Peinture bâtiment", "fa-roller-coaster"),
    ("Couture & mode", "fa-scissors"),
    ("Coiffure & esthétique", "fa-scissors"),
    ("Mécanique auto & moto", "fa-screwdriver-wrench"),
    ("Froid & climatisation", "fa-snowflake"),
    ("Informatique & réparation", "fa-laptop-code"),
    ("Photographie & vidéo", "fa-camera"),
    ("Traiteur & évènementiel", "fa-utensils"),
    ("Ménage & entretien", "fa-broom"),
    ("Carrelage", "fa-border-all"),
    ("Vitrerie & aluminium", "fa-window-maximize"),
]

QUARTIERS = ["Tanghin", "Zogona", "Dapoya", "Gounghin", "Pissy", "Karpala", "Ouaga 2000", "Cissin"]

DEMO_PRODUCTS = [
    ("Smartphone 128 Go double SIM", "Téléphones & accessoires", 85000),
    ("Ventilateur sur pied 3 vitesses", "Électroménager", 22000),
    ("Sac à main en cuir cousu main", "Mode & habillement", 18000),
    ("Panneau solaire 100 W + régulateur", "Construction & outillage", 65000),
    ("Beurre de karité pur 1 kg", "Beauté & soins", 4500),
    ("Ordinateur portable reconditionné i5", "Informatique", 195000),
    ("Table basse en bois de teck", "Maison & décoration", 45000),
    ("Sac de riz local 25 kg", "Alimentation & terroir", 17500),
    ("Casque moto homologué", "Motos & pièces", 15000),
    ("Machine à coudre mécanique", "Construction & outillage", 78000),
]


class Command(BaseCommand):
    help = "Crée les catégories, les métiers et (option) un jeu de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--complet", action="store_true", help="Ajoute des comptes et contenus fictifs")

    @transaction.atomic
    def handle(self, *args, **options):
        for order, (name, icon) in enumerate(CATEGORIES):
            Category.objects.update_or_create(name=name, defaults={"icon": icon, "order": order})
        self.stdout.write(self.style.SUCCESS(f"{len(CATEGORIES)} catégories produits en place."))

        for order, (name, icon) in enumerate(METIERS):
            ServiceCategory.objects.update_or_create(name=name, defaults={"icon": icon, "order": order})
        self.stdout.write(self.style.SUCCESS(f"{len(METIERS)} métiers en place."))

        if not options["complet"]:
            self.stdout.write("Relancez avec --complet pour ajouter des contenus de démonstration.")
            return

        seller, created = User.objects.get_or_create(
            username="boutique_demo", defaults={"email": "vendeur@example.bf"}
        )
        if created:
            seller.set_password("demo12345")
            seller.save()
        profile = seller.profile
        profile.user_type = "seller"
        profile.store_name = "Faso Électro"
        profile.store_description = "Électroménager et petit matériel, garantie 6 mois."
        profile.is_store_active = True
        profile.quartier = "Gounghin"
        profile.phone = "+226 70 00 00 01"
        profile.save()

        for name, cat_name, price in DEMO_PRODUCTS:
            category = Category.objects.get(name=cat_name)
            Product.objects.get_or_create(
                name=name,
                defaults={
                    "description": f"{name}. Article vérifié avant expédition. "
                    "Livraison possible dans toute la ville, retrait gratuit en boutique.",
                    "short_description": name,
                    "base_price": price,
                    "stock": random.randint(2, 25),
                    "category": category,
                    "seller": seller,
                    "is_featured": random.random() < 0.35,
                    "sold_count": random.randint(0, 30),
                },
            )
        self.stdout.write(self.style.SUCCESS(f"{len(DEMO_PRODUCTS)} produits de démonstration créés."))

        noms = [
            ("Ousmane Sawadogo", "Plomberie"), ("Fatimata Ouédraogo", "Couture & mode"),
            ("Issa Compaoré", "Électricité"), ("Salif Kaboré", "Menuiserie bois"),
            ("Aminata Zongo", "Coiffure & esthétique"), ("Boureima Traoré", "Soudure & métallerie"),
            ("Rasmané Nikièma", "Mécanique auto & moto"), ("Alizeta Sanou", "Traiteur & évènementiel"),
        ]
        for index, (full_name, metier) in enumerate(noms):
            username = f"pro{index + 1}"
            user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@example.bf"})
            if created:
                user.set_password("demo12345")
                user.save()
            user.profile.user_type = "artisan"
            user.profile.save()
            Artisan.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": full_name,
                    "service_category": ServiceCategory.objects.get(name=metier),
                    "phone": f"+226 7{random.randint(0, 9)} {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
                    "address": "Atelier au bord de la voie principale",
                    "quartier": random.choice(QUARTIERS),
                    "description": f"{metier} depuis plus de {random.randint(3, 18)} ans à Ouagadougou. "
                    "Travail soigné, devis gratuit, déplacement dans toute la ville.",
                    "years_experience": random.randint(3, 18),
                    "price_range": f"{random.choice([3, 5, 10])} 000 – {random.choice([25, 40, 75])} 000 FCFA",
                    "is_verified": random.random() < 0.5,
                    "accepts_urgent": random.random() < 0.5,
                    "is_featured": index < 3,
                    "rating": round(random.uniform(3.8, 5.0), 2),
                    "total_reviews": random.randint(2, 24),
                    "completed_jobs": random.randint(3, 60),
                },
            )
        self.stdout.write(self.style.SUCCESS(f"{len(noms)} artisans de démonstration créés."))
        self.stdout.write(self.style.WARNING("Comptes de test : boutique_demo / pro1…pro8 — mot de passe demo12345"))
