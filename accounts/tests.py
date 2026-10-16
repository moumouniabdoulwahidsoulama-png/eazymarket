"""Tests de la règle « on paie le pack avant d'ouvrir sa boutique »."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from payments.models import Transaction
from payments.services import confirm_transaction
from products.models import Category, Product

User = get_user_model()


class OuvertureDeBoutique(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("moussa", password="x")
        self.client.login(username="moussa", password="x")

    def test_le_formulaire_n_ouvre_pas_la_boutique(self):
        reponse = self.client.post(reverse("become_seller"), {
            "store_name": "Faso Électro", "phone": "70000000", "quartier": "Gounghin",
        })
        profil = UserProfile.objects.get(user=self.user)
        self.assertEqual(profil.store_name, "Faso Électro")
        self.assertFalse(profil.is_store_active)
        self.assertFalse(profil.can_sell)
        self.assertTrue(profil.boutique_en_attente)
        # On est envoyé vers le paiement, pas vers le tableau de bord.
        self.assertRedirects(reponse, reverse("buy_slots"))

    def test_aucun_emplacement_offert(self):
        profil = self.user.profile
        profil.store_name = "Test"
        profil.save()
        self.assertEqual(profil.total_slots, 0)
        self.assertFalse(profil.can_publish)

    def test_pas_de_boucle_entre_le_formulaire_et_le_paiement(self):
        self.client.post(reverse("become_seller"), {
            "store_name": "Faso Électro", "phone": "70000000",
        })
        # La page de paiement doit s'afficher, pas renvoyer au formulaire.
        reponse = self.client.get(reverse("buy_slots"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Faso Électro")
        # Et revenir au formulaire renvoie au paiement, sans redemander la fiche.
        reponse = self.client.get(reverse("become_seller"))
        self.assertRedirects(reponse, reverse("buy_slots"))

    def test_le_paiement_ouvre_la_boutique(self):
        self.client.post(reverse("become_seller"), {
            "store_name": "Faso Électro", "phone": "70000000",
        })
        self.client.post(reverse("buy_slots"), {"packs": "1"})

        tx = Transaction.objects.get(purpose=Transaction.Purpose.SHOP_PACK)
        self.assertEqual(tx.amount, 5000)

        confirm_transaction(tx)
        profil = UserProfile.objects.get(user=self.user)
        self.assertTrue(profil.is_store_active)
        self.assertTrue(profil.can_sell)
        self.assertFalse(profil.boutique_en_attente)
        self.assertEqual(profil.total_slots, 10)
        self.assertTrue(profil.can_publish)

    def test_tableau_de_bord_inaccessible_sans_paiement(self):
        self.client.post(reverse("become_seller"), {
            "store_name": "Faso Électro", "phone": "70000000",
        })
        reponse = self.client.get(reverse("seller_dashboard"))
        self.assertRedirects(
            reponse, reverse("become_seller"), target_status_code=302
        )

    def test_publier_est_refuse_sans_paiement(self):
        self.client.post(reverse("become_seller"), {
            "store_name": "Faso Électro", "phone": "70000000",
        })
        categorie = Category.objects.create(name="Électro", slug="electro")
        self.client.post(reverse("add_product"), {
            "name": "Frigo", "base_price": "50000", "category": categorie.id,
            "description": "un frigo", "stock": "1",
        })
        self.assertEqual(Product.objects.count(), 0)

    def test_la_boutique_officielle_reste_libre(self):
        profil = self.user.profile
        profil.unlimited_slots = True
        profil.save()
        self.assertTrue(profil.can_sell)
        self.assertIsNone(profil.total_slots)
        self.assertTrue(profil.can_publish)

    def test_un_vendeur_deja_ouvert_n_est_pas_bloque(self):
        """Les boutiques ouvertes avant le changement continuent de marcher."""
        profil = self.user.profile
        profil.store_name = "Ancienne boutique"
        profil.is_store_active = True
        profil.extra_slots = 10
        profil.save()
        self.assertTrue(profil.can_sell)
        self.assertFalse(profil.boutique_en_attente)
        self.assertEqual(profil.total_slots, 10)
