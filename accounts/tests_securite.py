"""Tests des défenses de connexion : blocage, 2FA, journal."""

import io
import shutil
import tempfile
from unittest import mock

from PIL import Image

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import LogConnexion

User = get_user_model()


class BlocageForceBrute(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("victime", password="bonmotdepasse", email="v@x.bf")

    def _mauvaise_tentative(self):
        return self.client.post(reverse("login"),
                                {"username": "victime", "password": "faux"})

    def test_les_echecs_sont_journalises(self):
        self._mauvaise_tentative()
        self.assertEqual(LogConnexion.objects.filter(succes=False).count(), 1)

    def test_blocage_apres_cinq_echecs(self):
        for _ in range(5):
            self._mauvaise_tentative()
        # 6e tentative, cette fois avec le BON mot de passe : doit être refusée.
        r = self.client.post(reverse("login"),
                             {"username": "victime", "password": "bonmotdepasse"})
        self.assertContains(r, "Trop de tentatives")
        self.assertFalse(r.wsgi_request.user.is_authenticated)

    def test_connexion_normale_marche(self):
        r = self.client.post(reverse("login"),
                             {"username": "victime", "password": "bonmotdepasse"})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(LogConnexion.objects.filter(succes=True).exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DoubleAuthentification(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("marchand", password="secret123", email="m@x.bf")
        p = self.user.profile
        p.two_factor_enabled = True
        p.two_factor_channel = "email"
        p.save()

    def test_le_mot_de_passe_seul_ne_connecte_pas(self):
        r = self.client.post(reverse("login"),
                             {"username": "marchand", "password": "secret123"})
        self.assertRedirects(r, reverse("login_verify"))
        # Pas encore connecté.
        r2 = self.client.get(reverse("profile"))
        self.assertNotEqual(r2.status_code, 200)
        # Un code est parti par e-mail.
        self.assertEqual(len(mail.outbox), 1)

    @mock.patch("accounts.securite.generer_code", return_value="123456")
    def test_le_bon_code_connecte(self, _faux_code):
        self.client.post(reverse("login"),
                         {"username": "marchand", "password": "secret123"})
        r = self.client.post(reverse("login_verify"), {"code": "123456"})
        self.assertEqual(r.status_code, 302)
        # Connecté pour de bon.
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.id)

    def test_mauvais_code_refuse(self):
        self.client.post(reverse("login"),
                         {"username": "marchand", "password": "secret123"})
        r = self.client.post(reverse("login_verify"), {"code": "000000"})
        self.assertContains(r, "incorrect")


class ActivationDeuxFacteurs(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="x", email="u@x.bf")
        self.client.login(username="u", password="x")

    def test_activer_puis_desactiver(self):
        r = self.client.post(reverse("security_settings"),
                             {"action": "activer", "canal": "email"})
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.two_factor_enabled)
        r = self.client.post(reverse("security_settings"), {"action": "desactiver"})
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.two_factor_enabled)

    def test_pas_d_email_pas_d_activation(self):
        self.user.email = ""
        self.user.save()
        self.client.post(reverse("security_settings"),
                        {"action": "activer", "canal": "email"})
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.two_factor_enabled)


MEDIA_TMP = tempfile.mkdtemp(prefix="eazy-test-media-")


@override_settings(MEDIA_ROOT=MEDIA_TMP)
class CompressionImage(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def test_grande_photo_reduite(self):
        from EazyMarket.imagerie import compresser_image
        img = Image.new("RGB", (3000, 2200), (180, 90, 30))
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=95)
        avant = buf.tell()
        fichier = SimpleUploadedFile("photo.jpg", buf.getvalue(), content_type="image/jpeg")
        fichier.size = avant
        contenu, ext = compresser_image(fichier)
        apres = len(contenu.read())
        self.assertEqual(ext, "jpg")
        self.assertLess(apres, avant)

    def test_produit_compresse_a_l_envoi(self):
        from products.models import Product, Category
        img = Image.new("RGB", (2500, 1800), (40, 120, 90))
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=95)
        photo = SimpleUploadedFile("gros.jpg", buf.getvalue(), content_type="image/jpeg")
        cat = Category.objects.create(name="X", slug="x")
        vendeur = User.objects.create_user("vend", password="x")
        p = Product.objects.create(name="Objet", slug="objet", description="d",
                                   base_price=1000, stock=1, category=cat,
                                   seller=vendeur, main_image=photo)
        p.refresh_from_db()
        # Le fichier stocké est plus léger que l'original de ~1,2 Mo.
        self.assertLess(p.main_image.size, len(buf.getvalue()))
        self.assertTrue(p.main_image.name.endswith(".jpg"))
