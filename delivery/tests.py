"""Tests de l'annuaire public des livreurs."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AnnuaireLivreurs(TestCase):
    def setUp(self):
        self.valide = User.objects.create_user("issa", password="x", first_name="Issa", last_name="K")
        p = self.valide.profile
        p.is_driver = True; p.is_verified = True; p.is_available = True
        p.vehicle_type = "moto"; p.delivery_zone = "Tanghin, Zogona"
        p.phone = "70112233"; p.whatsapp = "70112233"; p.total_deliveries = 12
        p.save()

        self.non_valide = User.objects.create_user("brouillon", password="x")
        q = self.non_valide.profile
        q.is_driver = True; q.is_verified = False; q.save()

    def test_liste_publique_montre_les_valides(self):
        r = self.client.get(reverse("driver_list"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Issa")

    def test_liste_cache_les_non_valides(self):
        r = self.client.get(reverse("driver_list"))
        self.assertNotContains(r, "brouillon")

    def test_recherche_par_zone(self):
        r = self.client.get(reverse("driver_list"), {"q": "Tanghin"})
        self.assertContains(r, "Issa")
        r = self.client.get(reverse("driver_list"), {"q": "Bobo"})
        self.assertNotContains(r, "Issa")

    def test_numero_cache_sans_connexion(self):
        r = self.client.get(reverse("driver_detail", args=[self.valide.profile.id]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "70112233")
        self.assertContains(r, "Connectez-vous")

    def test_numero_visible_une_fois_connecte(self):
        self.client.force_login(User.objects.create_user("curieux", password="x"))
        r = self.client.get(reverse("driver_detail", args=[self.valide.profile.id]))
        self.assertContains(r, "70112233")

    def test_fiche_d_un_non_valide_introuvable(self):
        r = self.client.get(reverse("driver_detail", args=[self.non_valide.profile.id]))
        self.assertEqual(r.status_code, 404)
