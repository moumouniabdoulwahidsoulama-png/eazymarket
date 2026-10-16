"""Tests des vidéos : quota, contrôles, liens externes, affichage."""

import shutil
import struct
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Category, Product
from videos.duree import duree_en_secondes
from videos.liens import identifier, url_de_lecture
from videos.models import Video
from videos.services import ajouter_video, emplacements

User = get_user_model()

# Les envois de fichiers vont dans un dossier temporaire : les tests ne
# doivent jamais laisser de vidéos dans le dossier media du projet.
MEDIA_DE_TEST = tempfile.mkdtemp(prefix="eazymarket-videos-")


class BaseVideo(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_DE_TEST, ignore_errors=True)


def faux_mp4(secondes=10, octets_de_remplissage=2048):
    """Fabrique un fichier au format MP4 avec un vrai bloc mvhd.

    On ne dépend d'aucun outil externe : on écrit l'en-tête à la main, ce qui
    permet de vérifier que la lecture de durée fonctionne réellement.
    """
    echelle = 1000
    mvhd = (
        b"mvhd"
        + bytes([0])                       # version 0
        + b"\x00\x00\x00"                  # drapeaux
        + b"\x00" * 8                      # dates de création / modification
        + struct.pack(">I", echelle)
        + struct.pack(">I", secondes * echelle)
    )
    return b"\x00\x00\x00\x20ftypisom" + b"\x00" * 16 + mvhd + b"\x00" * octets_de_remplissage


class LectureDeLaDuree(TestCase):
    def test_lit_la_duree_dans_l_entete(self):
        fichier = SimpleUploadedFile("clip.mp4", faux_mp4(18), content_type="video/mp4")
        self.assertEqual(duree_en_secondes(fichier), 18)

    def test_fichier_illisible_ne_bloque_pas(self):
        fichier = SimpleUploadedFile("clip.mp4", b"pas une video", content_type="video/mp4")
        self.assertEqual(duree_en_secondes(fichier), 0)

    def test_le_fichier_reste_lisible_apres_analyse(self):
        contenu = faux_mp4(5)
        fichier = SimpleUploadedFile("clip.mp4", contenu, content_type="video/mp4")
        duree_en_secondes(fichier)
        self.assertEqual(fichier.read(), contenu)


class ReconnaissanceDesLiens(TestCase):
    def test_plateformes_acceptees(self):
        self.assertEqual(identifier("https://www.tiktok.com/@moi/video/7234567890123456789"), "tiktok")
        self.assertEqual(identifier("https://youtu.be/dQw4w9WgXcQ"), "youtube")
        self.assertEqual(identifier("https://www.facebook.com/watch/?v=123"), "facebook")

    def test_lien_quelconque_refuse(self):
        self.assertEqual(identifier("https://exemple-douteux.tld/video"), "")
        self.assertEqual(identifier(""), "")

    def test_adresse_de_lecture(self):
        self.assertIn("embed/dQw4w9WgXcQ", url_de_lecture("https://youtu.be/dQw4w9WgXcQ"))
        self.assertIn("embed/v2/7234567890123456789",
                      url_de_lecture("https://www.tiktok.com/@moi/video/7234567890123456789"))
        self.assertEqual(url_de_lecture("https://www.facebook.com/watch/?v=123"), "")


@override_settings(MEDIA_ROOT=MEDIA_DE_TEST)
class AjoutDeVideo(BaseVideo):
    def setUp(self):
        self.cat = Category.objects.create(name="Meubles", slug="meubles")
        self.vendeur = User.objects.create_user("vendeur", password="x")
        self.vendeur.profile.user_type = "seller"
        # Un vendeur qui existe a payé son pack : sa boutique est ouverte.
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.extra_slots = 10
        self.vendeur.profile.store_name = "Chez Moussa"
        self.vendeur.profile.save()
        self.produit = Product.objects.create(
            name="Table", slug="table", description="d", base_price=20000, stock=1,
            category=self.cat, seller=self.vendeur, is_approved=True,
        )

    def _fichier(self, secondes=10, mo=1):
        return SimpleUploadedFile(
            "clip.mp4", faux_mp4(secondes, int(mo * 1024 * 1024)), content_type="video/mp4"
        )

    def test_ajout_d_un_fichier(self):
        video = ajouter_video(self.vendeur, self.produit, fichier=self._fichier(12))
        self.assertTrue(video.is_hosted)
        self.assertEqual(video.duration, 12)
        self.assertIn(video, Video.pour(self.produit))
        self.assertEqual(emplacements(self.vendeur)["utilises"], 1)

    def test_video_trop_longue_refusee(self):
        with self.assertRaises(ValidationError) as erreur:
            ajouter_video(self.vendeur, self.produit, fichier=self._fichier(120))
        self.assertIn("trop longue", " ".join(erreur.exception.messages))

    def test_video_trop_lourde_refusee(self):
        from django.conf import settings
        settings.EAZYMARKET["VIDEO_MAX_MB"] = 1
        try:
            with self.assertRaises(ValidationError) as erreur:
                ajouter_video(self.vendeur, self.produit, fichier=self._fichier(5, mo=3))
            self.assertIn("trop lourde", " ".join(erreur.exception.messages))
        finally:
            settings.EAZYMARKET["VIDEO_MAX_MB"] = 15

    def test_format_refuse(self):
        mauvais = SimpleUploadedFile("virus.exe", b"MZ...", content_type="video/mp4")
        with self.assertRaises(ValidationError):
            ajouter_video(self.vendeur, self.produit, fichier=mauvais)

    def test_lien_externe_gratuit_et_hors_quota(self):
        video = ajouter_video(
            self.vendeur, self.produit,
            lien="https://www.tiktok.com/@moussa/video/7234567890123456789",
        )
        self.assertFalse(video.is_hosted)
        self.assertEqual(video.plateforme, "tiktok")
        # Un lien n'occupe aucun emplacement : il ne coûte rien à la plateforme.
        self.assertEqual(emplacements(self.vendeur)["utilises"], 0)

    def test_lien_non_reconnu_refuse(self):
        with self.assertRaises(ValidationError):
            ajouter_video(self.vendeur, self.produit, lien="https://site-inconnu.tld/x")

    def test_quota_epuise(self):
        for _ in range(3):
            produit = Product.objects.create(
                name=f"Objet {_}", slug=f"objet-{_}", description="d", base_price=1000,
                stock=1, category=self.cat, seller=self.vendeur, is_approved=True,
            )
            ajouter_video(self.vendeur, produit, fichier=self._fichier(5))

        etat = emplacements(self.vendeur)
        self.assertEqual(etat["restants"], 0)
        with self.assertRaises(ValidationError) as erreur:
            ajouter_video(self.vendeur, self.produit, fichier=self._fichier(5))
        message = " ".join(erreur.exception.messages)
        self.assertIn("emplacements vidéo sont occupés", message)
        # Le message doit rappeler la porte de sortie gratuite.
        self.assertIn("TikTok", message)

    def test_le_lien_passe_meme_quota_plein(self):
        for i in range(3):
            produit = Product.objects.create(
                name=f"Objet {i}", slug=f"o-{i}", description="d", base_price=1000,
                stock=1, category=self.cat, seller=self.vendeur, is_approved=True,
            )
            ajouter_video(self.vendeur, produit, fichier=self._fichier(5))
        video = ajouter_video(
            self.vendeur, self.produit, lien="https://youtu.be/dQw4w9WgXcQ"
        )
        self.assertFalse(video.is_hosted)

    def test_supprimer_libere_l_emplacement_et_le_fichier(self):
        video = ajouter_video(self.vendeur, self.produit, fichier=self._fichier(5))
        chemin = video.file.name
        stockage = video.file.storage
        self.assertTrue(stockage.exists(chemin))
        video.delete()
        self.assertFalse(stockage.exists(chemin))
        self.assertEqual(emplacements(self.vendeur)["utilises"], 0)

    def test_maximum_par_fiche(self):
        for _ in range(3):
            ajouter_video(self.vendeur, self.produit, lien="https://youtu.be/dQw4w9WgXcQ")
        with self.assertRaises(ValidationError) as erreur:
            ajouter_video(self.vendeur, self.produit, lien="https://youtu.be/autre1")
        self.assertIn("déjà 3 vidéos", " ".join(erreur.exception.messages))

    def test_video_retiree_invisible_du_public(self):
        video = ajouter_video(self.vendeur, self.produit, lien="https://youtu.be/dQw4w9WgXcQ")
        video.is_approved = False
        video.save()
        self.assertNotIn(video, Video.pour(self.produit))
        self.assertIn(video, Video.toutes_pour(self.produit))


@override_settings(MEDIA_ROOT=MEDIA_DE_TEST)
class PagesVideo(BaseVideo):
    def setUp(self):
        self.cat = Category.objects.create(name="Meubles", slug="meubles")
        self.vendeur = User.objects.create_user("v", password="x")
        self.vendeur.profile.user_type = "seller"
        # Un vendeur qui existe a payé son pack : sa boutique est ouverte.
        self.vendeur.profile.is_store_active = True
        self.vendeur.profile.extra_slots = 10
        self.vendeur.profile.save()
        self.produit = Product.objects.create(
            name="Table", slug="table", description="d", base_price=20000, stock=1,
            category=self.cat, seller=self.vendeur, is_approved=True,
        )

    def test_la_fiche_produit_affiche_la_video(self):
        ajouter_video(self.vendeur, self.produit,
                      lien="https://www.tiktok.com/@a/video/7234567890123456789",
                      titre="Tour de la table")
        reponse = self.client.get(self.produit.get_absolute_url())
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Tour de la table")
        self.assertContains(reponse, "tiktok.com/embed/v2/")
        # Rien ne doit se télécharger tout seul.
        self.assertNotContains(reponse, "autoplay")

    def test_envoi_depuis_le_tableau_de_bord(self):
        self.client.login(username="v", password="x")
        reponse = self.client.post(
            reverse("add_video"),
            {"cible": "produit", "produit_id": self.produit.id,
             "external_url": "https://youtu.be/dQw4w9WgXcQ", "title": "Ma table"},
            follow=True,
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Video.pour(self.produit).count(), 1)

    def test_on_ne_peut_pas_publier_sur_le_produit_d_un_autre(self):
        autre = User.objects.create_user("intrus", password="x")
        self.client.login(username="intrus", password="x")
        reponse = self.client.post(
            reverse("add_video"),
            {"cible": "produit", "produit_id": self.produit.id,
             "external_url": "https://youtu.be/dQw4w9WgXcQ"},
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(Video.objects.count(), 0)
        autre.delete()

    def test_on_ne_supprime_que_ses_propres_videos(self):
        video = ajouter_video(self.vendeur, self.produit, lien="https://youtu.be/dQw4w9WgXcQ")
        User.objects.create_user("intrus2", password="x")
        self.client.login(username="intrus2", password="x")
        reponse = self.client.post(reverse("delete_video", args=[video.id]))
        self.assertEqual(reponse.status_code, 404)
        self.assertTrue(Video.objects.filter(pk=video.pk).exists())

    def test_page_d_achat_d_emplacements(self):
        self.client.login(username="v", password="x")
        reponse = self.client.get(reverse("buy_video_slots"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Avant de payer, essayez le lien")

    def test_achat_credite_les_emplacements(self):
        from payments.models import Transaction
        from payments.services import confirm_transaction

        self.client.login(username="v", password="x")
        self.client.post(reverse("buy_video_slots"), {"packs": "2"})
        tx = Transaction.objects.get(purpose=Transaction.Purpose.VIDEO_PACK)
        self.assertEqual(tx.amount, 1000)
        confirm_transaction(tx)
        self.vendeur.profile.refresh_from_db()
        self.assertEqual(self.vendeur.profile.extra_video_slots, 10)
        self.assertEqual(emplacements(self.vendeur)["total"], 13)
