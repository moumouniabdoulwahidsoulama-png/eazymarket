"""
Installe les données de référence de l'application : rayons de la boutique et
métiers de l'annuaire. Aucune donnée fictive — que du contenu réel, prêt à
recevoir de vrais vendeurs et de vrais artisans.

    python manage.py init_catalogue

La commande est idempotente : on peut la relancer sans rien casser. Elle met à
jour les icônes et l'ordre d'affichage, et n'écrase jamais les descriptions
saisies depuis l'administration.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Category
from services.models import ServiceCategory

# ---------------------------------------------------------------------
# Rayons de la boutique
# ---------------------------------------------------------------------
CATEGORIES = [
    ("Téléphones & accessoires", "fa-mobile-screen-button"),
    ("Informatique", "fa-laptop"),
    ("TV, son & image", "fa-tv"),
    ("Électroménager", "fa-blender"),
    ("Énergie solaire", "fa-solar-panel"),
    ("Mode homme", "fa-shirt"),
    ("Mode femme", "fa-person-dress"),
    ("Chaussures & sacs", "fa-shoe-prints"),
    ("Beauté & soins", "fa-spray-can-sparkles"),
    ("Bijoux & montres", "fa-gem"),
    ("Maison & décoration", "fa-couch"),
    ("Cuisine & ustensiles", "fa-utensils"),
    ("Alimentation & terroir", "fa-bowl-food"),
    ("Bébé & enfants", "fa-baby"),
    ("Sport & loisirs", "fa-futbol"),
    ("Motos & pièces", "fa-motorcycle"),
    ("Auto & pièces", "fa-car"),
    ("Construction & outillage", "fa-trowel-bricks"),
    ("Agriculture & élevage", "fa-seedling"),
    ("Artisanat & art", "fa-palette"),
    ("Livres & papeterie", "fa-book"),
    ("Santé & bien-être", "fa-heart-pulse"),
]

# ---------------------------------------------------------------------
# Métiers de l'annuaire — tous les corps de métier, y compris les
# services à domicile et les métiers de la maison.
# ---------------------------------------------------------------------
METIERS = [
    # --- Bâtiment & rénovation ---
    ("Maçonnerie", "fa-trowel-bricks", "Fondations, murs, chapes, crépissage."),
    ("Plomberie", "fa-faucet-drip", "Fuites, robinetterie, sanitaires, canalisations."),
    ("Électricité bâtiment", "fa-bolt", "Installation, tableau, dépannage, mise aux normes."),
    ("Peinture & décoration", "fa-paint-roller", "Peinture intérieure et extérieure, enduits."),
    ("Carrelage & dallage", "fa-border-all", "Pose de carreaux, faïence, dallage de cour."),
    ("Menuiserie bois", "fa-hammer", "Portes, meubles, lits, placards sur mesure."),
    ("Aluminium & vitrerie", "fa-window-maximize", "Fenêtres, baies, vitrines, moustiquaires."),
    ("Soudure & métallerie", "fa-fire-flame-simple", "Portails, grilles, charpente métallique."),
    ("Faux plafond & plâtrerie", "fa-grip-lines", "Plafonds décoratifs, cloisons, corniches."),
    ("Étanchéité & toiture", "fa-house-chimney", "Terrasses, tôles, gouttières, infiltrations."),
    ("Puits & forage", "fa-water", "Forage, pompes, château d'eau."),
    ("Terrassement & gros œuvre", "fa-truck-monster", "Fouilles, remblai, nivellement."),
    # --- Énergie & technique ---
    ("Froid & climatisation", "fa-snowflake", "Split, chambres froides, réfrigérateurs."),
    ("Énergie solaire", "fa-solar-panel", "Panneaux, batteries, kits solaires."),
    ("Groupe électrogène", "fa-plug-circle-bolt", "Installation, entretien, réparation."),
    ("Antenne & parabole", "fa-satellite-dish", "Installation et réglage de décodeurs."),
    ("Réparation électroménager", "fa-blender", "Machines à laver, congélateurs, fours."),
    # --- Auto, moto, transport ---
    ("Mécanique auto", "fa-screwdriver-wrench", "Diagnostic, entretien, réparation moteur."),
    ("Mécanique moto", "fa-motorcycle", "Entretien et réparation deux-roues."),
    ("Vulcanisation & pneus", "fa-circle-dot", "Pneus, chambres à air, équilibrage."),
    ("Tôlerie & peinture auto", "fa-spray-can", "Carrosserie, redressage, peinture."),
    ("Lavage auto & moto", "fa-car", "Lavage à domicile ou en station."),
    ("Chauffeur & location", "fa-car-side", "Chauffeur à la journée, location de véhicule."),
    ("Déménagement", "fa-truck-ramp-box", "Transport de meubles et marchandises."),
    # --- Numérique ---
    ("Réparation téléphone", "fa-mobile-screen-button", "Écrans, batteries, déblocage."),
    ("Informatique & maintenance", "fa-laptop-code", "Dépannage PC, réseau, installation."),
    ("Développement web & applis", "fa-code", "Sites internet, applications, boutiques en ligne."),
    ("Infographie & impression", "fa-print", "Flyers, banderoles, cartes de visite, sérigraphie."),
    ("Photographie & vidéo", "fa-camera", "Mariages, événements, portraits, drone."),
    ("Sonorisation & DJ", "fa-music", "Matériel son, animation musicale."),
    ("Community management", "fa-hashtag", "Pages Facebook, TikTok, publicité en ligne."),
    # --- Mode, beauté, artisanat ---
    ("Couture & mode", "fa-scissors", "Tenues sur mesure, retouches, uniformes."),
    ("Broderie & tissage", "fa-shirt", "Faso dan fani, bogolan, broderie machine."),
    ("Coiffure femme", "fa-wand-magic-sparkles", "Tresses, tissages, soins capillaires."),
    ("Coiffure homme & barbier", "fa-scissors", "Coupe, barbe, à domicile ou en salon."),
    ("Esthétique & manucure", "fa-hand-sparkles", "Ongles, maquillage, soins du visage."),
    ("Cordonnerie & maroquinerie", "fa-shoe-prints", "Chaussures, sacs, articles en cuir."),
    ("Bijouterie & orfèvrerie", "fa-gem", "Or, argent, bronze, réparation de bijoux."),
    ("Sculpture & bronze", "fa-monument", "Statues, objets d'art, fonderie."),
    ("Poterie & vannerie", "fa-jar", "Canaris, paniers, objets décoratifs."),
    # --- Maison & services aux personnes ---
    ("Aide-ménagère & ménage", "fa-broom", "Entretien de maison, bureaux, fin de chantier."),
    ("Gardiennage & sécurité", "fa-user-shield", "Gardien de jour ou de nuit, vigile."),
    ("Jardinage & espaces verts", "fa-leaf", "Entretien de jardin, taille, arrosage."),
    ("Cuisine à domicile", "fa-utensils", "Cuisinier pour la famille ou un événement."),
    ("Blanchisserie & repassage", "fa-shirt", "Lavage, repassage, à domicile ou en pressing."),
    ("Garde d'enfants", "fa-baby", "Nounou à domicile, garde ponctuelle."),
    ("Aide aux personnes âgées", "fa-hand-holding-heart", "Accompagnement et présence à domicile."),
    ("Désinsectisation", "fa-bug", "Cafards, moustiques, termites, rongeurs."),
    ("Vidange de fosse", "fa-toilet", "Vidange septique, curage, assainissement."),
    ("Livraison & coursier", "fa-motorcycle", "Courses, colis, documents en ville."),
    # --- Événementiel ---
    ("Traiteur & restauration", "fa-utensils", "Repas pour mariages, baptêmes, séminaires."),
    ("Pâtisserie", "fa-cake-candles", "Gâteaux de cérémonie, viennoiseries."),
    ("Location matériel événementiel", "fa-chair", "Chaises, bâches, vaisselle, groupe."),
    ("Décoration événementielle", "fa-champagne-glasses", "Salles, tentes, arches florales."),
    ("Animation & maître de cérémonie", "fa-microphone", "Animation de mariages et soirées."),
    # --- Agriculture & élevage ---
    ("Agriculture & maraîchage", "fa-seedling", "Production, plantation, conseil agricole."),
    ("Élevage & aviculture", "fa-egg", "Volailles, porcs, ovins, provende."),
    ("Irrigation & goutte-à-goutte", "fa-droplet", "Installation de systèmes d'arrosage."),
    ("Vétérinaire", "fa-paw", "Soins et vaccination des animaux."),
    # --- Services professionnels ---
    ("Comptabilité & gestion", "fa-calculator", "Tenue de comptes, déclarations, paie."),
    ("Conseil juridique", "fa-scale-balanced", "Contrats, formalités, accompagnement."),
    ("Traduction & rédaction", "fa-language", "Traduction, saisie, rédaction de documents."),
    ("Cours particuliers", "fa-chalkboard-user", "Répétiteur à domicile, toutes matières."),
    ("Secrétariat & saisie", "fa-keyboard", "Saisie, mise en page, photocopie."),
    ("Santé à domicile", "fa-user-nurse", "Infirmier, soins et injections à domicile."),
]


class Command(BaseCommand):
    help = "Installe les rayons de la boutique et les métiers de l'annuaire."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("init_pays")

        created = updated = 0
        for order, (name, icon) in enumerate(CATEGORIES):
            _, was_created = Category.objects.update_or_create(
                name=name, defaults={"icon": icon, "order": order}
            )
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(f"Boutique : {len(CATEGORIES)} rayons ({created} nouveaux)."))

        created = 0
        for order, (name, icon, description) in enumerate(METIERS):
            obj, was_created = ServiceCategory.objects.get_or_create(
                name=name, defaults={"icon": icon, "order": order, "description": description}
            )
            if not was_created:
                obj.icon, obj.order = icon, order
                if not obj.description:
                    obj.description = description
                obj.save(update_fields=["icon", "order", "description"])
            created += was_created
        self.stdout.write(self.style.SUCCESS(f"Services : {len(METIERS)} métiers ({created} nouveaux)."))
        self.stdout.write("Aucune donnée fictive n'a été créée.")
