"""Tests de la protection du contact artisan.

Le déblocage à 200 FCFA ne vaut que si le numéro n'est visible nulle part
ailleurs sur la page. Ces tests vérifient qu'aucune fuite ne revient.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from services.models import Artisan, ServiceCategory
from services.templatetags.protection import masquer_numeros

User = get_user_model()


class MasqueDuNumero(TestCase):
    def test_seuls_deux_chiffres_visibles(self):
        artisan = Artisan(phone="02096685")
        masque = artisan.phone_masque
        self.assertEqual(masque, "02 •• •• ••")
        # Le cœur du problème : le numéro entier ne doit jamais apparaître.
        self.assertNotIn("096685", masque)

    def test_indicatif_retire(self):
        self.assertEqual(Artisan(phone="+226 70 12 34 56").phone_masque, "70 •• •• ••")
        self.assertEqual(Artisan(phone="0022670123456").phone_masque, "70 •• •• ••")

    def test_numero_vide(self):
        self.assertEqual(Artisan(phone="").phone_masque, "•• •• •• ••")


class MasqueDansLesTextes(TestCase):
    def test_numero_dans_la_presentation(self):
        for texte in ["Appelez-moi au 70 12 34 56",
                      "whatsapp +226 02 09 66 85",
                      "contact 02096685",
                      "joignable au 70-12-34-56"]:
            with self.subTest(texte=texte):
                self.assertNotIn("34 56", masquer_numeros(texte))
                self.assertIn("••", masquer_numeros(texte))

    def test_les_prix_ne_sont_pas_masques(self):
        for texte in ["tarifs 25f - 100 000 fcfa",
                      "Formation de 25 000 FCFA sur 3 jours",
                      "15 ans de métier, livraison en 24h"]:
            with self.subTest(texte=texte):
                self.assertEqual(masquer_numeros(texte), texte)

    def test_client_ayant_paye_voit_tout(self):
        texte = "Appelez au 70 12 34 56"
        self.assertEqual(masquer_numeros(texte, True), texte)


class PageArtisan(TestCase):
    def setUp(self):
        self.categorie = ServiceCategory.objects.create(name="Secrétariat", slug="secretariat")
        self.user = User.objects.create_user("rosine", password="x")
        self.artisan = Artisan.objects.create(
            user=self.user, service_category=self.categorie,
            full_name="ROSINE PAGBELGUM", phone="02096685", whatsapp="02096685",
            description="Secrétaire expérimentée. Appelez-moi au 02 09 66 85.",
            address="Saaba", quartier="Saaba", price_range="25f - 100 000 fcfa",
            years_experience=10,
        )

    def test_le_numero_ne_fuit_nulle_part(self):
        reponse = self.client.get(reverse("artisan_detail", args=[self.artisan.id]))
        self.assertEqual(reponse.status_code, 200)
        page = reponse.content.decode()

        # Ni en clair, ni dans un masque trop bavard, ni dans la présentation.
        self.assertNotIn("02096685", page)
        self.assertNotIn("02 09 66 85", page)
        self.assertIn("02 •• •• ••", page)

    def test_les_tarifs_restent_lisibles(self):
        reponse = self.client.get(reverse("artisan_detail", args=[self.artisan.id]))
        self.assertContains(reponse, "100 000 fcfa")
